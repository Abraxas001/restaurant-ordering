import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

TURSO_URL = os.environ.get("libsql://restaurant-db-abraxas001.aws-ap-south-1.turso.io")
TURSO_TOKEN = os.environ.get("eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODI2NjA0NDEsImlkIjoiMDE5ZjBlYzAtMGQwMS03OTY1LTgyYjEtODFmNmZlZTBjNDM1IiwicmlkIjoiOWIyNGQ3YmMtMmYxZS00OTMwLThiMDUtZTg5MjdlZWZiNTg3In0.uL7tLRnQgezvIdtoGgxaGS48VC5bI86jieSPwvg71ZjzFXCgp5DXnnoNf2-j3l7T1kBkqVINogE2oH8qCkMyCg")

if TURSO_URL and TURSO_TOKEN:
    # Production: use Turso
    DATABASE_URL = f"{TURSO_URL}?authToken={TURSO_TOKEN}"
    DATABASE_URL = DATABASE_URL.replace("libsql://", "sqlite+libsql://")
else:
    # Local development: use SQLite
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
