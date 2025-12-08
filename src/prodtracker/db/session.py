# src/prodtracker/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
import os

DB_PATH = os.environ.get("PRODTRACKER_DB", "prodtracker.db")
ENGINE = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False, "timeout": 30}, echo=False)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)

def init_db():
    Base.metadata.create_all(bind=ENGINE)
