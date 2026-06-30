from fastapi import FastAPI, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, engine, SessionLocal
from models import Base, MenuItem, Order, OrderItem, Restaurant
from datetime import date, datetime
import os
from fastapi.responses import RedirectResponse
from fastapi import Form, Cookie
from typing import Optional
import hashlib
import secrets

print("DATABASE URL:", os.environ.get("TURSO_URL", "NOT FOUND"))

app = FastAPI()
Base.metadata.create_all(bind=engine)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Migrate: add missing columns if they don't exist
from sqlalchemy import text

Base.metadata.create_all(bind=engine)
def run_migrations():
    db = SessionLocal()
    try:
        # Step 1: Add restaurant_id column to menu_items if missing
        try:
            db.execute(text("ALTER TABLE menu_items ADD COLUMN restaurant_id INTEGER"))
            db.commit()
            print("Added restaurant_id to menu_items")
        except Exception:
            db.rollback()

        # Step 2: Add restaurant_id column to orders if missing
        try:
            db.execute(text("ALTER TABLE orders ADD COLUMN restaurant_id INTEGER"))
            db.commit()
            print("Added restaurant_id to orders")
        except Exception:
            db.rollback()

        # Step 3: Create a default restaurant for existing data (only if none exists)
        existing_restaurant = db.query(Restaurant).first()
        if not existing_restaurant:
            default_restaurant = Restaurant(
                name="NIRVANA",
                slug="nirvana",
                username="cafe_admin",
                password=ADMIN_PASSWORD  # reuse your existing admin password
            )
            db.add(default_restaurant)
            db.commit()
            db.refresh(default_restaurant)
            print(f"Created default restaurant with id {default_restaurant.id}")

            # Step 4: Backfill existing menu items and orders with this restaurant_id
            db.execute(text(f"UPDATE menu_items SET restaurant_id = {default_restaurant.id} WHERE restaurant_id IS NULL"))
            db.execute(text(f"UPDATE orders SET restaurant_id = {default_restaurant.id} WHERE restaurant_id IS NULL"))
            db.commit()
            print("Backfilled existing data with default restaurant_id")

    finally:
        db.close()

run_migrations()

# Auto-seed menu items if table is empty
def seed_menu():
    db = SessionLocal()
    try:
        count = db.query(MenuItem).count()
        if count == 0:
            items = [
                MenuItem(name="Burger", category="Main Course", price=250),
                MenuItem(name="Pizza", category="Main Course", price=450),
                MenuItem(name="Cold Coffee", category="Beverage", price=180),
                MenuItem(name="French Fries", category="Snacks", price=150),
            ]
            for item in items:
                db.add(item)
            db.commit()
            print("Menu seeded successfully!")
    finally:
        db.close()

seed_menu()
templates = Jinja2Templates(directory="templates")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Store active sessions in memory
active_sessions = set()

def create_session():
    token = secrets.token_hex(32)
    active_sessions.add(token)
    return token

def is_valid_session(token: str) -> bool:
    return token in active_sessions

@app.get("/")
def read_root():
    return {"message": "Restaurant API is up and running!"}

@app.get("/menu")
def get_menu(db: Session = Depends(get_db)):
    items = db.query(MenuItem).all()
    return items

@app.get("/r/{slug}/table/{table_number}")
def table_landing(slug: str, table_number: int, request: Request, db: Session = Depends(get_db)):
    restaurant = db.query(Restaurant).filter(Restaurant.slug == slug).first()
    if not restaurant:
        return {"error": "Restaurant not found"}

    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={
            "table_number": table_number,
            "slug": slug,
            "restaurant_name": restaurant.name
        }
    )

@app.get("/r/{slug}/menu/{table_number}")
def table_menu(
    slug: str,
    table_number: int,
    name: str,
    phone: str,
    request: Request,
    db: Session = Depends(get_db)
):
    restaurant = db.query(Restaurant).filter(Restaurant.slug == slug).first()
    if not restaurant:
        return {"error": "Restaurant not found"}

    items = db.query(MenuItem).filter(MenuItem.restaurant_id == restaurant.id).all()

    return templates.TemplateResponse(
        request=request,
        name="menu.html",
        context={
            "items": items,
            "table_number": table_number,
            "customer_name": name,
            "customer_phone": phone,
            "slug": slug,
            "restaurant_name": restaurant.name
        }
    )

@app.post("/order")
def place_order(
    table_number: int,
    item_ids: str,
    quantities: str,
    customer_name: str = "",
    customer_phone: str = "",
    db: Session = Depends(get_db)
):
    order = Order(
        table_number=table_number,
        status="New",
        customer_name=customer_name,
        customer_phone=customer_phone
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    ids = item_ids.split(",")
    qtys = quantities.split(",")

    for item_id, qty in zip(ids, qtys):
        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=int(item_id),
            quantity=int(qty)
        )
        db.add(order_item)

    db.commit()
    return {"message": "Order placed!", "order_id": order.id}

@app.get("/orders")
def get_orders(db: Session = Depends(get_db)):
    orders = db.query(Order).all()
    return orders

@app.get("/admin")
def admin_dashboard(
    request: Request,
    filter_date: str = None,
    admin_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    # Check authentication
    if not admin_token or not is_valid_session(admin_token):
        return RedirectResponse(url="/admin/login", status_code=302)

    if not filter_date:
        filter_date = date.today().isoformat()

    selected_date = datetime.strptime(filter_date, "%Y-%m-%d").date()

    all_orders_dates = db.query(Order.created_at).all()
    unique_dates = sorted(set(o.created_at.date() for o in all_orders_dates if o.created_at), reverse=True)

    if date.today() not in unique_dates:
        unique_dates.insert(0, date.today())

    orders = db.query(Order).filter(
        Order.created_at >= datetime.combine(selected_date, datetime.min.time()),
        Order.created_at <= datetime.combine(selected_date, datetime.max.time())
    ).order_by(Order.created_at.desc()).all()

    order_details = []
    for order in orders:
        items = db.query(OrderItem, MenuItem).join(
            MenuItem, OrderItem.menu_item_id == MenuItem.id
        ).filter(OrderItem.order_id == order.id).all()

        order_details.append({
            "order": order,
            "time": order.created_at.strftime('%I:%M %p') if order.created_at else "N/A",
            "order_items": items
        })

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "order_details": order_details,
            "unique_dates": unique_dates,
            "selected_date": selected_date.isoformat()
        }
    )

@app.post("/order/{order_id}/status")
def update_order_status(
    order_id: int,
    status: str,
    admin_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    if not admin_token or not is_valid_session(admin_token):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"error": "Order not found"}
    order.status = status
    db.commit()
    return {"message": "Status updated", "order_id": order_id, "status": status}

@app.post("/admin/menu/add")
def add_menu_item(
    name: str,
    category: str,
    price: float,
    admin_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    if not admin_token or not is_valid_session(admin_token):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    item = MenuItem(name=name, category=category, price=price)
    db.add(item)
    db.commit()
    return {"message": "Item added"}

@app.post("/admin/menu/edit/{item_id}")
def edit_menu_item(
    item_id: int,
    name: str,
    category: str,
    price: float,
    admin_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    if not admin_token or not is_valid_session(admin_token):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        return {"error": "Item not found"}
    item.name = name
    item.category = category
    item.price = price
    db.commit()
    return {"message": "Item updated"}

@app.get("/admin/menu")
def get_menu_items(db: Session = Depends(get_db)):
    items = db.query(MenuItem).all()
    return items

@app.get("/admin/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None}
    )

@app.post("/admin/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        token = create_session()
        response = RedirectResponse(url="/admin", status_code=302)
        response.set_cookie(key="admin_token", value=token, httponly=True)
        return response
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Invalid username or password"}
    )

@app.get("/admin/logout")
def logout(admin_token: Optional[str] = Cookie(None)):
    if admin_token in active_sessions:
        active_sessions.discard(admin_token)
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie("admin_token")
    return response
