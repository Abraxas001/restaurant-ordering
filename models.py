from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from datetime import datetime
from database import Base

class Restaurant(Base):
    __tablename__ = "restaurants"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    slug = Column(String, unique=True, index=True)  # used in URL, e.g. "spice-garden"
    username = Column(String, unique=True)
    password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"))
    name = Column(String)
    price = Column(Float)
    category = Column(String)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"))
    table_number = Column(Integer)
    status = Column(String, default="New")
    created_at = Column(DateTime, default=datetime.utcnow)
    customer_name = Column(String, nullable=True)
    customer_phone = Column(String, nullable=True)

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"))
    quantity = Column(Integer)
