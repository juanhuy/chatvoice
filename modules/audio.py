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

    # --- STREAMING METHODS FOR CALL ---
    def start_streaming(self, callback):
        """Bắt đầu stream mic cho cuộc gọi"""
        self.stream_callback = callback
        self.is_streaming = True
        self.input_stream = sd.InputStream(
            samplerate=SAMPLE_RATE, 
            channels=CHANNELS, 
            dtype=np.int16, 
            blocksize=CHUNK, 
            callback=self._stream_input_callback
        )
        self.input_stream.start()

    def _stream_input_callback(self, indata, frames, time, status):
        if status: print(f"Stream status: {status}")
        if self.is_streaming and self.stream_callback:
            self.stream_callback(indata.tobytes())

    def stop_streaming(self):
        """Dừng stream mic"""
        self.is_streaming = False
        if hasattr(self, 'input_stream'):
            self.input_stream.stop()
            self.input_stream.close()
        if hasattr(self, 'output_stream'):
            self.output_stream.stop()
            self.output_stream.close()
            del self.output_stream

    def play_stream_chunk(self, data_bytes):
        """Phát 1 chunk âm thanh nhận được"""
        if not hasattr(self, 'output_stream'):
            self.output_stream = sd.OutputStream(
                samplerate=SAMPLE_RATE, 
                channels=CHANNELS, 
                dtype=np.int16, 
                blocksize=CHUNK
            )
            self.output_stream.start()
        
        try:
            data_np = np.frombuffer(data_bytes, dtype=np.int16)
            self.output_stream.write(data_np)
        except Exception as e:
            print(f"Lỗi phát stream: {e}")
