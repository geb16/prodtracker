# src/prodtracker/db/models.py
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String(50), index=True)  # "focus", "unfocus", "prompt_response", "block"
    window_title = Column(String(512), nullable=True)
    app_name = Column(String(256), nullable=True)
    url = Column(String(1024), nullable=True)
    productive = Column(Boolean, nullable=False)  # signal True / noise False
    duration = Column(Float, nullable=True)  # seconds
    screenshot_path = Column(String(1024), nullable=True)
    meta_data = Column(Text, nullable=True)  # JSON string if needed


class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(128), unique=True, index=True)  # mobile device id
    name = Column(String(128))
    paired = Column(Boolean, default=False)
    secret = Column(String(256), nullable=True)  # HMAC/shared secret
    last_seen = Column(DateTime, default=datetime.utcnow)


class BlockRecord(Base):
    __tablename__ = "block_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    domains = Column(Text)  # JSON encoded list of domains
    active = Column(Boolean, default=True)
    reason = Column(String(256), nullable=True)
