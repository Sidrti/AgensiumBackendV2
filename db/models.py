"""
SQLAlchemy models for MySQL database.
"""
from sqlalchemy import Boolean, Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
from .database import Base
import enum


class OTPType(str, enum.Enum):
    """Enum for OTP types to ensure type safety."""
    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"


class User(Base):
    """User model with OTP verification support."""

    __tablename__ = "users"

    # Primary Fields
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)

    # Status Fields
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # OTP Fields
    otp_code = Column(String(6), nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    otp_type = Column(String(50), nullable=True)  # 'registration' or 'password_reset'

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, is_verified={self.is_verified})>"
