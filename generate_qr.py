import os
import qrcode

YOUR_URL = "https://restaurant-ordering-q8te.onrender.com"
RESTAURANT_SLUG = "nirvana"  # matches the slug created in Stage 1
NUM_TABLES = 10

# Create the folder if it doesn't exist already
if not os.path.exists(RESTAURANT_SLUG):
    os.makedirs(RESTAURANT_SLUG)
    print(f"Created folder: '{RESTAURANT_SLUG}'")

for i in range(1, NUM_TABLES + 1):
    url = f"{YOUR_URL}/r/{RESTAURANT_SLUG}/table/{i}"
    img = qrcode.make(url)
    
    # Construct the file path inside the folder
    file_path = os.path.join(RESTAURANT_SLUG, f"{RESTAURANT_SLUG}_qr_table_{i}.png")
    
    img.save(file_path)
    print(f"Generated QR for table {i} -> Saved to {file_path}")
