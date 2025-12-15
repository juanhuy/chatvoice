# ui/chat_window.py
import customtkinter as ctk
import threading
from tkinter import filedialog, messagebox
import os
from datetime import datetime
import winsound
import json
from ui.call_window import CallWindow

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
        self.active_group_calls = [] # Danh sách các nhóm đang có cuộc gọi
        self.is_calling = False
        self.call_target = None
        self.call_window = None # Store the popup window

        # Tạo thư mục lưu log nếu chưa có
        if not os.path.exists("chat_logs"):
            os.makedirs("chat_logs")

        self.configure(fg_color=BG_PRIMARY)
        self.pack(fill="both", expand=True)

        # === LAYOUT CHÍNH ===
        self.grid_columnconfigure(0, weight=0, minsize=260)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0) # Sidebar phải (ẩn mặc định)
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

        # Container cho các nút bên phải
        self.header_btn_frame = ctk.CTkFrame(self.chat_header, fg_color="transparent")
        self.header_btn_frame.pack(side="right", padx=10, pady=10)

        # Nút Call
        self.btn_call = ctk.CTkButton(self.header_btn_frame, text="📞 Call", width=60, fg_color=GREEN_COLOR, 
                                      hover_color=HOVER_COLOR, command=self.start_call)
        self.btn_call.pack(side="left", padx=5)

        # Nút Info (Mới)
        self.btn_info = ctk.CTkButton(self.header_btn_frame, text="Info", width=50, fg_color="#2f3136", 
                                      hover_color=HOVER_COLOR, command=self.toggle_right_sidebar)
        self.btn_info.pack(side="left", padx=5)

        ctk.CTkFrame(self.main_area, height=1, fg_color="#202225").grid(row=0, column=0, sticky="ews")

        # === SIDEBAR PHẢI (INFO PANEL) ===
        self.right_sidebar = ctk.CTkFrame(self, fg_color=BG_SECONDARY, corner_radius=0, width=240)
        self.right_sidebar.grid_propagate(False)
        # Mặc định ẩn, sẽ grid() khi toggle

        # Nội dung Sidebar Phải
        self.info_header = ctk.CTkLabel(self.right_sidebar, text="THÔNG TIN NHÓM", 
                                        font=("gg sans", 14, "bold"), text_color="white")
        self.info_header.pack(pady=20)
        
        self.member_list_frame = ctk.CTkScrollableFrame(self.right_sidebar, fg_color="transparent")
        self.member_list_frame.pack(fill="both", expand=True, padx=10)
        
        self.add_member_frame = ctk.CTkFrame(self.right_sidebar, fg_color="transparent")
        self.add_member_frame.pack(fill="x", padx=10, pady=20)
        
        # Thay Entry bằng ComboBox để search/chọn thành viên
        self.cbo_add_member = ctk.CTkComboBox(self.add_member_frame, values=[], height=30,
                                              fg_color=INPUT_BG, border_color=INPUT_BG,
                                              button_color=INPUT_BG, button_hover_color=HOVER_COLOR,
                                              dropdown_fg_color=BG_SECONDARY, dropdown_text_color="white",
                                              text_color="white", state="readonly")
        self.cbo_add_member.set("Chọn thành viên...")
        self.cbo_add_member.pack(fill="x", pady=(0, 5))
        
        # Khi click vào combobox (hoặc focus), ta sẽ request list user mới nhất
        # Tuy nhiên CTkComboBox không có event <FocusIn> dễ dàng, ta sẽ request khi mở Info Panel
        
        ctk.CTkButton(self.add_member_frame, text="Thêm", fg_color=ACCENT_COLOR, height=30,
                      command=self.add_member_action).pack(fill="x")

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
        self.switch_chat("ALL")

    # --- CALL FEATURE ---
    def start_call(self):
        """Bắt đầu cuộc gọi"""
        target = self.current_receiver
        if target == "ALL":
            messagebox.showwarning("Call", "Không thể gọi cho kênh chung!")
            return
        
        # --- GROUP CALL LOGIC ---
        if target in self.joined_groups:
            # Nếu đang trong cuộc gọi nhóm này rồi thì không làm gì
            if self.is_calling and self.call_target == target:
                return
            
            # Bắt đầu cuộc gọi nhóm
            self.is_calling = True
            self.call_target = target
            self.btn_call.configure(text="📞 Leave", fg_color=RED_COLOR, command=self.leave_group_call)
            
            # Gửi lệnh Start (hoặc Join)
            if target in self.active_group_calls:
                payload = f"GROUP_CALL_JOIN::{self.username}::{target}".encode('utf-8')
            else:
                payload = f"GROUP_CALL_START::{self.username}::{target}".encode('utf-8')
                self.active_group_calls.append(target)
                
            self.network.send(payload)
            
            # Bắt đầu stream ngay
            self.start_streaming_audio(target)
            
            # --- OPEN CALL WINDOW ---
            self.open_call_window(target, is_group=True)
            # ------------------------
            
            print(f"Đã tham gia cuộc gọi nhóm {target}")
            return
        # ------------------------
        
        self.is_calling = True
        self.btn_call.configure(text="📞 End", fg_color=RED_COLOR, command=self.end_call)
        
        # Gửi yêu cầu gọi 1-1
        payload = f"CALL_REQUEST::{self.username}::{target}".encode('utf-8')
        self.network.send(payload)
        print(f"Đang gọi cho {target}...")

    def open_call_window(self, target_name, is_group=False):
        if self.call_window is not None:
            try: self.call_window.destroy()
            except: pass
            
        self.call_window = CallWindow(
            self, 
            name=target_name, 
            is_group=is_group,
            end_callback=self.leave_group_call if is_group else self.end_call,
            mute_callback=self.audio.set_mute,
            deafen_callback=self.audio.set_deafen
        )

    def leave_group_call(self):
        """Rời cuộc gọi nhóm"""
        target = self.call_target
        if not target: return

        self.is_calling = False
        self.call_target = None
        self.audio.stop_streaming()
        
        # Close popup
        if self.call_window:
            try: self.call_window.destroy()
            except: pass
            self.call_window = None
        
        # Reset nút Call nếu đang ở tab đó
        if self.current_receiver == target:
            # Nếu vẫn còn người trong call (logic này client chưa biết chính xác, nhưng cứ hiện Join Call nếu còn trong active list)
            if target in self.active_group_calls:
                self.btn_call.configure(text="📞 Join Call", fg_color=GREEN_COLOR, command=self.start_call)
            else:
                self.btn_call.configure(text="📞 Call", fg_color=GREEN_COLOR, command=self.start_call)
            
        # Gửi lệnh Leave
        payload = f"GROUP_CALL_LEAVE::{self.username}::{target}".encode('utf-8')
        self.network.send(payload)
        print(f"Đã rời cuộc gọi nhóm {target}")

    def handle_group_call_started(self, sender, group_name):
        """Xử lý khi có cuộc gọi nhóm bắt đầu"""
        if group_name not in self.joined_groups: return
        
        # Cập nhật danh sách active calls
        if group_name not in self.active_group_calls:
            self.active_group_calls.append(group_name)
            
        # Cập nhật UI nếu đang ở tab đó
        if self.current_receiver == group_name and not self.is_calling:
            self.btn_call.configure(text="📞 Join Call", fg_color=GREEN_COLOR, command=self.start_call)

        # Nếu mình là người gọi thì bỏ qua thông báo
        if sender == self.username: return

        # Nếu đang ở trong cuộc gọi khác thì bỏ qua
        if self.is_calling: return

        # Hiện thông báo mời tham gia
        ans = messagebox.askyesno("Cuộc gọi nhóm", f"{sender} đã bắt đầu cuộc gọi trong nhóm {group_name}. Tham gia ngay?")
        if ans:
            # Chuyển sang tab nhóm đó
            self.switch_chat(group_name)
            # Gọi hàm start_call (nó sẽ xử lý như join)
            self.start_call()

    def handle_group_call_ended(self, group_name):
        """Xử lý khi cuộc gọi nhóm kết thúc (không còn ai)"""
        if group_name in self.active_group_calls:
            self.active_group_calls.remove(group_name)
        
        # Nếu mình đang ở trong cuộc gọi đó (trường hợp hiếm, ví dụ lag mạng)
        if self.is_calling and self.call_target == group_name:
            self.leave_group_call()
            messagebox.showinfo("Call", f"Cuộc gọi nhóm {group_name} đã kết thúc.")

        # Cập nhật UI nếu đang ở tab đó
        if self.current_receiver == group_name:
            self.btn_call.configure(text="📞 Call", fg_color=GREEN_COLOR, command=self.start_call)

    def end_call(self, notify=True):
        """Kết thúc cuộc gọi 1-1"""
        target = self.call_target if self.call_target else self.current_receiver
        self.is_calling = False
        self.call_target = None
        self.audio.stop_streaming()
        
        # Close popup
        if self.call_window:
            try: self.call_window.destroy()
            except: pass
            self.call_window = None

        self.btn_call.configure(text="📞 Call", fg_color=GREEN_COLOR, command=self.start_call)
        
        if notify and target:
            # Gửi lệnh kết thúc
            payload = f"CALL_END::{self.username}::{target}".encode('utf-8')
            self.network.send(payload)
        print("Đã kết thúc cuộc gọi.")

    def handle_call_request(self, sender):
        """Xử lý khi có người gọi đến"""
        ans = messagebox.askyesno("Cuộc gọi đến", f"{sender} đang gọi cho bạn. Chấp nhận?")
        if ans:
            self.is_calling = True
            # Gửi chấp nhận
            payload = f"CALL_ACCEPT::{self.username}::{sender}".encode('utf-8')
            self.network.send(payload)
            
            # Bắt đầu stream
            self.start_streaming_audio(sender)
            
            # --- OPEN CALL WINDOW ---
            self.open_call_window(sender, is_group=False)
            # ------------------------

            # Đổi trạng thái nút Call (nếu đang ở tab người đó)
            if self.current_receiver == sender:
                self.btn_call.configure(text="📞 End", fg_color=RED_COLOR, command=self.end_call)
        else:
            # Gửi từ chối
            payload = f"CALL_REJECT::{self.username}::{sender}".encode('utf-8')
            self.network.send(payload)

    def handle_call_response(self, response_type, sender):
        """Xử lý phản hồi cuộc gọi (Accept/Reject/End)"""
        if response_type == "CALL_ACCEPT":
            messagebox.showinfo("Call", f"{sender} đã chấp nhận cuộc gọi!")
            self.start_streaming_audio(sender)
            
            # --- OPEN CALL WINDOW ---
            self.open_call_window(sender, is_group=False)
            # ------------------------
            
        elif response_type == "CALL_REJECT":
            self.end_call(notify=False) # Reset UI
            messagebox.showinfo("Call", f"{sender} đã từ chối cuộc gọi.")
            
        elif response_type == "CALL_END":
            self.end_call(notify=False) # Reset UI
            messagebox.showinfo("Call", f"Cuộc gọi với {sender} đã kết thúc.")

    def start_streaming_audio(self, target):
        """Bắt đầu gửi âm thanh"""
        self.call_target = target
        self.audio.start_streaming(self.send_audio_chunk)

    def send_audio_chunk(self, audio_bytes):
        """Gửi 1 chunk âm thanh đi"""
        header_part = f"AUDIO_STREAM::{self.username}::{self.call_target}::".encode('utf-8')
        payload = header_part + audio_bytes
        self.network.send(payload)

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
            # Force update để đảm bảo UI vẽ lại
            frame.update_idletasks()

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
        def scroll_to_bottom():
            self.chat_scroll.update_idletasks()
            self.chat_scroll._parent_canvas.yview_moveto(1.0)
            
        self.after(10, scroll_to_bottom)
        self.after(100, scroll_to_bottom) # Double check for slow rendering

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
        self.create_grp_dialog = ctk.CTkToplevel(self)
        self.create_grp_dialog.title("Tạo nhóm mới")
        self.create_grp_dialog.geometry("300x400")
        self.create_grp_dialog.attributes("-topmost", True)
        
        ctk.CTkLabel(self.create_grp_dialog, text="Tên nhóm:", font=("Arial", 12, "bold")).pack(pady=5)
        name_entry = ctk.CTkEntry(self.create_grp_dialog, placeholder_text="Ví dụ: Team AOV")
        name_entry.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(self.create_grp_dialog, text="Chọn thành viên:", font=("Arial", 12, "bold")).pack(pady=5)
        
        # Scroll frame để chứa checkbox
        self.create_grp_scroll = ctk.CTkScrollableFrame(self.create_grp_dialog)
        self.create_grp_scroll.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Dictionary lưu biến checkbox
        self.create_grp_vars = {} 

        # Gửi yêu cầu lấy danh sách user để hiển thị
        self.network.send(b"GET_ALL_USERS")
        
        def create_action():
            group_name = name_entry.get().strip()
            if not group_name:
                messagebox.showwarning("Lỗi", "Vui lòng nhập tên nhóm!")
                return
            
            # Lấy danh sách user được chọn
            members = [u for u, v in self.create_grp_vars.items() if v.get() == 1]
            members.append(self.username) # Thêm chính mình
            
            members_str = ",".join(members)
            payload = f"GROUP_CREATE::{group_name}::{members_str}".encode('utf-8')
            self.network.send(payload)
            self.add_group_to_list(group_name)
            self.create_grp_dialog.destroy()
            self.create_grp_dialog = None
            
        ctk.CTkButton(self.create_grp_dialog, text="Tạo nhóm", command=create_action, fg_color=ACCENT_COLOR).pack(pady=10)

    def update_create_group_list(self, users_str):
        """Cập nhật danh sách user trong dialog tạo nhóm"""
        if not hasattr(self, 'create_grp_dialog') or self.create_grp_dialog is None or not self.create_grp_dialog.winfo_exists():
            return

        # Xóa cũ
        for widget in self.create_grp_scroll.winfo_children():
            widget.destroy()
        self.create_grp_vars = {}

        all_users = users_str.split(",") if users_str else []
        
        for user in all_users:
            if user != self.username:
                var = ctk.IntVar()
                chk = ctk.CTkCheckBox(self.create_grp_scroll, text=user, variable=var)
                chk.pack(anchor="w", pady=2)
                self.create_grp_vars[user] = var

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
        
        # Reset các nút trên header
        self.btn_call.pack_forget()
        self.btn_info.pack_forget()

        # 1. Nút Call (Hiện cho tất cả trừ ALL)
        if target != "ALL":
            self.btn_call.pack(side="left", padx=5)
            
            if self.is_calling and self.call_target == target:
                self.btn_call.configure(text="📞 Leave" if target in self.joined_groups else "📞 End", 
                                        fg_color=RED_COLOR, 
                                        command=self.leave_group_call if target in self.joined_groups else self.end_call)
            elif target in self.active_group_calls:
                 self.btn_call.configure(text="📞 Join Call", fg_color=GREEN_COLOR, command=self.start_call)
            else:
                self.btn_call.configure(text="📞 Call", fg_color=GREEN_COLOR, command=self.start_call)

        # 2. Nút Info (Chỉ hiện cho Group)
        if target in self.joined_groups:
            self.btn_info.pack(side="left", padx=5)
            # Nếu sidebar đang mở thì cập nhật nội dung
            if self.right_sidebar.winfo_viewable():
                self.update_group_info(target)
        else:
            self.right_sidebar.grid_forget() # Ẩn sidebar nếu không phải group

        self.btn_general.configure(fg_color="#393c43" if target == "ALL" else "transparent")
        for container in [self.group_container, self.dm_container]:
            for btn in container.winfo_children():
                is_active = btn.cget("text").endswith(f" {target}")
                btn.configure(fg_color="#393c43" if is_active else "transparent")
        for name, frame in self.frames_store.items():
            frame.pack_forget()
            
        # Reset scroll về đầu trước khi đổi nội dung để tránh bị kẹt ở khoảng trắng phía dưới
        self.chat_scroll._parent_canvas.yview_moveto(0.0)
        
        # Đảm bảo load history tại thời điểm này
        frame = self._get_chat_frame(target)
        frame.pack(fill="both", expand=True)
        
        # Sau đó cuộn xuống dưới cùng (cần delay để UI cập nhật lại chiều cao)
        def scroll_to_bottom():
            self.chat_scroll.update_idletasks()
            self.chat_scroll._parent_canvas.yview_moveto(1.0)
            
        self.after(50, scroll_to_bottom)
        self.after(200, scroll_to_bottom)
        
        # Xóa nội dung cũ và Focus vào input field
        self.msg_entry.delete(0, "end")
        
        def force_focus():
            self.focus_set() # Clear focus from button
            self.msg_entry.focus_force() # Force focus to entry
            
        self.after(100, force_focus)

    def toggle_right_sidebar(self):
        if self.right_sidebar.winfo_viewable():
            self.right_sidebar.grid_forget()
        else:
            self.right_sidebar.grid(row=0, column=2, sticky="nsew")
            self.update_group_info(self.current_receiver)

    def update_group_info(self, group_name):
        # Gửi yêu cầu lấy danh sách thành viên
        self.network.send(f"GROUP_GET_MEMBERS::{group_name}".encode('utf-8'))
        # Gửi yêu cầu lấy danh sách TẤT CẢ user để nạp vào combobox
        self.network.send(b"GET_ALL_USERS")

    def update_all_users_combo(self, users_str):
        """Cập nhật danh sách user vào combobox thêm thành viên VÀ dialog tạo nhóm"""
        
        # 1. Cập nhật Dialog Tạo Nhóm (nếu đang mở)
        self.update_create_group_list(users_str)

        # 2. Cập nhật ComboBox Add Member (như cũ)
        all_users = users_str.split(",") if users_str else []
        
        # Lấy danh sách thành viên hiện tại của nhóm (để loại trừ)
        current_members = getattr(self, "current_group_members", [])
        
        available_users = [u for u in all_users if u not in current_members]
        
        if available_users:
            self.cbo_add_member.configure(values=available_users)
            self.cbo_add_member.set(available_users[0])
        else:
            self.cbo_add_member.configure(values=["(Trống)"])
            self.cbo_add_member.set("(Trống)")

    def display_group_members(self, group_name, members_str, admin_name=""):
        if self.current_receiver != group_name: return
        
        # Lưu lại danh sách thành viên để dùng cho việc lọc combobox
        members = members_str.split(",")
        self.current_group_members = members
        
        # Xóa cũ
        for widget in self.member_list_frame.winfo_children():
            widget.destroy()
            
        ctk.CTkLabel(self.member_list_frame, text=f"THÀNH VIÊN - {len(members)}", 
                     font=("gg sans", 11, "bold"), text_color=TIMESTAMP_COLOR, anchor="w").pack(fill="x", pady=(0, 10))
        
        is_admin = (self.username == admin_name)

        # --- HIỆN/ẨN KHUNG THÊM THÀNH VIÊN ---
        if is_admin:
            self.add_member_frame.pack(fill="x", padx=10, pady=20)
        else:
            self.add_member_frame.pack_forget()
        # -------------------------------------

        for mem in members:
            row = ctk.CTkFrame(self.member_list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            # Avatar giả
            ctk.CTkButton(row, text=mem[:2].upper(), width=30, height=30, fg_color=GREEN_COLOR, 
                          corner_radius=15, hover=False, font=("Arial", 10, "bold")).pack(side="left", padx=(0, 10))
            
            # Tên + (Admin) nếu là admin
            display_name = mem
            if mem == admin_name:
                display_name += " 👑"
            
            ctk.CTkLabel(row, text=display_name, font=("gg sans", 13), text_color="white").pack(side="left")

            # Nút xóa (chỉ hiện nếu mình là admin và không phải xóa chính mình)
            if is_admin and mem != self.username:
                ctk.CTkButton(row, text="❌", width=25, height=25, fg_color="transparent", hover_color=RED_COLOR,
                              command=lambda m=mem: self.remove_member_action(m)).pack(side="right")
        
        # --- NÚT GIẢI TÁN NHÓM (CHO ADMIN) ---
        if is_admin:
            ctk.CTkFrame(self.member_list_frame, height=1, fg_color="#202225").pack(fill="x", pady=10)
            ctk.CTkButton(self.member_list_frame, text="⚠️ Giải tán nhóm", fg_color="transparent", 
                          border_width=1, border_color=RED_COLOR, text_color=RED_COLOR, hover_color=RED_COLOR,
                          command=self.delete_group_action).pack(fill="x", pady=5)
        # -------------------------------------

        # --- REFRESH COMBOBOX ---
        # Khi danh sách thành viên thay đổi, ta cần cập nhật lại dropdown để loại bỏ người vừa thêm
        self.network.send(b"GET_ALL_USERS")
        # ------------------------

    def delete_group_action(self):
        ans = messagebox.askyesno("Cảnh báo", f"Bạn có chắc muốn giải tán nhóm {self.current_receiver}?\nHành động này không thể hoàn tác!")
        if ans:
            payload = f"GROUP_DELETE::{self.current_receiver}".encode('utf-8')
            self.network.send(payload)

    def remove_member_action(self, member_name):
        ans = messagebox.askyesno("Xóa thành viên", f"Bạn có chắc muốn xóa {member_name} khỏi nhóm?")
        if ans:
            payload = f"GROUP_REMOVE_MEMBER::{self.current_receiver}::{member_name}".encode('utf-8')
            self.network.send(payload)

    def add_member_action(self):
        new_mem = self.cbo_add_member.get()
        if not new_mem or new_mem == "(Trống)" or new_mem == "Chọn thành viên...": return
        
        # Gửi yêu cầu thêm thành viên
        payload = f"GROUP_ADD_MEMBER::{self.current_receiver}::{new_mem}".encode('utf-8')
        self.network.send(payload)
        self.cbo_add_member.set("Chọn thành viên...")

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

    def on_group_created(self, group_name):
        self.add_group_to_list(group_name)

    def on_group_removed(self, group_name):
        if group_name in self.joined_groups:
            self.joined_groups.remove(group_name)
            
            # Remove button from UI
            for btn in self.group_container.winfo_children():
                if btn.cget("text") == f"🛡️ {group_name}":
                    btn.destroy()
                    break
            
            # If currently viewing this group, switch to ALL
            if self.current_receiver == group_name:
                self.switch_chat("ALL")
                messagebox.showinfo("Thông báo", f"Bạn đã bị xóa khỏi nhóm {group_name}.")

    def on_group_deleted(self, group_name):
        if group_name in self.joined_groups:
            self.joined_groups.remove(group_name)
            
            # Remove button from UI
            for btn in self.group_container.winfo_children():
                if btn.cget("text") == f"🛡️ {group_name}":
                    btn.destroy()
                    break
            
            # If currently viewing this group, switch to ALL
            if self.current_receiver == group_name:
                self.switch_chat("ALL")
                messagebox.showwarning("Thông báo", f"Nhóm {group_name} đã bị giải tán bởi Admin.")