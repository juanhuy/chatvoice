# server.py
import socket
import threading
import json
import os
from config import HOST, PORT, HEADER_SIZE

# --- CẤU HÌNH ---
USERS_FILE = "users.json"
users_db = {}

# --- LƯU TRỮ ---
clients = {} # {username: socket}
groups = {}  # {group_name: [member1, member2, ...]}
active_calls = {} # {group_name: {user1, user2, ...}}
GROUPS_FILE = "groups.json" # File lưu danh sách nhóm
# File lưu tin nhắn
MESSAGES_FILE = "messages.json"
messages = []  # danh sách tin nhắn đã lưu {type, sender, receiver, data}
lock = threading.Lock()

# --- HÀM XỬ LÝ USER ---
def load_users():
    global users_db
    if not os.path.exists(USERS_FILE): return
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users_db = json.load(f)
            print(f"[*] Đã tải {len(users_db)} users.")
    except: pass

def save_users():
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_db, f, ensure_ascii=False, indent=4)
    except: pass

# --- HÀM XỬ LÝ FILE NHÓM ---
def load_groups():
    global groups
    if not os.path.exists(GROUPS_FILE):
        return
    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # --- MIGRATION: Convert list to dict if needed ---
            groups = {}
            for name, val in data.items():
                if isinstance(val, list):
                    # Old format: assume first member is admin
                    groups[name] = {"members": val, "admin": val[0] if val else "admin"}
                else:
                    groups[name] = val
            # -------------------------------------------------
            print(f"[*] Đã tải {len(groups)} nhóm từ file.")
    except Exception as e:
        print(f"[!] Lỗi tải file nhóm: {e}")

def save_groups():
    try:
        with open(GROUPS_FILE, "w", encoding="utf-8") as f:
            json.dump(groups, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[!] Lỗi lưu nhóm: {e}")
# ---LOAD / SAVE MESSAGES---
def load_messages():
    global messages
    if not os.path.exists(MESSAGES_FILE):
        messages = []
        return
    try:
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            messages = json.load(f)
            print(f"[*] Đã tải {len(messages)} tin nhắn.")
    except:
        messages = []

def save_messages():
    try:
        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print("[!] Lỗi lưu tin nhắn:", e)

# --- XỬ LÝ MẠNG ---
def send_msg(sock, data):
    try:
        header = f"{len(data):<{HEADER_SIZE}}".encode('utf-8')
        sock.sendall(header + data)
    except: pass

def broadcast_user_list():
    with lock:
        users = ",".join(clients.keys())
        payload = f"USERLIST::{users}".encode('utf-8')
        for s in clients.values(): send_msg(s, payload)

def handle_client(conn, addr):
    print(f"[+] Kết nối từ {addr}")
    username = None
    
    while True:
        try:
            header = conn.recv(HEADER_SIZE)
            if not header: break
            
            try: msg_len = int(header.decode().strip())
            except: break
            
            data = b""
            while len(data) < msg_len:
                packet = conn.recv(msg_len - len(data))
                if not packet: break
                data += packet
            if not data: break

            parts = data.split(b"::", 3)
            msg_type = parts[0].decode()

            # --- XỬ LÝ LOGIN ---
            if msg_type == "LOGIN":
                login_user = parts[1].decode()
                login_pass = parts[2].decode()
                
                if login_user in users_db and users_db[login_user] == login_pass:
                    is_online = False
                    with lock:
                        if login_user in clients: is_online = True
                    
                    if is_online:
                        send_msg(conn, b"LOGIN_FAIL::Tai khoan dang online")
                    else:
                        with lock: clients[login_user] = conn
                        username = login_user
                        send_msg(conn, b"LOGIN_OK")
                        broadcast_user_list()
                        print(f"[+] {username} đã đăng nhập.")

                        # --- TÍNH NĂNG MỚI: GỬI LẠI DANH SÁCH NHÓM CŨ ---
                        # Kiểm tra xem user này có trong nhóm nào không, nếu có thì gửi lệnh ADD
                        with lock:
                            for grp_name, info in groups.items():
                                if username in info["members"]:
                                    # Gửi lệnh giả lập như vừa được mời vào nhóm
                                    payload = f"GROUP_ADDED::{grp_name}".encode('utf-8')
                                    send_msg(conn, payload)
                        # ------------------------------------------------
                        # ---- GỬI TIN NHẮN CŨ CHO USER (OFFLINE MSG) ----
                        with lock:
                            for msg in messages:
                                # Chỉ gửi lại tin nhắn nội dung, không gửi lại lệnh Call/System cũ
                                if msg["type"] not in ["TEXTMSG", "VOICEMSG", "FILE"]:
                                    continue

                                recv = msg["receiver"]

                                if recv == "ALL" or recv == username or (recv in groups and username in groups[recv]["members"]):
                                    
                                    # reconstruct message protocol
                                    reconstructed = (
                                        f"{msg['type']}::{msg['sender']}::{msg['receiver']}::".encode() +
                                        msg["data"].encode("latin1")
                                    )
                                    send_msg(conn, reconstructed) 

                else:
                    send_msg(conn, b"LOGIN_FAIL::Sai mat khau hoac tai khoan khong ton tai")

            # --- XỬ LÝ ĐĂNG KÝ (MỚI) ---
            elif msg_type == "REGISTER":
                reg_user = parts[1].decode()
                reg_pass = parts[2].decode()
                
                if reg_user in users_db:
                    send_msg(conn, b"REGISTER_FAIL::Tai khoan da ton tai")
                else:
                    with lock:
                        users_db[reg_user] = reg_pass
                        save_users()
                    send_msg(conn, b"REGISTER_OK")
                    print(f"[+] Đăng ký mới: {reg_user}")
 
            # --- XỬ LÝ TẠO NHÓM ---
            elif msg_type == "GROUP_CREATE":
                group_name = parts[1].decode()
                members_str = parts[2].decode()
                members = members_str.split(",")
                
                # Người tạo nhóm là admin (username hiện tại của session này)
                admin = username

                with lock:
                    groups[group_name] = {
                        "members": members,
                        "admin": admin
                    }
                    save_groups() # <--- LƯU NGAY VÀO FILE
                
                print(f"[G] Nhóm mới: {group_name} - Admin: {admin} - TV: {members}")
                
                notify_payload = f"GROUP_ADDED::{group_name}".encode('utf-8')
                with lock:
                    for mem in members:
                        if mem in clients:
                            send_msg(clients[mem], notify_payload)

            # --- XỬ LÝ THÊM THÀNH VIÊN VÀO NHÓM (MỚI) ---
            elif msg_type == "GROUP_ADD_MEMBER":
                group_name = parts[1].decode()
                new_member = parts[2].decode()
                
                with lock:
                    if group_name in groups:
                        # Check if user is admin? (Optional, but good practice. For now let's allow any member to add? Or restrict?)
                        # User didn't ask to restrict ADD, only REMOVE. So I'll keep ADD open or maybe restrict it too?
                        # The prompt said "người tạo sẽ là admin nhóm đó" and "nút xóa thành viên".
                        # Usually only admin adds too, but let's stick to the request: "ok cho tôi nút xóa thành viên với".
                        # I will just update the structure access.
                        
                        current_members = groups[group_name]["members"]
                        if new_member not in current_members:
                            current_members.append(new_member)
                            save_groups()
                            
                            # Thông báo cho thành viên mới biết là họ đã được thêm vào nhóm
                            if new_member in clients:
                                send_msg(clients[new_member], f"GROUP_ADDED::{group_name}".encode('utf-8'))
                                
                            # Gửi lại danh sách thành viên mới cho người yêu cầu (để cập nhật UI)
                            # Cần gửi cả admin để UI biết
                            admin_name = groups[group_name].get("admin", "")
                            members_str = ",".join(current_members)
                            send_msg(conn, f"GROUP_MEMBERS::{group_name}::{members_str}::{admin_name}".encode('utf-8'))

            # --- XỬ LÝ XÓA THÀNH VIÊN KHỎI NHÓM (MỚI) ---
            elif msg_type == "GROUP_REMOVE_MEMBER":
                group_name = parts[1].decode()
                member_to_remove = parts[2].decode()
                
                with lock:
                    if group_name in groups:
                        grp_info = groups[group_name]
                        admin_name = grp_info.get("admin", "")
                        
                        # Chỉ admin mới được xóa, trừ khi tự thoát (nhưng ở đây là nút xóa thành viên)
                        if username == admin_name:
                            if member_to_remove in grp_info["members"]:
                                grp_info["members"].remove(member_to_remove)
                                save_groups()
                                
                                # Thông báo cho người bị xóa (nếu cần, hoặc họ sẽ tự thấy mất nhóm khi refresh/login lại)
                                # Có thể gửi lệnh GROUP_REMOVED nếu muốn realtime, nhưng hiện tại chưa có handler client.
                                # Ít nhất gửi lại danh sách thành viên mới cho admin (người xóa)
                                members_str = ",".join(grp_info["members"])
                                send_msg(conn, f"GROUP_MEMBERS::{group_name}::{members_str}::{admin_name}".encode('utf-8'))
                                
                                # Thông báo cho người bị xóa biết?
                                if member_to_remove in clients:
                                    # Gửi lệnh GROUP_REMOVED để client tự cập nhật UI
                                    send_msg(clients[member_to_remove], f"GROUP_REMOVED::{group_name}".encode('utf-8'))
                        else:
                            # Không phải admin
                            pass

            # --- XỬ LÝ LẤY DANH SÁCH THÀNH VIÊN (MỚI) ---
            elif msg_type == "GROUP_GET_MEMBERS":
                group_name = parts[1].decode()
                with lock:
                    if group_name in groups:
                        members_list = groups[group_name]["members"]
                        admin_name = groups[group_name].get("admin", "")
                        members_str = ",".join(members_list)
                        # Gửi thêm admin_name vào cuối
                        send_msg(conn, f"GROUP_MEMBERS::{group_name}::{members_str}::{admin_name}".encode('utf-8'))

            # --- XỬ LÝ GROUP CALL (MỚI) ---
            elif msg_type == "GROUP_CALL_START":
                sender = parts[1].decode()
                group_name = parts[2].decode()
                
                with lock:
                    if group_name not in active_calls:
                        active_calls[group_name] = set()
                    active_calls[group_name].add(sender)
                
                # Notify all group members that a call started
                if group_name in groups:
                    members = groups[group_name]["members"]
                    notify_payload = f"GROUP_CALL_STARTED::{sender}::{group_name}".encode('utf-8')
                    with lock:
                        for mem in members:
                            if mem != sender and mem in clients:
                                send_msg(clients[mem], notify_payload)

            elif msg_type == "GROUP_CALL_JOIN":
                sender = parts[1].decode()
                group_name = parts[2].decode()
                with lock:
                    if group_name not in active_calls:
                        active_calls[group_name] = set()
                    active_calls[group_name].add(sender)
                
            elif msg_type == "GROUP_CALL_LEAVE":
                sender = parts[1].decode()
                group_name = parts[2].decode()
                with lock:
                    if group_name in active_calls:
                        active_calls[group_name].discard(sender)
                        if not active_calls[group_name]:
                            del active_calls[group_name]
                            # Notify everyone that the call ended
                            if group_name in groups:
                                notify_payload = f"GROUP_CALL_ENDED::{group_name}".encode('utf-8')
                                for mem in groups[group_name]["members"]:
                                    if mem in clients:
                                        send_msg(clients[mem], notify_payload)

            # --- XỬ LÝ TIN NHẮN & CUỘC GỌI ---
            elif msg_type in ["TEXTMSG", "VOICEMSG", "FILE", "CALL_REQUEST", "CALL_ACCEPT", "CALL_REJECT", "CALL_END", "AUDIO_STREAM"]:
                if not username: continue
                sender = parts[1].decode()
                receiver = parts[2].decode()
                payload = parts[3] if len(parts) > 3 else b""

                # --- LƯU TIN NHẮN (CHỈ LƯU TEXT, VOICE, FILE) ---
                if msg_type in ["TEXTMSG", "VOICEMSG", "FILE"]:
                    with lock:
                        messages.append({
                            "type": msg_type,
                            "sender": sender,
                            "receiver": receiver,
                            "data": payload.decode("latin1")   # tránh lỗi nhị phân
                        })
                        save_messages()

                # --- XỬ LÝ AUDIO STREAM CHO GROUP ---
                if msg_type == "AUDIO_STREAM" and receiver in groups:
                     with lock:
                        # Only send to people in the active call
                        if receiver in active_calls:
                            participants = active_calls[receiver]
                            for mem in participants:
                                if mem != sender and mem in clients:
                                    send_msg(clients[mem], data)
                     continue # Skip the default broadcasting
                # ------------------------------------

                if receiver == "ALL":
                    with lock:
                        for u, s in clients.items():
                            if u != sender: send_msg(s, data)
                
                elif receiver in groups:
                    member_list = groups[receiver]["members"]
                    
                    # --- SECURITY CHECK: Sender must be in the group ---
                    if sender not in member_list:
                        # Nếu sender không có trong nhóm, không gửi tin nhắn đi
                        # Có thể gửi thông báo lỗi về cho sender nếu muốn
                        # send_msg(conn, b"ERROR::You are not in this group")
                        continue
                    # ---------------------------------------------------

                    with lock:
                        for mem in member_list:
                            if mem != sender and mem in clients:
                                send_msg(clients[mem], data)
                
                else:
                    with lock:
                        target = clients.get(receiver)
                        if target: send_msg(target, data)

        except Exception as e:
            print(f"Lỗi client {username}: {e}")
            break

    if username:
        with lock: 
            if username in clients: del clients[username]
            # --- CLEANUP ACTIVE CALLS ---
            for grp in list(active_calls.keys()):
                if username in active_calls[grp]:
                    active_calls[grp].discard(username)
                    if not active_calls[grp]:
                        del active_calls[grp]
                        # Notify everyone that the call ended
                        if grp in groups:
                            notify_payload = f"GROUP_CALL_ENDED::{grp}".encode('utf-8')
                            for mem in groups[grp]:
                                if mem in clients:
                                    send_msg(clients[mem], notify_payload)
            # ----------------------------
        broadcast_user_list()
        print(f"[-] {username} đã thoát.")
    conn.close()

def start():
    # Load dữ liệu cũ lên khi khởi động server
    load_groups()
    load_users()
    load_messages()
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()
    print(f"Server đang chạy tại {HOST}:{PORT}")
    print(f"Đã tải {len(users_db)} users.")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start()