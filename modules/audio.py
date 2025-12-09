# modules/audio.py
import sounddevice as sd
import numpy as np
import os # <--- Nhớ import thư viện này
from config import SAMPLE_RATE, CHANNELS, CHUNK

class AudioManager:
    def __init__(self):
        self.is_recording = False
        self.frames = []

    def start_recording(self):
        self.is_recording = True
        self.frames = []
        return self._record_loop

    def stop_recording(self):
        self.is_recording = False
        if not self.frames: return None
        # Ghép các frame lại
        raw_data = np.concatenate(self.frames, axis=0).astype(np.int16)
        if raw_data.ndim > 1 and raw_data.shape[1] == 1:
            raw_data = raw_data.reshape(-1)
        return raw_data.tobytes()

    def _record_loop(self):
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=np.int16, blocksize=CHUNK) as stream:
                while self.is_recording:
                    data, _ = stream.read(CHUNK)
                    self.frames.append(data)
        except Exception as e:
            print(f"Lỗi ghi âm: {e}")
            self.is_recording = False

    def play_audio(self, audio_data):
        """Hàm phát âm thanh thông minh: Xử lý cả Bytes và Đường dẫn file"""
        if not audio_data: return

        # --- FIX LỖI: Nếu đầu vào là String (đường dẫn file), hãy đọc file ra ---
        if isinstance(audio_data, str):
            if os.path.exists(audio_data):
                try:
                    with open(audio_data, "rb") as f:
                        audio_data = f.read() # Đọc file thành bytes
                except Exception as e:
                    print(f"Không đọc được file âm thanh: {e}")
                    return
            else:
                # Nếu là string nhưng không phải file (ví dụ tin nhắn rác), bỏ qua
                return 
        # -----------------------------------------------------------------------

        # Đến đây audio_data chắc chắn là bytes, tiến hành phát
        try:
            data = np.frombuffer(audio_data, dtype=np.int16)
            sd.play(data, samplerate=SAMPLE_RATE)
            sd.wait()
        except Exception as e:
            print(f"Lỗi phát loa: {e}")