# ui/chat_window.py
import customtkinter as ctk
import threading
from tkinter import filedialog, messagebox
import os
from datetime import datetime
import winsound
import json

# --- DISCORD COLOR PALETTE ---
BG_PRIMARY = "#36393f"
BG_SECONDARY = "#2f3136"
BG_TERTIARY = "#202225"
INPUT_BG = "#40444b"
TEXT_COLOR = "#dcddde"
TIMESTAMP_COLOR = "#72767d"
ACCENT_COLOR = "#5865F2"
GREEN_COLOR = "#3ba55c"
RED_COLOR = "#ed4245"
HOVER_COLOR = "#393c43"

class ChatWindow(ctk.CTkFrame):
    def __init__(self, parent, network, audio, username):
        super().__init__(parent)
        self.network = network
        self.audio = audio
        self.username = username
        self.current_receiver = "ALL"
        self.frames_store = {}
        self.online_users = [] 
        self.joined_groups = [] 

        # Tạo thư mục lưu log nếu chưa có
        if not os.path.exists("chat_logs"):
            os.makedirs("chat_logs")

        self.configure(fg_color=BG_PRIMARY)
        self.pack(fill="both", expand=True)

        # === LAYOUT CHÍNH ===
        self.grid_columnconfigure(0, weight=0, minsize=260)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === SIDEBAR TRÁI ===
        self.sidebar = ctk.CTkFrame(self, fg_color=BG_SECONDARY, corner_radius=0, width=260)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # 1. Header Server
        self.server_header = ctk.CTkButton(self.sidebar, text="LAN Voice Server", 
                                           fg_color="transparent", hover_color=HOVER_COLOR,
                                           font=("gg sans", 16, "bold"), anchor="w", height=50)
        self.server_header.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkFrame(self.sidebar, height=1, fg_color="#202225").pack(fill="x", pady=10)

        # 2. Vùng danh sách kênh
        self.channel_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.channel_list.pack(fill="both", expand=True, padx=5)

        # --- CONTAINER ---
        self.group_header_frame = ctk.CTkFrame(self.channel_list, fg_color="transparent")
        self.group_container = ctk.CTkFrame(self.channel_list, fg_color="transparent")
        self.dm_container = ctk.CTkFrame(self.channel_list, fg_color="transparent")

        # 1. Kênh chung
        self.btn_general = self.create_channel_btn("📢  Kênh chung (ALL)", "ALL")
        self.btn_general.pack(fill="x", pady=2)

        # 2. Giao diện Group
        self.group_header_frame.pack(fill="x", pady=(20, 5), padx=5)
        ctk.CTkLabel(self.group_header_frame, text="CÁC NHÓM", 
                     font=("gg sans", 11, "bold"), text_color=TIMESTAMP_COLOR, anchor="w").pack(side="left")
        ctk.CTkButton(self.group_header_frame, text="+", width=20, height=20, 
                      fg_color="transparent", text_color=TIMESTAMP_COLOR, hover_color=HOVER_COLOR,
                      command=self.open_create_group_dialog).pack(side="right")
        self.group_container.pack(fill="x") 

        # 3. Giao diện DM
        ctk.CTkLabel(self.channel_list, text="TIN NHẮN RIÊNG (ONLINE)", 
                     font=("gg sans", 11, "bold"), text_color=TIMESTAMP_COLOR, anchor="w").pack(fill="x", pady=(20, 5), padx=5)
        self.dm_container.pack(fill="x") 

        # 4. Voice Panel
        self.voice_panel = ctk.CTkFrame(self.sidebar, fg_color="#292b2f", height=55)
        self.voice_panel.pack(fill="x", side="bottom")
        
        self.avatar = ctk.CTkButton(self.voice_panel, text=username[:2].upper(), width=35, height=35,
                                    fg_color=GREEN_COLOR, corner_radius=20, hover=False)
        self.avatar.pack(side="left", padx=10, pady=10)
        self.lbl_username = ctk.CTkLabel(self.voice_panel, text=username, font=("gg sans", 13, "bold"), text_color="white")
        self.lbl_username.pack(side="left", pady=10)
        self.btn_mic = ctk.CTkButton(self.voice_panel, text="🎤", width=30, fg_color="transparent", hover_color=HOVER_COLOR, command=self.toggle_rec)
        self.btn_mic.pack(side="right", padx=5)

        # === MAIN CHAT AREA ===
        self.main_area = ctk.CTkFrame(self, fg_color=BG_PRIMARY, corner_radius=0)
        self.main_area.grid(row=0, column=1, sticky="nsew")
        self.main_area.grid_columnconfigure(0, weight=1) # Fix lỗi khoảng trống
        self.main_area.grid_rowconfigure(0, weight=0)
        self.main_area.grid_rowconfigure(1, weight=1)
        self.main_area.grid_rowconfigure(2, weight=0)

        # Header
        self.chat_header = ctk.CTkFrame(self.main_area, fg_color=BG_PRIMARY, height=50, corner_radius=0)
        self.chat_header.grid(row=0, column=0, sticky="ew")
        self.lbl_header_title = ctk.CTkLabel(self.chat_header, text="📢 Kênh chung", 
                                             font=("gg sans", 16, "bold"), text_color="white", anchor="w")
        self.lbl_header_title.pack(side="left", padx=20, pady=15)
        ctk.CTkFrame(self.main_area, height=1, fg_color="#202225").grid(row=0, column=0, sticky="ews")

        # Chat Log
        self.chat_scroll = ctk.CTkScrollableFrame(self.main_area, fg_color=BG_PRIMARY)
        self.chat_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # Input Area
        self.input_area = ctk.CTkFrame(self.main_area, fg_color=BG_PRIMARY, height=70)
        self.input_area.grid(row=2, column=0, sticky="ew")
        self.input_bar = ctk.CTkFrame(self.input_area, fg_color=INPUT_BG, corner_radius=20)
        self.input_bar.pack(fill="x", padx=15, pady=15)
        
        self.btn_file = ctk.CTkButton(self.input_bar, text="➕", width=30, fg_color="transparent", 
                                      hover_color=HOVER_COLOR, text_color="#b9bbbe", command=self.send_file)
        self.btn_file.pack(side="left", padx=5)
        
        self.btn_emoji = ctk.CTkButton(self.input_bar, text="😀", width=30, fg_color="transparent",
                                       hover_color=HOVER_COLOR, text_color="#b9bbbe", command=self.open_emoji_picker)
        self.btn_emoji.pack(side="left", padx=5)

        self.msg_entry = ctk.CTkEntry(self.input_bar, placeholder_text=f"Gửi tin nhắn đến #ALL",
                                      fg_color="transparent", border_width=0, text_color="white", height=40)
        self.msg_entry.pack(side="left", fill="x", expand=True)
        self.msg_entry.bind("<Return>", self.send_text)
        
        self.btn_send = ctk.CTkButton(self.input_bar, text="Gửi", width=50, fg_color="transparent", 
                                      hover_color=HOVER_COLOR, text_color=ACCENT_COLOR, font=("Arial", 12, "bold"),
                                      command=self.send_text)
        self.btn_send.pack(side="right", padx=10)

        # Tự động tạo frame ALL và load lịch sử
        self._get_chat_frame("ALL")

    # --- TÍNH NĂNG 1: LƯU VÀ TẢI LỊCH SỬ CHAT (MỚI) ---
    def save_log(self, receiver, sender, content, msg_type="text"):
        """Lưu tin nhắn vào file JSON"""
        # Tên file: tên_mình_tên_đối_phương.json
        # Ví dụ: Huy_ALL.json, Huy_TeamA.json, Huy_Nam.json
        filename = f"chat_logs/{self.username}_{receiver}.json"
        
        entry = {
            "time": datetime.now().strftime("%H:%M %d/%m"),
            "sender": sender,
            "type": msg_type,
            "content": str(content) if msg_type != "voice" else "[Tin nhắn thoại]" 
        }
        
        data = []
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except: pass
        
        data.append(entry)
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_history(self, target):
        """Đọc file JSON và hiện lại tin nhắn"""
        filename = f"chat_logs/{self.username}_{target}.json"
        if not os.path.exists(filename): return
        
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            for msg in data:
                sender = msg.get("sender", "Unknown")
                content = msg.get("content", "")
                msg_type = msg.get("type", "text")
                is_voice = (msg_type == "voice")
                
                # Gọi display_msg với save=False để KHÔNG lưu lại lần nữa
                self.display_msg(sender, content, target, is_voice, save=False)
                
        except Exception as e:
            print(f"Lỗi load history: {e}")

    # --- TÍNH NĂNG 2: DISPLAY MSG (CẬP NHẬT) ---
    def display_msg(self, sender, text, to_tab, is_voice=False, save=True):
        """Hiển thị tin nhắn lên màn hình"""
        
        # Xác định Tab cần hiện - Phải xử lý cả tin nhắn riêng
        if to_tab == "ALL": 
            target_view = "ALL"
        elif to_tab in self.joined_groups: 
            target_view = to_tab 
        elif to_tab == self.username:  # Tin riêng cho mình từ người khác
            target_view = sender
        else:  # Tin riêng từ mình gửi cho người khác
            target_view = to_tab

        # --- LƯU LOG (Chỉ lưu khi save=True) ---
        if save:
            self.save_log(target_view, sender, text, "voice" if is_voice else "text")

        # Âm thanh thông báo
        if sender != self.username and save: 
            try: winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except: pass

        # Lấy frame chat (Nếu chưa có sẽ tự tạo và LOAD HISTORY)
        frame = self._get_chat_frame(target_view)
        
        # Nếu đang xem tab này thì hiện ra
        if self.current_receiver == target_view: 
            frame.pack(fill="both", expand=True)

        # Vẽ giao diện tin nhắn
        msg_container = ctk.CTkFrame(frame, fg_color="transparent")
        msg_container.pack(fill="x", pady=2, padx=5)

        avatar_color = ACCENT_COLOR if sender == self.username else "#faa61a"
        ctk.CTkButton(msg_container, text=sender[:2].upper(), width=35, height=35, fg_color=avatar_color, 
                      corner_radius=20, hover=False, font=("Arial", 10, "bold")).grid(row=0, column=0, rowspan=2, padx=(0, 10), sticky="n")

        header_frame = ctk.CTkFrame(msg_container, fg_color="transparent")
        header_frame.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(header_frame, text=sender, font=("gg sans", 13, "bold"), text_color="white").pack(side="left")
        ctk.CTkLabel(header_frame, text=datetime.now().strftime(" %H:%M"), font=("gg sans", 10), text_color=TIMESTAMP_COLOR).pack(side="left")

        content_frame = ctk.CTkFrame(msg_container, fg_color="transparent")
        content_frame.grid(row=1, column=1, sticky="w")

        if is_voice:
            vb = ctk.CTkFrame(content_frame, fg_color=INPUT_BG, corner_radius=5)
            vb.pack(anchor="w", pady=2)
            ctk.CTkLabel(vb, text="🎤 Voice", text_color="white", font=("Arial", 12)).pack(side="left", padx=10)
            ctk.CTkButton(vb, text="▶", width=40, fg_color=GREEN_COLOR, height=25,
                          command=lambda: threading.Thread(target=self.audio.play_audio, args=(text,)).start()).pack(side="left", padx=5, pady=5)
        else:
            ctk.CTkLabel(content_frame, text=text, wraplength=450, justify="left", text_color="#dcddde").pack(anchor="w")
            
        # Tự động cuộn xuống dưới cùng
        self.after(10, lambda: self.chat_scroll._parent_canvas.yview_moveto(1.0))

    def _get_chat_frame(self, target):
        """Lấy frame chat, nếu chưa có thì tạo mới VÀ load lịch sử"""
        if target not in self.frames_store:
            frame = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
            self.frames_store[target] = frame
            
            # --- LOAD LỊCH SỬ CHỈ KHI LẦN ĐẦU TẠO FRAME ---
            self.load_history(target) 
            # -------------------------------------------
            
        return self.frames_store[target]

    # --- CÁC HÀM KHÁC (GIỮ NGUYÊN) ---
    def open_create_group_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Tạo nhóm mới")
        dialog.geometry("300x400")
        dialog.attributes("-topmost", True)
        ctk.CTkLabel(dialog, text="Tên nhóm:", font=("Arial", 12, "bold")).pack(pady=5)
        name_entry = ctk.CTkEntry(dialog, placeholder_text="Ví dụ: Team AOV")
        name_entry.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(dialog, text="Chọn thành viên:", font=("Arial", 12, "bold")).pack(pady=5)
        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.pack(fill="both", expand=True, padx=10, pady=5)
        selected_users = {}
        for user in self.online_users:
            if user != self.username:
                var = ctk.IntVar()
                chk = ctk.CTkCheckBox(scroll, text=user, variable=var)
                chk.pack(anchor="w", pady=2)
                selected_users[user] = var
        def create_action():
            group_name = name_entry.get().strip()
            if not group_name:
                messagebox.showwarning("Lỗi", "Vui lòng nhập tên nhóm!")
                return
            members = [u for u, v in selected_users.items() if v.get() == 1]
            members.append(self.username)
            members_str = ",".join(members)
            payload = f"GROUP_CREATE::{group_name}::{members_str}".encode('utf-8')
            self.network.send(payload)
            self.add_group_to_list(group_name)
            dialog.destroy()
        ctk.CTkButton(dialog, text="Tạo nhóm", command=create_action, fg_color=ACCENT_COLOR).pack(pady=10)

    def add_group_to_list(self, group_name):
        if group_name not in self.joined_groups:
            self.joined_groups.append(group_name)
            btn = self.create_channel_btn(f"🛡️ {group_name}", group_name)
            btn.pack(fill="x", pady=1)
            # Tự động tạo frame và load history cho nhóm mới
            self._get_chat_frame(group_name)

    def open_emoji_picker(self):
        emoji_window = ctk.CTkToplevel(self)
        emoji_window.title("Emoji")
        emoji_window.geometry("300x200")
        emoji_window.attributes("-topmost", True)
        emojis = ["😀", "😂", "🥰", "😎", "😭", "😡", "👍", "👎", "❤️", "🔥", "🎉", "👀", "💩", "👻", "🤖", "✅"]
        frame = ctk.CTkFrame(emoji_window)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        r, c = 0, 0
        for icon in emojis:
            ctk.CTkButton(frame, text=icon, width=40, height=40, fg_color="transparent", border_width=1,
                          command=lambda i=icon: self.insert_emoji(i)).grid(row=r, column=c, padx=5, pady=5)
            c += 1
            if c > 3: c = 0; r += 1

    def insert_emoji(self, icon):
        self.msg_entry.insert("end", icon)
        self.msg_entry.focus()

    def create_channel_btn(self, text, value):
        parent = self.dm_container 
        if value == "ALL": parent = self.channel_list 
        elif value in self.joined_groups: parent = self.group_container
        btn = ctk.CTkButton(parent, text=text, fg_color="#393c43" if value == "ALL" else "transparent", 
                            text_color="#dcddde", hover_color="#393c43", anchor="w", height=35,
                            command=lambda: self.switch_chat(value))
        return btn

    def switch_chat(self, target):
        self.current_receiver = target
        if target == "ALL": icon = "📢"
        elif target in self.joined_groups: icon = "🛡️"
        else: icon = "@"
        self.lbl_header_title.configure(text=f"{icon} {target}")
        self.msg_entry.configure(placeholder_text=f"Gửi đến {target}")
        self.btn_general.configure(fg_color="#393c43" if target == "ALL" else "transparent")
        for container in [self.group_container, self.dm_container]:
            for btn in container.winfo_children():
                is_active = btn.cget("text").endswith(f" {target}")
                btn.configure(fg_color="#393c43" if is_active else "transparent")
        for name, frame in self.frames_store.items():
            frame.pack_forget()
        # Đảm bảo load history tại thời điểm này
        frame = self._get_chat_frame(target)
        frame.pack(fill="both", expand=True)

    def send_text(self, event=None):
        text = self.msg_entry.get().strip()
        if not text: return
        payload = f"TEXTMSG::{self.username}::{self.current_receiver}::{text}".encode()
        self.network.send(payload)
        self.display_msg(self.username, text, self.current_receiver)
        self.msg_entry.delete(0, "end")

    def toggle_rec(self):
        if not self.audio.is_recording:
            self.btn_mic.configure(fg_color=RED_COLOR, text="■")
            self.avatar.configure(border_width=2, border_color=GREEN_COLOR)
            threading.Thread(target=self.audio.start_recording()).start()
        else:
            self.btn_mic.configure(fg_color="transparent", text="🎤")
            self.avatar.configure(border_width=0)
            data = self.audio.stop_recording()
            if data:
                payload = b"VOICEMSG::" + self.username.encode() + b"::" + self.current_receiver.encode() + b"::" + data
                self.network.send(payload)
                self.display_msg(self.username, data, self.current_receiver, is_voice=True)

    def send_file(self):
        path = filedialog.askopenfilename()
        if path:
            name = os.path.basename(path)
            with open(path, "rb") as f: data = f.read()
            payload = b"FILE::" + self.username.encode() + b"::" + self.current_receiver.encode() + b"::" + name.encode() + b"::" + data
            self.network.send(payload)
            self.display_msg(self.username, f"📎 File: {name}", self.current_receiver)

    def update_user_list(self, users_str):
        self.online_users = users_str.split(",") if users_str else []
        for widget in self.dm_container.winfo_children():
            widget.destroy()
        for u in self.online_users:
            if u and u != self.username:
                btn = self.create_channel_btn(f"👤 {u}", u)
                btn.pack(fill="x", pady=1)
                # Tự động tạo frame để chuẩn bị (sẽ load history khi switch_chat)
                # Không gọi _get_chat_frame() ở đây để tránh load history quá sớm
                if u not in self.frames_store:
                    frame = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
                    self.frames_store[u] = frame 

    def on_group_created(self, group_name):
        self.add_group_to_list(group_name)