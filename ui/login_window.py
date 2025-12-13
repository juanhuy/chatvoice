# ui/login_window.py
import customtkinter as ctk
from tkinter import messagebox

# Colors
BG_COLOR = "#36393f"
ACCENT_COLOR = "#5865F2"
GREEN_COLOR = "#3ba55c"
INPUT_BG = "#202225"

class LoginWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Đăng nhập")
        self.geometry("400x500") # Tăng chiều cao để chứa đủ nút
        self.resizable(False, False)
        self.configure(fg_color=BG_COLOR)
        
        self.main_frame = ctk.CTkFrame(self, fg_color=BG_COLOR, corner_radius=10)
        self.main_frame.pack(pady=40, padx=40, fill="both", expand=True)

        ctk.CTkLabel(self.main_frame, text="LAN CHAT", 
                     font=("Arial", 24, "bold"), text_color="white").pack(pady=(10, 20))

        # IP
        ctk.CTkLabel(self.main_frame, text="IP SERVER", 
                     font=("Arial", 11, "bold"), text_color="#b9bbbe", anchor="w").pack(fill="x")
        self.ip = ctk.CTkEntry(self.main_frame, placeholder_text="127.0.0.1", 
                               fg_color=INPUT_BG, border_width=0, height=40, text_color="white")
        self.ip.pack(fill="x", pady=(0, 10))
        self.ip.insert(0, "127.0.0.1")

        # User
        ctk.CTkLabel(self.main_frame, text="USERNAME", 
                     font=("Arial", 11, "bold"), text_color="#b9bbbe", anchor="w").pack(fill="x")
        self.user = ctk.CTkEntry(self.main_frame, placeholder_text="Tên đăng nhập", 
                                 fg_color=INPUT_BG, border_width=0, height=40, text_color="white")
        self.user.pack(fill="x", pady=(0, 10))

        # Pass
        ctk.CTkLabel(self.main_frame, text="PASSWORD", 
                     font=("Arial", 11, "bold"), text_color="#b9bbbe", anchor="w").pack(fill="x")
        self.pwd = ctk.CTkEntry(self.main_frame, placeholder_text="Mật khẩu", show="*", 
                                fg_color=INPUT_BG, border_width=0, height=40, text_color="white")
        self.pwd.pack(fill="x", pady=(0, 20))

        # Button
        self.btn_login = ctk.CTkButton(self.main_frame, text="Vào Chat", 
                                       fg_color=ACCENT_COLOR, hover_color="#4752C4", 
                                       height=45, font=("Arial", 14, "bold"),
                                       command=self.on_login)
        self.btn_login.pack(fill="x", pady=10)

        self.btn_register = ctk.CTkButton(self.main_frame, text="Đăng Ký", 
                                          fg_color=GREEN_COLOR, hover_color="#2D7D46",
                                          height=45, font=("Arial", 14, "bold"),
                                          command=self.on_register)
        self.btn_register.pack(fill="x", pady=5)

        self.protocol("WM_DELETE_WINDOW", parent.destroy)

    def on_login(self):
        ip = self.ip.get()
        user = self.user.get()
        pwd = self.pwd.get()
        if not ip or not user:
            messagebox.showwarning("Lỗi", "Nhập IP và Tên!")
            return
        # Gọi về main (không cần mode="login" nữa vì chỉ có 1 chức năng)
        self.parent.connect_server(ip, user, pwd)

    def on_register(self):
        ip = self.ip.get()
        user = self.user.get()
        pwd = self.pwd.get()
        if not ip or not user or not pwd:
            messagebox.showwarning("Lỗi", "Vui lòng nhập đầy đủ thông tin để đăng ký!")
            return
        
        self.parent.register_user(ip, user, pwd)