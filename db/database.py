"""
Database connection configuration for MySQL.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# MySQL connection - REQUIRED
# SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://avnadmin:AVNS_L28H0U06v5Ky--zUw1T@mysql-1d10a985-vivekb379-a220.g.aivencloud.com:16218/defaultdb?charset=utf8mb4";

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set. "
        "Please configure MySQL connection string in .env file."
    )

if "mysql" not in SQLALCHEMY_DATABASE_URL.lower():
    raise ValueError(
        "Only MySQL database is supported. "
        "DATABASE_URL must be a MySQL connection string."
    )

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,      # Verify connections before use
    pool_recycle=3600,       # Recycle connections every hour
    pool_size=10,            # Maximum connections in pool
    max_overflow=20,         # Additional connections when pool is full
    echo=False               # Set True for SQL debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    Dependency that provides a database session.
    Automatically closes the session after request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
