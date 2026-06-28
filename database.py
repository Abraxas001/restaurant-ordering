import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Always use SQLite — Turso approach wasn't compatible
# We'll use a fixed path so data persists on Render
DATABASE_URL = "sqlite:////opt/render/project/src/restaurant.db"

# Fallback for local development
if not os.path.exists("/opt/render"):
    DATABASE_URL = "sqlite:///./restaurant.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
