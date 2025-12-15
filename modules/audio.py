# modules/audio.py
import sounddevice as sd
import numpy as np
import os 
import queue
import threading
import time
from config import SAMPLE_RATE, CHANNELS, CHUNK, SILENCE_THRESHOLD

class AudioManager:
    def __init__(self):
        self.is_recording = False
        self.frames = []
        
        # --- MIXING QUEUES ---
        # Thay vì 1 queue, ta dùng dict {user_id: Queue}
        self.user_queues = {} 
        self.is_playing_stream = False
        self.play_thread = None
        
        # --- MUTE / DEAFEN STATE ---
        self.is_muted = False
        self.is_deafened = False

    def set_mute(self, muted):
        self.is_muted = muted

    def set_deafen(self, deafened):
        self.is_deafened = deafened

    def start_recording(self):
        # Đảm bảo không conflict với stream
        if hasattr(self, 'input_stream') and self.input_stream.active:
            self.stop_streaming()
            
        self.is_recording = True
        self.frames = []
        return self._record_loop

    def stop_recording(self):
        self.is_recording = False
        if not self.frames: return None
        # Ghép các frame lại
        try:
            raw_data = np.concatenate(self.frames, axis=0).astype(np.int16)
            if raw_data.ndim > 1 and raw_data.shape[1] == 1:
                raw_data = raw_data.reshape(-1)
            return raw_data.tobytes()
        except:
            return None

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

        if isinstance(audio_data, str):
            if os.path.exists(audio_data):
                try:
                    with open(audio_data, "rb") as f:
                        audio_data = f.read()
                except Exception as e:
                    print(f"Không đọc được file âm thanh: {e}")
                    return
            else:
                return 

        try:
            data = np.frombuffer(audio_data, dtype=np.int16)
            sd.play(data, samplerate=SAMPLE_RATE)
            sd.wait()
        except Exception as e:
            print(f"Lỗi phát loa: {e}")

    # --- STREAMING METHODS FOR CALL ---
    def start_streaming(self, callback):
        """Bắt đầu stream mic cho cuộc gọi"""
        # Đảm bảo tắt recording voice note nếu đang chạy
        if self.is_recording:
            self.is_recording = False
            
        self.stream_callback = callback
        self.is_streaming = True
        
        try:
            self.input_stream = sd.InputStream(
                samplerate=SAMPLE_RATE, 
                channels=CHANNELS, 
                dtype=np.int16, 
                blocksize=CHUNK, 
                callback=self._stream_input_callback
            )
            self.input_stream.start()
        except Exception as e:
            print(f"Lỗi start stream: {e}")

    def _stream_input_callback(self, indata, frames, time, status):
        if status: print(f"Stream status: {status}")
        
        if self.is_muted or self.is_deafened:
            return 

        if self.is_streaming and self.stream_callback:
            volume = np.linalg.norm(indata) * 10
            if volume > SILENCE_THRESHOLD:
                self.stream_callback(indata.tobytes())

    def stop_streaming(self):
        """Dừng stream mic"""
        self.is_streaming = False
        self.is_playing_stream = False 
        
        # Clear all queues
        self.user_queues.clear()

        if hasattr(self, 'input_stream'):
            try:
                self.input_stream.stop()
                self.input_stream.close()
            except: pass
        
        if hasattr(self, 'output_stream'):
            try:
                self.output_stream.stop()
                self.output_stream.close()
                del self.output_stream
            except: pass

    def play_stream_chunk(self, data_bytes, sender_id):
        """Thêm chunk vào hàng đợi của user tương ứng"""
        if self.is_deafened: return

        if sender_id not in self.user_queues:
            self.user_queues[sender_id] = queue.Queue()
            
        q = self.user_queues[sender_id]
        
        # Latency control per user
        if q.qsize() > 5: # Giảm buffer xuống thấp hơn để realtime hơn
            try:
                for _ in range(2): q.get_nowait()
            except queue.Empty: pass

        q.put(data_bytes)
        
        if not self.is_playing_stream:
            self.is_playing_stream = True
            self.play_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self.play_thread.start()

    def _playback_loop(self):
        """Luồng MIXING và phát âm thanh"""
        if not hasattr(self, 'output_stream'):
            try:
                self.output_stream = sd.OutputStream(
                    samplerate=SAMPLE_RATE, 
                    channels=CHANNELS, 
                    dtype=np.int16, 
                    blocksize=CHUNK
                )
                self.output_stream.start()
            except Exception as e:
                print(f"Lỗi init output stream: {e}")
                return

        while self.is_playing_stream:
            try:
                # 1. Lấy danh sách các user đang có audio trong queue
                active_users = [uid for uid, q in self.user_queues.items() if not q.empty()]
                
                if not active_users:
                    # Nếu không có ai nói, ngủ 1 chút để đỡ tốn CPU (nhưng phải ngắn hơn thời gian 1 chunk)
                    # 1 chunk 1024 mẫu @ 44100Hz ~ 23ms. Ngủ 10ms là an toàn.
                    time.sleep(0.01)
                    continue

                # 2. Lấy 1 chunk từ mỗi user và MIX lại
                mixed_audio = np.zeros(CHUNK * CHANNELS, dtype=np.int32) # Dùng int32 để cộng không bị tràn
                
                for uid in active_users:
                    try:
                        data_bytes = self.user_queues[uid].get_nowait()
                        data_np = np.frombuffer(data_bytes, dtype=np.int16).astype(np.int32)
                        
                        # Nếu độ dài không khớp (hiếm), resize
                        if len(data_np) != len(mixed_audio):
                            continue
                            
                        mixed_audio += data_np
                    except queue.Empty:
                        pass
                
                # 3. Clip về int16 để phát
                mixed_audio = np.clip(mixed_audio, -32768, 32767).astype(np.int16)
                
                # 4. Write ra loa
                self.output_stream.write(mixed_audio)
                
            except Exception as e:
                print(f"Lỗi playback loop: {e}")
                break
