# src/prodtracker/db/models.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float
from sqlalchemy.ext.declarative import declarative_base




Base = declarative_base() 
"""
why is declarative_base needed?
- It provides a base class for all ORM-mapped classes in SQLAlchemy.
- It maintains a catalog of classes and tables relative to that base.
- It allows defining models using class definitions, making it easier to work with database tables as Python objects.
- It enables features like automatic table creation, schema generation, and relationship management.
- It promotes a clear and organized way to define database schemas in code.
- clarify  ORM (Object-Relational Mapping) and how it relates to declarative_base with hands-on examples.

- ORM is a programming technique that allows developers to interact with a relational database using object-oriented programming concepts. 
- It maps database tables to classes and rows to instances of those classes.
- declarative_base is a function in SQLAlchemy that provides a base class for defining ORM-mapped classes. 
- By using declarative_base, developers can define their database schema as Python classes, making it easier to work with the database in an object-oriented manner.
- Example:
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
Base = declarative_base()
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
# Create an SQLite database in memory
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()
# Create a new user instance
new_user = User(name='Alice', email='alice@example.com')
session.add(new_user)
session.commit()
# Query the user from the database
user = session.query(User).filter_by(name='Alice').first()
print(user.email)  # Output: alice@example.com

# In this example, we define a User class that maps to the users table in the database.
# We use declarative_base to create a base class for our ORM models.
# We then create a new user instance, add it to the session, and commit the changes to the database.

"""

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
    device_id = Column(String(128), unique=True, index=True)    # mobile device id
    name = Column(String(128))
    paired = Column(Boolean, default=False)
    secret = Column(String(256), nullable=True)                  # HMAC/shared secret
    last_seen = Column(DateTime, default=datetime.utcnow)

class BlockRecord(Base):
    __tablename__ = "block_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    domains = Column(Text)        # JSON encoded list of domains
    active = Column(Boolean, default=True)
    reason = Column(String(256), nullable=True)
