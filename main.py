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
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

app = FastAPI()
Base.metadata.create_all(bind=engine)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

SUPERADMIN_USERNAME = os.environ.get("SUPERADMIN_USERNAME", "superadmin")
SUPERADMIN_PASSWORD = os.environ.get("SUPERADMIN_PASSWORD", "super123")

superadmin_sessions = set()

def create_superadmin_session():
    token = secrets.token_hex(32)
    superadmin_sessions.add(token)
    return token

def is_valid_superadmin_session(token: str) -> bool:
    return token in superadmin_sessions

@app.get("/superadmin/login")
def superadmin_login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="superadmin_login.html",
        context={"error": None}
    )

@app.post("/superadmin/login")
def superadmin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    if username == SUPERADMIN_USERNAME and verify_password(password, SUPERADMIN_PASSWORD):
        token = create_superadmin_session()
        response = RedirectResponse(url="/superadmin", status_code=302)
        response.set_cookie(
            key="superadmin_token",
            value=token,
            httponly=True,
            path="/superadmin"
        )
        return response
    return templates.TemplateResponse(
        request=request,
        name="superadmin_login.html",
        context={"error": "Invalid credentials"}
    )

@app.get("/superadmin/logout")
def superadmin_logout(superadmin_token: Optional[str] = Cookie(None)):
    if superadmin_token in superadmin_sessions:
        superadmin_sessions.discard(superadmin_token)
    response = RedirectResponse(url="/superadmin/login", status_code=302)
    response.delete_cookie("superadmin_token", path="/superadmin")
    return response

@app.get("/superadmin")
def superadmin_dashboard(
    request: Request,
    superadmin_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    if not superadmin_token or not is_valid_superadmin_session(superadmin_token):
        return RedirectResponse(url="/superadmin/login", status_code=302)

    restaurants = db.query(Restaurant).order_by(Restaurant.created_at.desc()).all()

    restaurant_stats = []
    for r in restaurants:
        total_orders = db.query(Order).filter(Order.restaurant_id == r.id).count()
        today_orders = db.query(Order).filter(
            Order.restaurant_id == r.id,
            Order.created_at >= datetime.combine(date.today(), datetime.min.time())
        ).count()
        menu_count = db.query(MenuItem).filter(MenuItem.restaurant_id == r.id).count()

        restaurant_stats.append({
            "restaurant": r,
            "total_orders": total_orders,
            "today_orders": today_orders,
            "menu_count": menu_count
        })

    return templates.TemplateResponse(
        request=request,
        name="superadmin.html",
        context={"restaurant_stats": restaurant_stats}
    )

@app.post("/superadmin/add-restaurant")
def add_restaurant(
    name: str = Form(...),
    slug: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    superadmin_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    if not superadmin_token or not is_valid_superadmin_session(superadmin_token):
        return RedirectResponse(url="/superadmin/login", status_code=302)

    existing = db.query(Restaurant).filter(Restaurant.slug == slug).first()
    if existing:
        return RedirectResponse(url="/superadmin?error=slug_exists", status_code=302)

    restaurant = Restaurant(
        name=name,
        slug=slug,
        username=username,
        password=hash_password(password)  # hash before storing
    )
    db.add(restaurant)
    db.commit()

    return RedirectResponse(url="/superadmin", status_code=302)

@app.get("/superadmin/migrate-passwords")
def migrate_passwords(
    superadmin_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    if not superadmin_token or not is_valid_superadmin_session(superadmin_token):
        return {"error": "Unauthorized"}

    restaurants = db.query(Restaurant).all()
    migrated = []

    for r in restaurants:
        # Only hash if not already hashed (bcrypt hashes start with $2b$)
        if not r.password.startswith("$2b$"):
            r.password = hash_password(r.password)
            migrated.append(r.name)

    db.commit()
    return {"message": "Passwords migrated", "migrated": migrated}

@app.get("/generate-hash")
def generate_hash(password: str):
    return {"hash": hash_password(password)}

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

        try:
            db.execute(text("ALTER TABLE orders ADD COLUMN restaurant_order_number INTEGER"))
            db.commit()
            print("Added restaurant_order_number to orders")
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

active_sessions = {}  # token -> restaurant_id

def create_session(restaurant_id: int):
    token = secrets.token_hex(32)
    active_sessions[token] = restaurant_id
    return token

def get_session_restaurant_id(token: str):
    return active_sessions.get(token)

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

@app.post("/r/{slug}/order")
def place_order(
    slug: str,
    table_number: int,
    item_ids: str,
    quantities: str,
    customer_name: str = "",
    customer_phone: str = "",
    db: Session = Depends(get_db)
):
    restaurant = db.query(Restaurant).filter(Restaurant.slug == slug).first()
    if not restaurant:
        return {"error": "Restaurant not found"}

    # Calculate next order number for this restaurant
    last_order = db.query(Order).filter(
        Order.restaurant_id == restaurant.id
    ).order_by(Order.restaurant_order_number.desc()).first()

    next_order_number = (last_order.restaurant_order_number + 1) if last_order and last_order.restaurant_order_number else 1

    order = Order(
        restaurant_id=restaurant.id,
        restaurant_order_number=next_order_number,
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
    return {"message": "Order placed!", "order_id": order.id, "order_number": next_order_number}

@app.get("/orders")
def get_orders(db: Session = Depends(get_db)):
    orders = db.query(Order).all()
    return orders

@app.get("/r/{slug}/admin")
def admin_dashboard(
    slug: str,
    request: Request,
    filter_date: str = None,
    admin_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    restaurant = db.query(Restaurant).filter(Restaurant.slug == slug).first()
    if not restaurant:
        return {"error": "Restaurant not found"}

    restaurant_id = get_session_restaurant_id(admin_token) if admin_token else None
    if not restaurant_id or restaurant_id != restaurant.id:
        return RedirectResponse(url=f"/r/{slug}/admin/login", status_code=302)

    if not filter_date:
        filter_date = date.today().isoformat()

    selected_date = datetime.strptime(filter_date, "%Y-%m-%d").date()

    all_orders_dates = db.query(Order.created_at).filter(Order.restaurant_id == restaurant.id).all()
    unique_dates = sorted(set(o.created_at.date() for o in all_orders_dates if o.created_at), reverse=True)

    if date.today() not in unique_dates:
        unique_dates.insert(0, date.today())

    orders = db.query(Order).filter(
        Order.restaurant_id == restaurant.id,
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
            "selected_date": selected_date.isoformat(),
            "slug": slug,
            "restaurant_name": restaurant.name
        }
    )

@app.post("/r/{slug}/order/{order_id}/status")
def update_order_status(
    slug: str,
    order_id: int,
    status: str,
    admin_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    restaurant = db.query(Restaurant).filter(Restaurant.slug == slug).first()
    restaurant_id = get_session_restaurant_id(admin_token) if admin_token else None
    if not restaurant or not restaurant_id or restaurant_id != restaurant.id:
        return {"error": "Unauthorized"}

    order = db.query(Order).filter(Order.id == order_id, Order.restaurant_id == restaurant.id).first()
    if not order:
        return {"error": "Order not found"}
    order.status = status
    db.commit()
    return {"message": "Status updated"}

@app.post("/r/{slug}/admin/menu/add")
def add_menu_item(
    slug: str,
    name: str,
    category: str,
    price: float,
    admin_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    restaurant = db.query(Restaurant).filter(Restaurant.slug == slug).first()
    restaurant_id = get_session_restaurant_id(admin_token) if admin_token else None
    if not restaurant or not restaurant_id or restaurant_id != restaurant.id:
        return {"error": "Unauthorized"}

    item = MenuItem(restaurant_id=restaurant.id, name=name, category=category, price=price)
    db.add(item)
    db.commit()
    return {"message": "Item added"}

@app.post("/r/{slug}/admin/menu/edit/{item_id}")
def edit_menu_item(
    slug: str,
    item_id: int,
    name: str,
    category: str,
    price: float,
    admin_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    restaurant = db.query(Restaurant).filter(Restaurant.slug == slug).first()
    restaurant_id = get_session_restaurant_id(admin_token) if admin_token else None
    if not restaurant or not restaurant_id or restaurant_id != restaurant.id:
        return {"error": "Unauthorized"}

    item = db.query(MenuItem).filter(MenuItem.id == item_id, MenuItem.restaurant_id == restaurant.id).first()
    if not item:
        return {"error": "Item not found"}
    item.name = name
    item.category = category
    item.price = price
    db.commit()
    return {"message": "Item updated"}

@app.get("/r/{slug}/admin/menu")
def get_menu_items(slug: str, db: Session = Depends(get_db)):
    restaurant = db.query(Restaurant).filter(Restaurant.slug == slug).first()
    if not restaurant:
        return []
    items = db.query(MenuItem).filter(MenuItem.restaurant_id == restaurant.id).all()
    return items

@app.post("/r/{slug}/admin/login")
def login(
    slug: str,
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    restaurant = db.query(Restaurant).filter(
        Restaurant.slug == slug,
        Restaurant.username == username,
    ).first()

    if restaurant and verify_password(password, restaurant.password):
        token = create_session(restaurant.id)
        response = RedirectResponse(url=f"/r/{slug}/admin", status_code=302)
        response.set_cookie(
            key="admin_token",
            value=token,
            httponly=True,
            path=f"/r/{slug}"
        )
        return response

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Invalid username or password", "slug": slug}
    )

@app.post("/r/{slug}/admin/login")
def login(
    slug: str,
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    restaurant = db.query(Restaurant).filter(
        Restaurant.slug == slug,
        Restaurant.username == username,
        Restaurant.password == password
    ).first()

    if restaurant:
        token = create_session(restaurant.id)
        response = RedirectResponse(url=f"/r/{slug}/admin", status_code=302)
        response.set_cookie(
            key="admin_token",
            value=token,
            httponly=True,
            path=f"/r/{slug}"
        )
        return response

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Invalid username or password", "slug": slug}
    )

@app.get("/r/{slug}/admin/logout")
def logout(slug: str, admin_token: Optional[str] = Cookie(None)):
    if admin_token in active_sessions:
        del active_sessions[admin_token]
    response = RedirectResponse(url=f"/r/{slug}/admin/login", status_code=302)
    response.delete_cookie("admin_token", path=f"/r/{slug}")
    return response

