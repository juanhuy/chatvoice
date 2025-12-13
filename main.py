# main.py
import customtkinter as ctk
import threading
from tkinter import messagebox
from modules.network import NetworkClient
from modules.audio import AudioManager
from ui.login_window import LoginWindow
from ui.chat_window import ChatWindow

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw() # Ẩn cửa sổ chính
        self.title("Lan Voice Chat")
        self.geometry("1000x650") 

        # Init Modules
        self.network = NetworkClient()
        self.audio = AudioManager()
        
        # Show Login
        self.login_win = LoginWindow(self)
        self.chat_ui = None

    def connect_server(self, ip, user, pwd):
        result = self.network.connect(ip, user, pwd)
        print(f"DEBUG: Kết quả từ Server trả về là: '{result}'") 

        if result == "OK":
            self.login_win.destroy()
            self.deiconify() # Hiện cửa sổ chính
            
            # Khởi tạo giao diện chat
            self.chat_ui = ChatWindow(self, self.network, self.audio, user)
            self.chat_ui.pack(fill="both", expand=True) 
            
            # Bắt đầu luồng nhận tin nhắn
            threading.Thread(target=self.network.receive_loop, 
                             args=(self.on_data_received,), daemon=True).start()
        else:
            messagebox.showerror("Đăng nhập thất bại", f"Lỗi từ Server:\n{result}")

    def register_user(self, ip, user, pwd):
        result = self.network.register(ip, user, pwd)
        if result == "OK":
            messagebox.showinfo("Thành công", "Đăng ký thành công! Bạn có thể đăng nhập ngay.")
        else:
            messagebox.showerror("Thất bại", f"Đăng ký thất bại:\n{result}")

    def on_data_received(self, data):
        # Hàm callback xử lý dữ liệu từ Network gửi về
        try:
            if data == b"LOGIN_OK": return
            
            # 1. Cập nhật danh sách User online
            if data.startswith(b"USERLIST::"):
                try:
                    users = data.decode().split("::")[1]
                    self.chat_ui.after(0, lambda: self.chat_ui.update_user_list(users))
                except: pass

            # 2. Xử lý khi được thêm vào NHÓM (Mới)
            elif data.startswith(b"GROUP_ADDED::"):
                group_name = data.decode().split("::")[1]
                self.chat_ui.after(0, lambda: self.chat_ui.on_group_created(group_name))

            # 2b. Xử lý khi bị xóa khỏi NHÓM (Mới)
            elif data.startswith(b"GROUP_REMOVED::"):
                group_name = data.decode().split("::")[1]
                self.chat_ui.after(0, lambda: self.chat_ui.on_group_removed(group_name))

            # 2c. Xử lý khi NHÓM BỊ GIẢI TÁN (Mới)
            elif data.startswith(b"GROUP_DELETED::"):
                group_name = data.decode().split("::")[1]
                self.chat_ui.after(0, lambda: self.chat_ui.on_group_deleted(group_name))
                
            # 3. Xử lý Tin nhắn văn bản
            elif data.startswith(b"TEXTMSG::"):
                parts = data.decode().split("::", 3)
                if len(parts) == 4:
                    sender, receiver, msg = parts[1], parts[2], parts[3]
                    
                    # Logic xác định Tab hiển thị:
                    # - Nếu receiver là ALL -> Tab ALL
                    # - Nếu receiver là tên một nhóm mình đã tham gia -> Tab Nhóm đó
                    # - Nếu receiver là mình (tin riêng cho mình) -> Tab là tên người gửi
                    if receiver == "ALL":
                        target_tab = "ALL"
                    elif self.chat_ui and receiver in self.chat_ui.joined_groups:
                        target_tab = receiver
                    elif receiver == self.chat_ui.username:  # Tin nhắn riêng cho mình
                        target_tab = sender
                    else:
                        target_tab = receiver  # Chat riêng với người khác
                        
                    self.chat_ui.after(0, lambda: self.chat_ui.display_msg(sender, msg, target_tab))
                
            # 4. Xử lý Tin nhắn thoại
            elif data.startswith(b"VOICEMSG::"):
                parts = data.split(b"::", 3)
                if len(parts) == 4:
                    sender, receiver, audio = parts[1].decode(), parts[2].decode(), parts[3]
                    
                    if receiver == "ALL":
                        target_tab = "ALL"
                    elif self.chat_ui and receiver in self.chat_ui.joined_groups:
                        target_tab = receiver
                    elif receiver == self.chat_ui.username:  # Voice riêng cho mình
                        target_tab = sender
                    else:
                        target_tab = receiver  # Voice riêng với người khác
                    
                    self.chat_ui.after(0, lambda: self.chat_ui.display_msg(sender, audio, target_tab, True))

            # 5. Xử lý File
            elif data.startswith(b"FILE::"):
                parts = data.split(b"::", 4)
                if len(parts) == 5:
                    sender, receiver, fname = parts[1].decode(), parts[2].decode(), parts[3].decode()
                    
                    if receiver == "ALL": target_tab = "ALL"
                    elif self.chat_ui and receiver in self.chat_ui.joined_groups: target_tab = receiver
                    elif receiver == self.chat_ui.username: target_tab = sender
                    else: target_tab = receiver
                    
                    self.chat_ui.after(0, lambda: self.chat_ui.display_msg(sender, f"[Nhận file] {fname}", target_tab))

            # 6. Xử lý Call Request
            elif data.startswith(b"CALL_REQUEST::"):
                sender = data.decode().split("::")[1]
                self.chat_ui.after(0, lambda: self.chat_ui.handle_call_request(sender))

            # 7. Xử lý Call Response (Accept/Reject/End)
            elif any(data.startswith(prefix) for prefix in [b"CALL_ACCEPT::", b"CALL_REJECT::", b"CALL_END::"]):
                parts = data.decode().split("::")
                msg_type = parts[0]
                sender = parts[1]
                self.chat_ui.after(0, lambda: self.chat_ui.handle_call_response(msg_type, sender))

            # 8. Xử lý Audio Stream
            elif data.startswith(b"AUDIO_STREAM::"):
                parts = data.split(b"::", 3)
                if len(parts) == 4:
                    audio_data = parts[3]
                    self.audio.play_stream_chunk(audio_data)

            # 9. Xử lý Group Call Started
            elif data.startswith(b"GROUP_CALL_STARTED::"):
                parts = data.decode().split("::")
                sender = parts[1]
                group_name = parts[2]
                self.chat_ui.after(0, lambda: self.chat_ui.handle_group_call_started(sender, group_name))

            # 10. Xử lý Group Call Ended
            elif data.startswith(b"GROUP_CALL_ENDED::"):
                group_name = data.decode().split("::")[1]
                self.chat_ui.after(0, lambda: self.chat_ui.handle_group_call_ended(group_name))

            # 11. Xử lý Group Members List
            elif data.startswith(b"GROUP_MEMBERS::"):
                parts = data.decode().split("::")
                group_name = parts[1]
                members_str = parts[2]
                admin_name = parts[3] if len(parts) > 3 else ""
                self.chat_ui.after(0, lambda: self.chat_ui.display_group_members(group_name, members_str, admin_name))

            # 12. Xử lý All Users List (cho tính năng Add Member)
            elif data.startswith(b"ALL_USERS::"):
                users_str = data.decode().split("::")[1]
                self.chat_ui.after(0, lambda: self.chat_ui.update_all_users_combo(users_str))

        except Exception as e:
            print(f"Error parsing data: {e}")

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()