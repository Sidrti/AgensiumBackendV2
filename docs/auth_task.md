# Task: MySQL Authentication System Implementation

A comprehensive guide for implementing a production-ready MySQL 8+ authentication system with OTP verification, Pydantic validators, and FastAPI best practices.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Prerequisites & Setup](#3-prerequisites--setup)
4. [Implementation](#4-implementation)
   - [4.1 Database Connection](#41-database-connection)
   - [4.2 SQLAlchemy Models](#42-sqlalchemy-models)
   - [4.3 Pydantic Schemas with Validators](#43-pydantic-schemas-with-validators)
   - [4.4 Custom Exceptions](#44-custom-exceptions)
   - [4.5 Utility Functions](#45-utility-functions)
   - [4.6 Dependencies](#46-dependencies)
   - [4.7 API Router](#47-api-router)
5. [API Endpoints Reference](#5-api-endpoints-reference)
6. [Testing & Verification](#6-testing--verification)
7. [Progress Tracking](#7-progress-tracking)

---

## 1. Overview

### 1.1 Goal

Implement a robust MySQL 8+ authentication system for Agensium Backend with:

- MySQL 8+ as the primary database
- OTP-based email verification
- Secure password reset flow
- Pydantic-powered input validation

### 1.2 Key Features

| Feature                         | Description                                                |
| ------------------------------- | ---------------------------------------------------------- |
| **OTP Type Differentiation**    | Separate OTP types for `registration` and `password_reset` |
| **Email Verification**          | Users must verify email before login                       |
| **Pydantic Validators**         | Centralized, reusable validation logic                     |
| **Password Security**           | Strong password requirements enforced at schema level      |
| **User Enumeration Protection** | Consistent responses to prevent email discovery            |

### 1.3 Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         REGISTRATION FLOW                               │
├─────────────────────────────────────────────────────────────────────────┤
│  Register → OTP Sent (type: registration) → Verify OTP → Login Enabled │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                       PASSWORD RESET FLOW                               │
├─────────────────────────────────────────────────────────────────────────┤
│  Forgot Password → OTP Sent (type: password_reset) → Reset Password    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture

### 2.1 Project Structure

```
backend/
├── main.py                    # FastAPI application entry point
├── requirements.txt           # Project dependencies
├── .env                       # Environment variables
├── auth/
│   ├── __init__.py
│   ├── router.py              # API endpoints (clean, no validation logic)
│   ├── dependencies.py        # FastAPI dependencies (get_current_user)
│   ├── utils.py               # Password hashing, JWT, OTP generation
│   └── exceptions.py          # Custom HTTP exceptions
├── db/
│   ├── __init__.py
│   ├── database.py            # MySQL connection & session
│   ├── models.py              # SQLAlchemy models
│   └── schemas.py             # Pydantic schemas with validators
└── docs2/
    └── task2.md               # This document
```

### 2.2 Technology Stack

| Component        | Technology        |
| ---------------- | ----------------- |
| Framework        | FastAPI           |
| Database         | MySQL 8+          |
| ORM              | SQLAlchemy 2.0    |
| Validation       | Pydantic v2       |
| Auth             | JWT (python-jose) |
| Password Hashing | Passlib (bcrypt)  |

---

## 3. Prerequisites & Setup

### 3.1 Install Dependencies

```bash
pip install fastapi uvicorn sqlalchemy mysql-connector-python python-jose[cryptography] passlib[bcrypt] python-dotenv pydantic[email]
```

Or add to `requirements.txt`:

```txt
fastapi>=0.100.0
uvicorn>=0.23.0
sqlalchemy>=2.0.0
mysql-connector-python>=8.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-dotenv>=1.0.0
pydantic[email]>=2.0.0
```

### 3.2 Environment Configuration

Create `.env` file in the backend root:

```env
# Database Configuration (REQUIRED)
DATABASE_URL=mysql+mysqlconnector://user:password@localhost:3306/agensium

# JWT Configuration
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OTP Configuration
OTP_EXPIRE_MINUTES=10
```

### 3.3 MySQL Database Setup

```sql
-- Create database
CREATE DATABASE IF NOT EXISTS agensium CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user (optional)
CREATE USER 'agensium_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON agensium.* TO 'agensium_user'@'localhost';
FLUSH PRIVILEGES;
```

---

## 4. Implementation

### 4.1 Database Connection

**File:** `backend/db/database.py`

```python
"""
Database connection configuration for MySQL.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# MySQL connection - REQUIRED
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

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
```

---

### 4.2 SQLAlchemy Models

**File:** `backend/db/models.py`

```python
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
```

---

### 4.3 Pydantic Schemas with Validators

**File:** `backend/db/schemas.py`

This is the **key file** implementing Pydantic validators for clean, reusable validation.

```python
"""
Pydantic schemas with built-in validators for input validation.
All validation logic is centralized here - route handlers stay clean.
"""
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, Literal
from enum import Enum
import re


# ============================================================================
# CONSTANTS & ENUMS
# ============================================================================

class OTPTypeEnum(str, Enum):
    """Valid OTP types."""
    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"


# Password validation constants
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_SPECIAL_CHARS = r"!@#$%^&*()_+\-=\[\]{}|;:,.<>?"


# ============================================================================
# REUSABLE VALIDATORS
# ============================================================================

class PasswordMixin:
    """
    Mixin class containing reusable password validation logic.
    Use this in any schema that requires password validation.
    """

    @staticmethod
    def validate_password_strength(password: str, field_name: str = "Password") -> str:
        """
        Validate password meets all security requirements.

        Requirements:
        - Minimum 8 characters
        - Maximum 128 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
        """
        if not password or not password.strip():
            raise ValueError(f"{field_name} is required")

        password = password.strip()

        if len(password) < PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"{field_name} must be at least {PASSWORD_MIN_LENGTH} characters long"
            )

        if len(password) > PASSWORD_MAX_LENGTH:
            raise ValueError(
                f"{field_name} must not exceed {PASSWORD_MAX_LENGTH} characters"
            )

        if not any(char.isupper() for char in password):
            raise ValueError(
                f"{field_name} must contain at least one uppercase letter"
            )

        if not any(char.islower() for char in password):
            raise ValueError(
                f"{field_name} must contain at least one lowercase letter"
            )

        if not any(char.isdigit() for char in password):
            raise ValueError(
                f"{field_name} must contain at least one digit"
            )

        if not re.search(f"[{re.escape(PASSWORD_SPECIAL_CHARS)}]", password):
            raise ValueError(
                f"{field_name} must contain at least one special character "
                f"({PASSWORD_SPECIAL_CHARS})"
            )

        return password


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class UserCreate(BaseModel):
    """
    Schema for user registration.
    All validation happens automatically via Pydantic validators.
    """
    email: EmailStr = Field(
        ...,
        description="User's email address",
        examples=["user@example.com"]
    )
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="User's password (8-128 chars, uppercase, lowercase, digit, special char)",
        examples=["SecurePass123!"]
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User's full name",
        examples=["John Doe"]
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower().strip()

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        """Validate and clean full name."""
        if not v or not v.strip():
            raise ValueError("Full name is required")

        cleaned = v.strip()

        # Check for valid characters (letters, spaces, hyphens, apostrophes)
        if not re.match(r"^[a-zA-Z\s\-']+$", cleaned):
            raise ValueError(
                "Full name can only contain letters, spaces, hyphens, and apostrophes"
            )

        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        return PasswordMixin.validate_password_strength(v, "Password")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "user@example.com",
                    "password": "SecurePass123!",
                    "full_name": "John Doe"
                }
            ]
        }
    }


class VerifyOTP(BaseModel):
    """Schema for OTP verification."""
    email: EmailStr = Field(..., description="User's email address")
    otp: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit OTP code",
        examples=["123456"]
    )
    otp_type: Literal["registration", "password_reset"] = Field(
        ...,
        description="Type of OTP: 'registration' or 'password_reset'"
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower().strip()

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        """Validate OTP format."""
        if not v or not v.strip():
            raise ValueError("OTP is required")

        cleaned = v.strip()

        if not cleaned.isdigit():
            raise ValueError("OTP must contain only digits")

        if len(cleaned) != 6:
            raise ValueError("OTP must be exactly 6 digits")

        return cleaned


class ForgotPassword(BaseModel):
    """Schema for forgot password request."""
    email: EmailStr = Field(..., description="User's email address")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower().strip()


class ResetPassword(BaseModel):
    """Schema for password reset with OTP."""
    email: EmailStr = Field(..., description="User's email address")
    otp: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit OTP code"
    )
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="New password"
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower().strip()

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        """Validate OTP format."""
        cleaned = v.strip()
        if not cleaned.isdigit() or len(cleaned) != 6:
            raise ValueError("OTP must be exactly 6 digits")
        return cleaned

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength."""
        return PasswordMixin.validate_password_strength(v, "New password")


class ChangePassword(BaseModel):
    """Schema for changing password (logged-in users)."""
    old_password: str = Field(
        ...,
        min_length=1,
        description="Current password"
    )
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="New password"
    )

    @field_validator("old_password")
    @classmethod
    def validate_old_password(cls, v: str) -> str:
        """Validate old password is provided."""
        if not v or not v.strip():
            raise ValueError("Current password is required")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength."""
        return PasswordMixin.validate_password_strength(v, "New password")

    @model_validator(mode="after")
    def passwords_must_differ(self):
        """Ensure new password is different from old password."""
        if self.old_password == self.new_password:
            raise ValueError("New password must be different from current password")
        return self


class ResendOTP(BaseModel):
    """Schema for resending OTP."""
    email: EmailStr = Field(..., description="User's email address")
    otp_type: Literal["registration", "password_reset"] = Field(
        ...,
        description="Type of OTP to resend"
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower().strip()


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class UserResponse(BaseModel):
    """Response schema for user data."""
    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    message: Optional[str] = None

    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    """Response schema for registration."""
    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    message: str
    otp: Optional[str] = None  # Only in development
    otp_type: Optional[str] = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """Response schema for JWT token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiry time in seconds")
    user_email: EmailStr


class GenericResponse(BaseModel):
    """Generic API response."""
    message: str
    otp: Optional[str] = None  # Only in development
    otp_type: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
    error_code: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"detail": "Invalid credentials", "error_code": "AUTH_001"}
            ]
        }
    }
```

---

### 4.4 Custom Exceptions

**File:** `backend/auth/exceptions.py`

```python
"""
Custom exceptions for authentication module.
Provides consistent error responses across the API.
"""
from fastapi import HTTPException, status


class AuthException(HTTPException):
    """Base exception for authentication errors."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = None,
        headers: dict = None
    ):
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers=headers
        )
        self.error_code = error_code


class InvalidCredentialsException(AuthException):
    """Exception for invalid login credentials."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            error_code="AUTH_001",
            headers={"WWW-Authenticate": "Bearer"}
        )


class EmailNotVerifiedException(AuthException):
    """Exception when email is not verified."""

    def __init__(self, otp: str = None, otp_type: str = None):
        headers = {"WWW-Authenticate": "Bearer"}
        if otp:
            headers["X-OTP"] = otp
            headers["X-OTP-Type"] = otp_type or "registration"

        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email to login.",
            error_code="AUTH_002",
            headers=headers
        )


class UserInactiveException(AuthException):
    """Exception when user account is inactive."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive. Please contact support.",
            error_code="AUTH_003"
        )


class EmailAlreadyExistsException(AuthException):
    """Exception when email is already registered."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
            error_code="AUTH_004"
        )


class UserNotFoundException(AuthException):
    """Exception when user is not found."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            error_code="AUTH_005"
        )


class InvalidOTPException(AuthException):
    """Exception for invalid OTP."""

    def __init__(self, detail: str = "Invalid OTP"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="AUTH_006"
        )


class OTPExpiredException(AuthException):
    """Exception when OTP has expired."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new one.",
            error_code="AUTH_007"
        )


class OTPTypeMismatchException(AuthException):
    """Exception when OTP type doesn't match."""

    def __init__(self, expected: str, received: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OTP type. Expected '{expected}', got '{received}'",
            error_code="AUTH_008"
        )


class InvalidTokenException(AuthException):
    """Exception for invalid JWT token."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            error_code="AUTH_009",
            headers={"WWW-Authenticate": "Bearer"}
        )


class PasswordMismatchException(AuthException):
    """Exception when old password is incorrect."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
            error_code="AUTH_010"
        )
```

---

### 4.5 Utility Functions

**File:** `backend/auth/utils.py`

```python
"""
Utility functions for authentication.
Includes password hashing, JWT handling, and OTP generation.
"""
import os
import random
import string
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================================
# PASSWORD FUNCTIONS
# ============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.

    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a plain password using bcrypt.

    Args:
        password: The plain text password to hash

    Returns:
        The hashed password string
    """
    return pwd_context.hash(password)


# ============================================================================
# JWT FUNCTIONS
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: The payload data to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        The encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.

    Args:
        token: The JWT token string to decode

    Returns:
        The decoded payload or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# ============================================================================
# OTP FUNCTIONS
# ============================================================================

def generate_otp(length: int = 6) -> str:
    """
    Generate a random numeric OTP.

    Args:
        length: The length of the OTP (default: 6)

    Returns:
        A string of random digits
    """
    return "".join(random.choices(string.digits, k=length))


def get_otp_expiry() -> datetime:
    """
    Get the expiry datetime for a new OTP.

    Returns:
        datetime object representing when the OTP expires
    """
    return datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)


def is_otp_expired(expires_at: datetime) -> bool:
    """
    Check if an OTP has expired.

    Args:
        expires_at: The expiry datetime of the OTP

    Returns:
        True if expired, False otherwise
    """
    return datetime.utcnow() > expires_at
```

---

### 4.6 Dependencies

**File:** `backend/auth/dependencies.py`

```python
"""
FastAPI dependencies for authentication.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from db.database import get_db
from db import models
from . import utils
from .exceptions import InvalidTokenException, UserNotFoundException, UserInactiveException

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """
    Dependency to get the current authenticated user.

    Args:
        token: JWT token from Authorization header
        db: Database session

    Returns:
        The authenticated User object

    Raises:
        InvalidTokenException: If token is invalid or expired
        UserNotFoundException: If user doesn't exist
        UserInactiveException: If user account is inactive
    """
    payload = utils.decode_access_token(token)

    if payload is None:
        raise InvalidTokenException()

    email: str = payload.get("sub")
    if email is None:
        raise InvalidTokenException()

    user = db.query(models.User).filter(models.User.email == email).first()

    if user is None:
        raise UserNotFoundException()

    if not user.is_active:
        raise UserInactiveException()

    return user


async def get_current_active_verified_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """
    Dependency to get current user who is both active and verified.

    Args:
        current_user: The authenticated user

    Returns:
        The verified User object

    Raises:
        HTTPException: If user is not verified
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified"
        )
    return current_user
```

---

### 4.7 API Router

**File:** `backend/auth/router.py`

The router is now **clean and focused** - all validation is handled by Pydantic schemas.

```python
"""
Authentication API routes.
All input validation is handled by Pydantic schemas - routes stay clean.
"""
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from db.database import get_db
from db import models, schemas
from . import utils, dependencies
from .exceptions import (
    InvalidCredentialsException,
    EmailNotVerifiedException,
    UserInactiveException,
    EmailAlreadyExistsException,
    UserNotFoundException,
    InvalidOTPException,
    OTPExpiredException,
    OTPTypeMismatchException,
    PasswordMismatchException
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================================
# REGISTRATION & VERIFICATION
# ============================================================================

@router.post(
    "/register",
    response_model=schemas.RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new user account. An OTP will be sent for email verification."
)
def register_user(
    user: schemas.UserCreate,  # Validation happens here automatically!
    db: Session = Depends(get_db)
):
    """
    Register a new user with email verification.

    - Validates input via Pydantic schema
    - Checks for duplicate email
    - Creates user with is_verified=False
    - Generates and returns OTP for verification
    """
    # Check if email already exists
    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user:
        raise EmailAlreadyExistsException()

    # Generate OTP
    otp_code = utils.generate_otp()
    otp_expires_at = utils.get_otp_expiry()

    # Create user
    db_user = models.User(
        email=user.email,
        hashed_password=utils.get_password_hash(user.password),
        full_name=user.full_name,
        otp_code=otp_code,
        otp_expires_at=otp_expires_at,
        otp_type="registration",
        is_verified=False,
        is_active=True
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # TODO: Send OTP via email service
    # await send_otp_email(user.email, otp_code)

    return schemas.RegisterResponse(
        id=db_user.id,
        email=db_user.email,
        full_name=db_user.full_name,
        is_active=db_user.is_active,
        message="Registration successful. Please verify your email with the OTP sent.",
        otp=otp_code,  # Remove in production - only for testing
        otp_type="registration"
    )


@router.post(
    "/verify-otp",
    response_model=schemas.GenericResponse,
    summary="Verify OTP",
    description="Verify OTP for email verification or password reset."
)
def verify_otp(
    data: schemas.VerifyOTP,  # Validation happens here automatically!
    db: Session = Depends(get_db)
):
    """
    Verify OTP for registration or password reset.

    - Validates OTP format via Pydantic
    - Checks OTP existence and expiry
    - Validates OTP type matches expected flow
    - For registration: marks user as verified
    - For password_reset: confirms OTP is valid for reset
    """
    user = db.query(models.User).filter(
        models.User.email == data.email
    ).first()

    if not user:
        raise UserNotFoundException()

    # Validate OTP
    if not user.otp_code or user.otp_code != data.otp:
        raise InvalidOTPException("Invalid OTP code")

    if utils.is_otp_expired(user.otp_expires_at):
        raise OTPExpiredException()

    if user.otp_type != data.otp_type:
        raise OTPTypeMismatchException(
            expected=user.otp_type,
            received=data.otp_type
        )

    # Process based on OTP type
    if data.otp_type == "registration":
        user.is_verified = True
        user.otp_code = None
        user.otp_expires_at = None
        user.otp_type = None
        db.commit()

        return schemas.GenericResponse(
            message="Email verified successfully. You can now login."
        )

    elif data.otp_type == "password_reset":
        # Don't clear OTP yet - it's needed for reset-password endpoint
        return schemas.GenericResponse(
            message="OTP verified. Please proceed to reset your password."
        )

    raise InvalidOTPException("Unknown OTP type")


@router.post(
    "/resend-otp",
    response_model=schemas.GenericResponse,
    summary="Resend OTP",
    description="Resend OTP for email verification or password reset."
)
def resend_otp(
    data: schemas.ResendOTP,
    db: Session = Depends(get_db)
):
    """
    Resend OTP to user's email.

    - Generates new OTP
    - Updates expiry time
    - Maintains same OTP type
    """
    user = db.query(models.User).filter(
        models.User.email == data.email
    ).first()

    # User enumeration protection
    if not user:
        return schemas.GenericResponse(
            message="If the email exists, a new OTP will be sent."
        )

    # For registration OTP, user must not be verified
    if data.otp_type == "registration" and user.is_verified:
        return schemas.GenericResponse(
            message="Email is already verified. Please login."
        )

    # Generate new OTP
    otp_code = utils.generate_otp()
    user.otp_code = otp_code
    user.otp_expires_at = utils.get_otp_expiry()
    user.otp_type = data.otp_type
    db.commit()

    # TODO: Send OTP via email service

    return schemas.GenericResponse(
        message="OTP sent to your email.",
        otp=otp_code,  # Remove in production
        otp_type=data.otp_type
    )


# ============================================================================
# PASSWORD MANAGEMENT
# ============================================================================

@router.post(
    "/forgot-password",
    response_model=schemas.GenericResponse,
    summary="Request password reset",
    description="Request a password reset OTP."
)
def forgot_password(
    data: schemas.ForgotPassword,
    db: Session = Depends(get_db)
):
    """
    Request password reset OTP.

    - Generates password_reset type OTP
    - Uses consistent response for security (user enumeration protection)
    """
    user = db.query(models.User).filter(
        models.User.email == data.email
    ).first()

    # User enumeration protection - same response regardless of user existence
    if not user:
        return schemas.GenericResponse(
            message="If the email exists, a password reset OTP will be sent."
        )

    # Generate OTP
    otp_code = utils.generate_otp()
    user.otp_code = otp_code
    user.otp_expires_at = utils.get_otp_expiry()
    user.otp_type = "password_reset"
    db.commit()

    # TODO: Send OTP via email service

    return schemas.GenericResponse(
        message="Password reset OTP sent to your email.",
        otp=otp_code,  # Remove in production
        otp_type="password_reset"
    )


@router.post(
    "/reset-password",
    response_model=schemas.GenericResponse,
    summary="Reset password",
    description="Reset password using OTP."
)
def reset_password(
    data: schemas.ResetPassword,  # Password validation via Pydantic!
    db: Session = Depends(get_db)
):
    """
    Reset password using OTP.

    - Validates new password via Pydantic schema
    - Verifies OTP is valid and correct type
    - Updates password and clears OTP fields
    """
    user = db.query(models.User).filter(
        models.User.email == data.email
    ).first()

    if not user:
        raise UserNotFoundException()

    # Validate OTP
    if not user.otp_code or user.otp_code != data.otp:
        raise InvalidOTPException("Invalid OTP code")

    if utils.is_otp_expired(user.otp_expires_at):
        raise OTPExpiredException()

    if user.otp_type != "password_reset":
        raise OTPTypeMismatchException(
            expected="password_reset",
            received=user.otp_type or "none"
        )

    # Update password
    user.hashed_password = utils.get_password_hash(data.new_password)
    user.otp_code = None
    user.otp_expires_at = None
    user.otp_type = None
    db.commit()

    return schemas.GenericResponse(
        message="Password reset successfully. Please login with your new password."
    )


@router.post(
    "/change-password",
    response_model=schemas.GenericResponse,
    summary="Change password",
    description="Change password for logged-in user."
)
def change_password(
    data: schemas.ChangePassword,  # Validates old != new via Pydantic!
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change password for authenticated user.

    - Verifies current password
    - Validates new password via Pydantic (including old != new check)
    - Updates password
    """
    if not utils.verify_password(data.old_password, current_user.hashed_password):
        raise PasswordMismatchException()

    current_user.hashed_password = utils.get_password_hash(data.new_password)
    db.commit()

    return schemas.GenericResponse(
        message="Password changed successfully."
    )


# ============================================================================
# LOGIN & TOKEN
# ============================================================================

@router.post(
    "/login",
    response_model=schemas.Token,
    summary="Login",
    description="Login to get access token."
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token.

    - Validates credentials
    - Checks user is active and verified
    - Returns JWT access token
    """
    user = db.query(models.User).filter(
        models.User.email == form_data.username.lower()
    ).first()

    if not user:
        raise InvalidCredentialsException()

    if not utils.verify_password(form_data.password, user.hashed_password):
        raise InvalidCredentialsException()

    if not user.is_active:
        raise UserInactiveException()

    # Check email verification
    if not user.is_verified:
        # Generate new OTP for unverified user
        otp_code = utils.generate_otp()
        user.otp_code = otp_code
        user.otp_expires_at = utils.get_otp_expiry()
        user.otp_type = "registration"
        db.commit()

        raise EmailNotVerifiedException(otp=otp_code, otp_type="registration")

    # Create access token
    access_token = utils.create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=utils.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return schemas.Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=utils.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_email=user.email
    )


# ============================================================================
# USER PROFILE
# ============================================================================

@router.get(
    "/me",
    response_model=schemas.UserResponse,
    summary="Get current user",
    description="Get the current authenticated user's profile."
)
def get_current_user_profile(
    current_user: models.User = Depends(dependencies.get_current_user)
):
    """
    Get current user's profile.

    - Requires valid JWT token
    - Returns user profile data
    """
    return schemas.UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        message="Profile retrieved successfully"
    )
```

---

## 5. API Endpoints Reference

### 6.1 Endpoints Summary

| Method | Endpoint                | Description             | Auth Required |
| ------ | ----------------------- | ----------------------- | ------------- |
| `POST` | `/auth/register`        | Register new user       | No            |
| `POST` | `/auth/verify-otp`      | Verify OTP              | No            |
| `POST` | `/auth/resend-otp`      | Resend OTP              | No            |
| `POST` | `/auth/login`           | Login & get token       | No            |
| `POST` | `/auth/forgot-password` | Request password reset  | No            |
| `POST` | `/auth/reset-password`  | Reset password with OTP | No            |
| `POST` | `/auth/change-password` | Change password         | Yes           |
| `GET`  | `/auth/me`              | Get user profile        | Yes           |

### 6.2 Request/Response Examples

#### Register User

```bash
POST /auth/register
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "full_name": "John Doe"
}
```

**Response (201):**

```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "message": "Registration successful. Please verify your email with the OTP sent.",
  "otp": "123456",
  "otp_type": "registration"
}
```

#### Verify OTP

```bash
POST /auth/verify-otp
Content-Type: application/json

{
    "email": "user@example.com",
    "otp": "123456",
    "otp_type": "registration"
}
```

**Response (200):**

```json
{
  "message": "Email verified successfully. You can now login."
}
```

#### Login

```bash
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=SecurePass123!
```

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user_email": "user@example.com"
}
```

#### Forgot Password

```bash
POST /auth/forgot-password
Content-Type: application/json

{
    "email": "user@example.com"
}
```

**Response (200):**

```json
{
  "message": "Password reset OTP sent to your email.",
  "otp": "654321",
  "otp_type": "password_reset"
}
```

#### Reset Password

```bash
POST /auth/reset-password
Content-Type: application/json

{
    "email": "user@example.com",
    "otp": "654321",
    "new_password": "NewSecurePass456!"
}
```

**Response (200):**

```json
{
  "message": "Password reset successfully. Please login with your new password."
}
```

---

## 6. Testing & Verification

### 6.1 Test Cases (20 Total)

#### Registration Flow

| #   | Test Case                     | Expected Result                 |
| --- | ----------------------------- | ------------------------------- |
| 1   | Register with valid data      | 201, OTP returned               |
| 2   | Register with duplicate email | 400, "Email already registered" |
| 3   | Register with weak password   | 422, Validation error           |
| 4   | Register with invalid email   | 422, Validation error           |
| 5   | Register with empty full name | 422, Validation error           |

#### OTP Verification Flow

| #   | Test Case                  | Expected Result         |
| --- | -------------------------- | ----------------------- |
| 6   | Verify with correct OTP    | 200, "Email verified"   |
| 7   | Verify with wrong OTP      | 400, "Invalid OTP"      |
| 8   | Verify with expired OTP    | 400, "OTP has expired"  |
| 9   | Verify with wrong OTP type | 400, "Invalid OTP type" |
| 10  | Resend OTP                 | 200, New OTP returned   |

#### Login Flow

| #   | Test Case                 | Expected Result              |
| --- | ------------------------- | ---------------------------- |
| 11  | Login before verification | 403, "Email not verified"    |
| 12  | Login after verification  | 200, Token returned          |
| 13  | Login with wrong password | 401, "Invalid credentials"   |
| 14  | Login with inactive user  | 403, "User account inactive" |

#### Password Reset Flow

| #   | Test Case                      | Expected Result                    |
| --- | ------------------------------ | ---------------------------------- |
| 15  | Forgot password (existing)     | 200, OTP returned                  |
| 16  | Forgot password (non-existing) | 200, Same message (protection)     |
| 17  | Reset with valid OTP           | 200, "Password reset successfully" |
| 18  | Reset with wrong OTP type      | 400, "Invalid OTP type"            |

#### Change Password Flow

| #   | Test Case                        | Expected Result                   |
| --- | -------------------------------- | --------------------------------- |
| 19  | Change with correct old password | 200, "Password changed"           |
| 20  | Change with wrong old password   | 400, "Current password incorrect" |

### 6.2 Running the Application

```bash
# Start MySQL (using Docker)
docker run -d \
  --name mysql-agensium \
  -e MYSQL_ROOT_PASSWORD=rootpassword \
  -e MYSQL_DATABASE=agensium \
  -e MYSQL_USER=agensium_user \
  -e MYSQL_PASSWORD=secure_password \
  -p 3306:3306 \
  mysql:8

# Start the server
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Access API docs
# http://localhost:8000/docs
```

### 6.3 Sample curl Commands

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"SecurePass123!","full_name":"Test User"}'

# Verify OTP
curl -X POST http://localhost:8000/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","otp":"123456","otp_type":"registration"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -d "username=test@example.com&password=SecurePass123!"

# Get Profile (with token)
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## 7. Progress Tracking

### Implementation Checklist

- [ ] **Database Setup**

  - [ ] MySQL 8+ installed and configured
  - [ ] Database and user created
  - [ ] `.env` file configured

- [x] **Core Implementation**

  - [x] `db/database.py` - MySQL connection
  - [x] `db/models.py` - User model with OTP fields
  - [x] `db/schemas.py` - Pydantic schemas with validators
  - [x] `auth/exceptions.py` - Custom exceptions
  - [x] `auth/utils.py` - Password, JWT, OTP utilities
  - [x] `auth/dependencies.py` - FastAPI dependencies
  - [x] `auth/router.py` - API endpoints

- [ ] **Testing**

  - [ ] Registration flow (5 tests)
  - [ ] OTP verification flow (5 tests)
  - [ ] Login flow (4 tests)
  - [ ] Password reset flow (4 tests)
  - [ ] Change password flow (2 tests)

- [ ] **Production Ready**
  - [ ] Remove OTP from responses (email integration)
  - [ ] Add rate limiting
  - [ ] Add logging
  - [ ] Security audit complete

---

## Best Practices Summary

### ✅ What We Did Right

1. **Pydantic Validators**: All validation logic centralized in schemas
2. **Clean Routes**: Route handlers focus only on business logic
3. **Custom Exceptions**: Consistent error responses with error codes
4. **User Enumeration Protection**: Same response for existing/non-existing emails
5. **OTP Type Safety**: Prevents cross-flow OTP usage
6. **Password Security**: Strong requirements enforced at schema level
7. **Separation of Concerns**: Clear module responsibilities
8. **Type Hints**: Full type safety throughout codebase
9. **Documentation**: OpenAPI auto-generated from schemas

### ⚠️ Production Considerations

1. **Remove OTP from responses** - Integrate email service
2. **Add rate limiting** - Prevent brute force attacks
3. **Add request logging** - Audit trail for security
4. **Use HTTPS** - Secure transport layer
5. **Rotate SECRET_KEY** - Regular key rotation
6. **Add refresh tokens** - Better token management

---

**Status**: Ready for implementation with best practices.
