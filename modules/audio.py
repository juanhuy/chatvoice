# modules/audio.py
import sounddevice as sd
import numpy as np
import os 
import queue
import threading
from config import SAMPLE_RATE, CHANNELS, CHUNK, SILENCE_THRESHOLD

class AudioManager:
    def __init__(self):
        self.is_recording = False
        self.frames = []
        self.audio_queue = queue.Queue()
        self.is_playing_stream = False
        self.play_thread = None
        
        # --- MUTE / DEAFEN STATE ---
        self.is_muted = False
        self.is_deafened = False

    def set_mute(self, muted):
        self.is_muted = muted

    def set_deafen(self, deafened):
        self.is_deafened = deafened
        # Deafen usually implies Mute too (can't speak if you can't hear?)
        # But we will handle logic in UI or here. 
        # For now, just flag it.

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
        
        # --- MUTE CHECK ---
        if self.is_muted or self.is_deafened:
            return # Don't send audio if muted or deafened
        # ------------------

        if self.is_streaming and self.stream_callback:
            # --- VAD: Silence Suppression ---
            # Tính biên độ trung bình (RMS) của chunk
            # indata là numpy array int16
            volume = np.linalg.norm(indata) * 10
            
            # Chỉ gửi nếu âm lượng lớn hơn ngưỡng
            if volume > SILENCE_THRESHOLD:
                self.stream_callback(indata.tobytes())

    def stop_streaming(self):
        """Dừng stream mic"""
        self.is_streaming = False
        self.is_playing_stream = False # Stop playback thread
        
        # Clear queue to prevent old audio from playing next time
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()

        if hasattr(self, 'input_stream'):
            self.input_stream.stop()
            self.input_stream.close()
        
        if hasattr(self, 'output_stream'):
            self.output_stream.stop()
            self.output_stream.close()
            del self.output_stream

    def play_stream_chunk(self, data_bytes):
        """Thêm chunk vào hàng đợi để phát"""
        
        # --- DEAFEN CHECK ---
        if self.is_deafened:
            return # Don't play audio if deafened
        # --------------------

        # --- LATENCY CONTROL: Drop old packets if queue is too full ---
        if self.audio_queue.qsize() > 10: # Nếu hàng đợi > 10 chunks (~200ms)
            try:
                # Xả bớt 5 chunk cũ nhất để bắt kịp thời gian thực
                for _ in range(5): self.audio_queue.get_nowait()
            except queue.Empty: pass
        # --------------------------------------------------------------

        self.audio_queue.put(data_bytes)
        
        if not self.is_playing_stream:
            self.is_playing_stream = True
            self.play_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self.play_thread.start()

    def _playback_loop(self):
        """Luồng riêng để phát âm thanh từ hàng đợi"""
        if not hasattr(self, 'output_stream'):
            self.output_stream = sd.OutputStream(
                samplerate=SAMPLE_RATE, 
                channels=CHANNELS, 
                dtype=np.int16, 
                blocksize=CHUNK
            )
            self.output_stream.start()

        while self.is_playing_stream:
            try:
                data_bytes = self.audio_queue.get(timeout=1) # Chờ 1s nếu không có data
                data_np = np.frombuffer(data_bytes, dtype=np.int16)
                self.output_stream.write(data_np)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Lỗi playback loop: {e}")
                break
