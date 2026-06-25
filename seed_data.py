from database import SessionLocal
from models import MenuItem

db = SessionLocal()

items = [
    MenuItem(name="Burger", category="Main Course", price=250),
    MenuItem(name="Pizza", category="Main Course", price=450),
    MenuItem(name="Cold Coffee", category="Beverage", price=180),
    MenuItem(name="French Fries", category="Snacks", price=150),
]

for item in items:
    db.add(item)

db.commit()
db.close()

print("Menu items added successfully!")