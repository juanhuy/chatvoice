# modules/network.py
import socket
from config import PORT, HEADER_SIZE

class NetworkClient:
    def __init__(self):
        self.client = None
        self.connected = False

    def connect(self, ip, username, password):
        try:
            # 1. Tạo kết nối Socket
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.settimeout(3) # Nếu server không trả lời sau 3s thì báo lỗi
            self.client.connect((ip, PORT))
            
            # 2. Gửi thông tin đăng nhập
            payload = f"LOGIN::{username}::{password}".encode('utf-8')
            header = f"{len(payload):<{HEADER_SIZE}}".encode('utf-8')
            self.client.sendall(header + payload)
            
            # 3. QUAN TRỌNG: Ngồi đợi Server trả lời "LOGIN_OK" hay "LOGIN_FAIL"
            # (Code cũ thiếu đoạn này nên nó cứ thế chạy tiếp)
            resp_header = self.client.recv(HEADER_SIZE)
            if not resp_header: return "Mất kết nối với Server"
            
            msg_len = int(resp_header.decode().strip())
            response = self.client.recv(msg_len).decode()
            
            # 4. Kiểm tra câu trả lời
            if response == "LOGIN_OK":
                self.connected = True
                self.client.settimeout(None) # Đăng nhập xong thì bỏ timeout để chat
                return "OK"
            elif response.startswith("LOGIN_FAIL"):
                self.client.close()
                # Trả về lý do lỗi (ví dụ: Sai mật khẩu)
                return response.split("::")[1] if "::" in response else "Đăng nhập thất bại"
            else:
                self.client.close()
                return "Phản hồi lạ từ Server"
                
        except Exception as e:
            if self.client: self.client.close()
            return f"Lỗi kết nối: {str(e)}"

    def register(self, ip, username, password):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(3)
            client.connect((ip, PORT))
            
            payload = f"REGISTER::{username}::{password}".encode('utf-8')
            header = f"{len(payload):<{HEADER_SIZE}}".encode('utf-8')
            client.sendall(header + payload)
            
            resp_header = client.recv(HEADER_SIZE)
            if not resp_header: return "Mất kết nối"
            
            msg_len = int(resp_header.decode().strip())
            response = client.recv(msg_len).decode()
            
            client.close()
            
            if response == "REGISTER_OK": return "OK"
            elif response.startswith("REGISTER_FAIL"):
                return response.split("::")[1]
            else: return "Lỗi không xác định"
            
        except Exception as e:
            return f"Lỗi: {str(e)}"

    def send(self, data):
        if not self.connected: return
        try:
            header = f"{len(data):<{HEADER_SIZE}}".encode('utf-8')
            self.client.sendall(header + data)
        except:
            self.disconnect()

    def receive_loop(self, callback_func):
        while self.connected:
            try:
                header = self.client.recv(HEADER_SIZE)
                if not header: break
                msg_len = int(header.decode().strip())
                
                data = b""
                while len(data) < msg_len:
                    packet = self.client.recv(msg_len - len(data))
                    if not packet: break
                    data += packet
                
                if data: callback_func(data)
            except: break
        self.disconnect()

    def disconnect(self):
        self.connected = False
        if self.client: 
            try: self.client.close()
            except: pass