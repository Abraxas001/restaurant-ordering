from database import get_db, engine, SessionLocal
from fastapi import FastAPI, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, engine
from models import Base, MenuItem, Order, OrderItem
from datetime import date, datetime

app = FastAPI()
Base.metadata.create_all(bind=engine)

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

@app.get("/")
def read_root():
    return {"message": "Restaurant API is up and running!"}

@app.get("/menu")
def get_menu(db: Session = Depends(get_db)):
    items = db.query(MenuItem).all()
    return items

@app.get("/table/{table_number}")
def table_menu(table_number: int, request: Request, db: Session = Depends(get_db)):
    items = db.query(MenuItem).all()
    return templates.TemplateResponse(
    request=request,
    name="menu.html",
    context={
        "items": items,
        "table_number": table_number
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
def admin_dashboard(request: Request, filter_date: str = None, db: Session = Depends(get_db)):
    # Default to today if no date provided
    if not filter_date:
        filter_date = date.today().isoformat()
    
    selected_date = datetime.strptime(filter_date, "%Y-%m-%d").date()
    
    # Get all unique dates that have orders
    all_orders_dates = db.query(Order.created_at).all()
    unique_dates = sorted(set(o.created_at.date() for o in all_orders_dates if o.created_at), reverse=True)
    
    # Ensure today is always in the list
    if date.today() not in unique_dates:
        unique_dates.insert(0, date.today())

    # Filter orders by selected date
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
def update_order_status(order_id: int, status: str, db: Session = Depends(get_db)):
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
    db: Session = Depends(get_db)
):
    item = MenuItem(name=name, category=category, price=price)
    db.add(item)
    db.commit()
    return {"message": "Item added"}

@app.post("/admin/menu/edit/{item_id}")
def edit_menu_item(
    item_id: int,
    price: float,
    db: Session = Depends(get_db)
):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        return {"error": "Item not found"}
    item.price = price
    db.commit()
    return {"message": "Price updated"}

@app.get("/admin/menu")
def get_menu_items(db: Session = Depends(get_db)):
    items = db.query(MenuItem).all()
    return items

@app.post("/admin/menu/edit/{item_id}")
def edit_menu_item(
    item_id: int,
    name: str,
    category: str,
    price: float,
    db: Session = Depends(get_db)
):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        return {"error": "Item not found"}
    item.name = name
    item.category = category
    item.price = price
    db.commit()
    return {"message": "Item updated"}

@app.get("/table/{table_number}")
def table_landing(table_number: int, request: Request):
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={"table_number": table_number}
    )

@app.get("/menu/{table_number}")
def table_menu(table_number: int, name: str, phone: str, request: Request, db: Session = Depends(get_db)):
    items = db.query(MenuItem).all()
    return templates.TemplateResponse(
        request=request,
        name="menu.html",
        context={
            "items": items,
            "table_number": table_number,
            "customer_name": name,
            "customer_phone": phone
        }
    )
