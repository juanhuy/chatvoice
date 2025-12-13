# server.py
import socket
import threading
import json
import os
import time
import uuid
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
offline_messages = {}     # {username: [msg_obj]}
GROUPS_FILE = "groups.json" # File lưu danh sách nhóm
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
                            msgs = offline_messages.get(username, [])
                            for m in msgs:
                                payload = (
                                    f"{m['type']}::{m['id']}::{m['sender']}::{m['receiver']}::"
                                    .encode() + m["data"].encode("latin1")
                                )
                                send_msg(conn, payload)
                                    

                else:
                    send_msg(conn, b"LOGIN_FAIL::Sai mat khau")
                 # ---------- ACK ----------
            elif msg_type == "ACK":
                msg_id = parts[1].decode()

                if not username:
                    continue

                with lock:
                    msgs = offline_messages.get(username, [])
                    offline_messages[username] = [m for m in msgs if m["id"] != msg_id]
                    if not offline_messages[username]:
                        offline_messages.pop(username, None)


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

            # --- XỬ LÝ TIN NHẮN & CUỘC GỌI ---
            elif msg_type in ["TEXTMSG", "VOICEMSG", "FILE", "CALL_REQUEST", "CALL_ACCEPT", "CALL_REJECT", "CALL_END", "AUDIO_STREAM"]:
                if not username: continue
                sender = parts[1].decode()
                receiver = parts[2].decode()
                payload = parts[3] if len(parts) > 3 else b""

                # --- LƯU TIN NHẮN ---
                if sender != username:
                    continue

                msg_id = str(uuid.uuid4())
                msg_obj = {
                    "id": msg_id,
                    "type": msg_type,
                    "sender": sender,
                    "receiver": receiver,
                    "data": payload.decode("latin1"),
                    "time": int(time.time())
                }

                send_payload = (
                    f"{msg_type}::{msg_id}::{sender}::{receiver}::"
                    .encode() + payload
                )

                def deliver(user):
                    print("SEND:", send_payload[:100])
                    if user in clients:
                        send_msg(clients[user], send_payload)
                    else:
                        offline_messages.setdefault(user, []).append(msg_obj.copy())

                if receiver == "ALL":
                    with lock:
                        for u in ALLOWED_USERS:
                            #if u == sender: continue
                            # if u in clients and u!= sender: send_msg(clients[u], send_payload)
                            # else:
                            #     msg_copy = msg_obj.copy()
                            #     msg_copy["delivered"] = False
                            #     offline_messages.setdefault(u, []).append(msg_copy)
                            if u != sender:
                                deliver(u)  

                elif receiver in groups:
                    member_list = groups[receiver]
                    with lock:
                        # for mem in member_list:
                            # if mem == sender:
                            #     continue
                            # if mem in clients and u!= sender:
                            #     send_msg(clients[mem], send_payload)
                            # else:
                            #     msg_copy = msg_obj.copy()
                            #     msg_copy["delivered"] = False
                            #     offline_messages.setdefault(mem, []).append(msg_copy)
                        for mem in groups[receiver]:    
                            if mem != sender:
                                deliver(mem)
      
                else:
                    with lock:
                        # target = clients.get(receiver)
                        # if target: send_msg(target, send_payload)
                        # else:
                            # msg_copy = msg_obj.copy()
                            # msg_copy["delivered"] = False                    
                            # offline_messages.setdefault(receiver, []).append(msg_copy)
                            deliver(receiver)

        except Exception as e:
            print(f"Lỗi client {username}: {e}")
            break

    if username:
        with lock: 
            if username in clients: del clients[username]
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