import customtkinter as ctk

class CallWindow(ctk.CTkToplevel):
    def __init__(self, parent, name, is_group=False, end_callback=None, mute_callback=None, deafen_callback=None):
        super().__init__(parent)
        self.title("Cuộc gọi")
        self.geometry("300x400")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        
        self.end_callback = end_callback
        self.mute_callback = mute_callback
        self.deafen_callback = deafen_callback
        
        self.is_muted = False
        self.is_deafened = False

        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) # Avatar area
        self.grid_rowconfigure(1, weight=0) # Name
        self.grid_rowconfigure(2, weight=0) # Controls

        # Avatar
        # Placeholder for now, maybe use a big label with first letter
        # Group avatar color vs User avatar color
        bg_color = "#5865F2" if not is_group else "#faa61a"
        
        self.avatar_lbl = ctk.CTkLabel(self, text=name[:2].upper(), font=("Arial", 50, "bold"), 
                                       width=150, height=150, fg_color=bg_color, corner_radius=75)
        self.avatar_lbl.grid(row=0, column=0, pady=40)

        # Name
        self.name_lbl = ctk.CTkLabel(self, text=name, font=("gg sans", 20, "bold"))
        self.name_lbl.grid(row=1, column=0, pady=(0, 40))

        # Controls Frame
        self.controls = ctk.CTkFrame(self, fg_color="transparent")
        self.controls.grid(row=2, column=0, pady=20)

        # Buttons
        # Mic
        self.btn_mic = ctk.CTkButton(self.controls, text="🎤", width=50, height=50, corner_radius=25,
                                     fg_color="#3ba55c", command=self.toggle_mic)
        self.btn_mic.pack(side="left", padx=10)

        # End Call
        self.btn_end = ctk.CTkButton(self.controls, text="📞", width=60, height=60, corner_radius=30,
                                     fg_color="#ed4245", hover_color="#c03537", command=self.end_call_action)
        self.btn_end.pack(side="left", padx=10)

        # Deafen (Headphone)
        self.btn_deafen = ctk.CTkButton(self.controls, text="🎧", width=50, height=50, corner_radius=25,
                                        fg_color="#3ba55c", command=self.toggle_deafen)
        self.btn_deafen.pack(side="left", padx=10)

        self.protocol("WM_DELETE_WINDOW", self.end_call_action)

    def toggle_mic(self):
        self.is_muted = not self.is_muted
        if self.is_muted:
            self.btn_mic.configure(fg_color="#ed4245", text="🔇")
        else:
            self.btn_mic.configure(fg_color="#3ba55c", text="🎤")
            # If unmuting, we must undeafen if currently deafened
            if self.is_deafened:
                self.toggle_deafen()
        
        if self.mute_callback:
            self.mute_callback(self.is_muted)

    def toggle_deafen(self):
        self.is_deafened = not self.is_deafened
        if self.is_deafened:
            self.btn_deafen.configure(fg_color="#ed4245", text="🔇")
            # Deafen implies mute usually
            if not self.is_muted:
                self.toggle_mic() # Auto mute mic when deafen
        else:
            self.btn_deafen.configure(fg_color="#3ba55c", text="🎧")
        
        if self.deafen_callback:
            self.deafen_callback(self.is_deafened)

    def end_call_action(self):
        if self.end_callback:
            self.end_callback()
        self.destroy()
