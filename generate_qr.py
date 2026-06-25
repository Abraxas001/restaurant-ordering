# generate_qr.py
import qrcode

YOUR_IP = "192.168.1.20"  # replace with your actual IP (run ipconfig)
NUM_TABLES = 10

for i in range(1, NUM_TABLES + 1):
    url = f"http://192.168.1.8:8000/table/{i}"
    img = qrcode.make(url)
    img.save(f"qr_table_{i}.png")
    print(f"Generated QR for table {i}")
