# config.py

# Cấu hình Mạng
# HOST = '26.158.211.81'   # Server lắng nghe tất cả IP
HOST = '192.168.88.183'   # Server lắng nghe tất cả IP
PORT = 12345       # Cổng kết nối
HEADER_SIZE = 10   # Độ dài header gói tin

# Cấu hình Âm thanh (Chỉ Client dùng, nhưng để đây cho tiện)
CHUNK = 1024
SAMPLE_RATE = 44100
CHANNELS = 1
SILENCE_THRESHOLD = 500 # Ngưỡng lọc âm (0-32767), dưới mức này coi là im lặng
CHANNELS = 1