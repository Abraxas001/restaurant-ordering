import qrcode

YOUR_URL = "https://restaurant-ordering-q8te.onrender.com"
RESTAURANT_SLUG = "my-restaurant"  # matches the slug created in Stage 1
NUM_TABLES = 10

for i in range(1, NUM_TABLES + 1):
    url = f"{YOUR_URL}/r/{RESTAURANT_SLUG}/table/{i}"
    img = qrcode.make(url)
    img.save(f"qr_table_{i}.png")
    print(f"Generated QR for table {i}")
