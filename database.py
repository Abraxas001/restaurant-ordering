import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

TURSO_URL = os.environ.get("TURSO_URL")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN")

if TURSO_URL and TURSO_TOKEN:
    DATABASE_URL = f"{TURSO_URL}?authToken={TURSO_TOKEN}"
    DATABASE_URL = DATABASE_URL.replace("libsql://", "sqlite+libsql://")
else:
    DATABASE_URL = "sqlite:///./restaurant.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
