# server.py
import socket
import threading
import json
import os
from config import HOST, PORT, HEADER_SIZE

# --- CẤU HÌNH ---
ALLOWED_USERS = {
    "admin": "123456",
    "huy": "123456",
    "phuoc": "123456",
    "khanh": "123456",
    "phu": "123456",
    "chi": "123456",
}

# --- LƯU TRỮ ---
clients = {} # {username: socket}
groups = {}  # {group_name: [member1, member2, ...]}
active_calls = {} # {group_name: {user1, user2, ...}}
GROUPS_FILE = "groups.json" # File lưu danh sách nhóm
# File lưu tin nhắn
MESSAGES_FILE = "messages.json"
messages = []  # danh sách tin nhắn đã lưu {type, sender, receiver, data}
lock = threading.Lock()

# --- HÀM XỬ LÝ FILE NHÓM ---
def load_groups():
    global groups
    if not os.path.exists(GROUPS_FILE):
        return
    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            groups = json.load(f)
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
                
                if login_user in ALLOWED_USERS and ALLOWED_USERS[login_user] == login_pass:
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
                            for grp_name, members in groups.items():
                                if username in members:
                                    # Gửi lệnh giả lập như vừa được mời vào nhóm
                                    payload = f"GROUP_ADDED::{grp_name}".encode('utf-8')
                                    send_msg(conn, payload)
                        # ------------------------------------------------
                        # ---- GỬI TIN NHẮN CŨ CHO USER (OFFLINE MSG) ----
                        with lock:
                            for msg in messages:
                                recv = msg["receiver"]

                                if recv == "ALL" or recv == username or (recv in groups and username in groups.get(recv, [])):
                                    
                                    # reconstruct message protocol
                                    reconstructed = (
                                        f"{msg['type']}::{msg['sender']}::{msg['receiver']}::".encode() +
                                        msg["data"].encode("latin1")
                                    )
                                    send_msg(conn, reconstructed) 

                else:
                    send_msg(conn, b"LOGIN_FAIL::Sai mat khau")
 
            # --- XỬ LÝ TẠO NHÓM ---
            elif msg_type == "GROUP_CREATE":
                group_name = parts[1].decode()
                members_str = parts[2].decode()
                members = members_str.split(",")
                
                with lock:
                    groups[group_name] = members
                    save_groups() # <--- LƯU NGAY VÀO FILE
                
                print(f"[G] Nhóm mới: {group_name} - TV: {members}")
                
                notify_payload = f"GROUP_ADDED::{group_name}".encode('utf-8')
                with lock:
                    for mem in members:
                        if mem in clients:
                            send_msg(clients[mem], notify_payload)

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
                    members = groups[group_name]
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
                                for mem in groups[group_name]:
                                    if mem in clients:
                                        send_msg(clients[mem], notify_payload)

            # --- XỬ LÝ TIN NHẮN & CUỘC GỌI ---
            elif msg_type in ["TEXTMSG", "VOICEMSG", "FILE", "CALL_REQUEST", "CALL_ACCEPT", "CALL_REJECT", "CALL_END", "AUDIO_STREAM"]:
                if not username: continue
                sender = parts[1].decode()
                receiver = parts[2].decode()
                payload = parts[3] if len(parts) > 3 else b""

                # --- LƯU TIN NHẮN (TRỪ AUDIO STREAM) ---
                if msg_type != "AUDIO_STREAM":
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
                    member_list = groups[receiver]
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
    # Load nhóm cũ lên khi khởi động server
    load_groups()
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()
    print(f"Server đang chạy tại {HOST}:{PORT}")
    print("Danh sách User:", list(ALLOWED_USERS.keys()))
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start()