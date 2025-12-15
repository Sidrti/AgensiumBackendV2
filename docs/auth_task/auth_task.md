# Task: MySQL Authentication System Implementation

A comprehensive guide for the production-ready MySQL 8+ authentication system with OTP verification, Pydantic validators, and FastAPI best practices.

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

- MySQL 8+ as the primary database (hosted on Aiven Cloud)
- OTP-based email verification
- Secure password reset flow
- Pydantic-powered input validation
- Integration with billing/wallet system

### 1.2 Key Features

| Feature                         | Description                                                                       |
| ------------------------------- | --------------------------------------------------------------------------------- |
| **OTP Type Differentiation**    | Separate OTP types for `registration` and `password_reset`                        |
| **Email Verification**          | Users must verify email before login                                              |
| **Pydantic Validators**         | Centralized, reusable validation logic                                            |
| **Password Security**           | Strong password requirements enforced at schema level (bcrypt with 72-byte limit) |
| **User Enumeration Protection** | Consistent responses to prevent email discovery                                   |
| **Stripe Integration**          | User model includes `stripe_customer_id` for billing                              |
| **Wallet System**               | Each user has a credit wallet for agent execution                                 |

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
│   ├── database.py            # MySQL connection & session (PyMySQL driver)
│   ├── models.py              # SQLAlchemy models (User, CreditWallet, etc.)
│   └── schemas.py             # Pydantic schemas with validators
├── billing/
│   ├── __init__.py
│   ├── router.py              # Billing API endpoints
│   ├── wallet_service.py      # Credit wallet operations
│   ├── stripe_service.py      # Stripe integration
│   └── exceptions.py          # Billing exceptions
├── email_services/
│   ├── __init__.py
│   ├── email_service.py       # Brevo email integration
│   ├── email_templates.py     # HTML email templates
│   └── email_config.py        # Email configuration
└── docs/
    └── auth_task/
        ├── auth_task.md       # This document
        ├── email_services.md  # Email service task (Brevo)
        └── BREVO_SETUP_GUIDE.md
```

### 2.2 Technology Stack

| Component        | Technology               |
| ---------------- | ------------------------ |
| Framework        | FastAPI >= 0.115.0       |
| Database         | MySQL 8+ (Aiven Cloud)   |
| ORM              | SQLAlchemy 2.0+          |
| DB Driver        | PyMySQL >= 1.1.0         |
| Validation       | Pydantic v2              |
| Auth             | JWT (python-jose)        |
| Password Hashing | bcrypt >= 4.1.0 (direct) |
| Billing          | Stripe >= 10.0.0         |

---

## 3. Prerequisites & Setup

### 3.1 Install Dependencies

The following dependencies are already in `requirements.txt`:

```txt
# FastAPI and server
fastapi>=0.115.0
uvicorn[standard]==0.24.0

# Database - MySQL
sqlalchemy>=2.0.0
pymysql>=1.1.0
cryptography>=41.0.0
alembic>=1.13.0

# Authentication
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
bcrypt>=4.1.0

# Validation
email-validator>=2.1.0
pydantic[email]>=2.0.0

# Environment
python-dotenv==1.0.0

# Billing - Stripe
stripe>=10.0.0
```

### 3.2 Environment Configuration

Create `.env` file in the backend root:

```env
# Database Configuration - MySQL (Aiven Cloud)
DATABASE_URL=mysql+pymysql://user:password@host:port/database?charset=utf8mb4

# JWT Configuration
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OTP Configuration
OTP_EXPIRE_MINUTES=10

# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Frontend URL (for CORS)
FRONTEND_URL=http://localhost:5173
```

### 3.3 MySQL Database (Aiven Cloud)

The project uses Aiven Cloud MySQL. Connection string format:

```
mysql+pymysql://user:password@host:port/database?charset=utf8mb4
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

# MySQL connection using PyMySQL driver
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

The User model now includes Stripe integration and relationships to the billing system:

```python
"""
SQLAlchemy models for MySQL database.
"""
from sqlalchemy import Boolean, Column, Integer, String, DateTime, Enum, ForeignKey, JSON, Text, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
import enum


class OTPType(str, enum.Enum):
    """Enum for OTP types to ensure type safety."""
    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"


class User(Base):
    """User model with OTP verification support and Stripe integration."""

    __tablename__ = "users"

    # Primary Fields
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)

    # Stripe Integration
    stripe_customer_id = Column(String(255), unique=True, nullable=True, index=True)

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

    # Relationships
    wallet = relationship("CreditWallet", back_populates="user", uselist=False)
    transactions = relationship("CreditTransaction", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, is_verified={self.is_verified})>"
```

---

### 4.3 Pydantic Schemas with Validators

**File:** `backend/db/schemas.py`

Key changes from original spec:

- Password max length is 72 (bcrypt limit)
- Added billing-related schemas

```python
# Password validation constants
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 72  # bcrypt has a 72-byte limit
PASSWORD_SPECIAL_CHARS = r"!@#$%^&*()_+\-=\[\]{}|;:,.<>?"
```

The full implementation includes:

- `UserCreate` - Registration schema with password validation
- `VerifyOTP` - OTP verification with type differentiation
- `ForgotPassword` - Password reset request
- `ResetPassword` - Password reset with OTP
- `ChangePassword` - Change password for logged-in users (validates old ≠ new)
- `ResendOTP` - Resend OTP request

---

### 4.4 Custom Exceptions

**File:** `backend/auth/exceptions.py`

| Error Code | Exception                   | HTTP Status | Description                   |
| ---------- | --------------------------- | ----------- | ----------------------------- |
| AUTH_001   | InvalidCredentialsException | 401         | Invalid email or password     |
| AUTH_002   | EmailNotVerifiedException   | 403         | Email not verified            |
| AUTH_003   | UserInactiveException       | 403         | User account is inactive      |
| AUTH_004   | EmailAlreadyExistsException | 400         | Email already registered      |
| AUTH_005   | UserNotFoundException       | 404         | User not found                |
| AUTH_006   | InvalidOTPException         | 400         | Invalid OTP                   |
| AUTH_007   | OTPExpiredException         | 400         | OTP has expired               |
| AUTH_008   | OTPTypeMismatchException    | 400         | OTP type doesn't match        |
| AUTH_009   | InvalidTokenException       | 401         | Invalid or expired JWT token  |
| AUTH_010   | PasswordMismatchException   | 400         | Current password is incorrect |

---

### 4.5 Utility Functions

**File:** `backend/auth/utils.py`

Uses bcrypt directly (not via passlib) for password hashing:

```python
import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    # Truncate to 72 bytes (bcrypt limit)
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """Hash a plain password using bcrypt."""
    # Truncate to 72 bytes (bcrypt limit)
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')
```

---

### 4.6 Dependencies

**File:** `backend/auth/dependencies.py`

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token, db) -> models.User:
    """Dependency to get the current authenticated user."""
    # Validates JWT token
    # Returns User object or raises exception

async def get_current_active_verified_user(current_user) -> models.User:
    """Dependency to get current user who is both active and verified."""
    # Additional check for is_verified
```

---

### 4.7 API Router

**File:** `backend/auth/router.py`

All routes are prefixed with `/auth` and tagged with `Authentication`.

---

## 5. API Endpoints Reference

### 5.1 Endpoints Summary

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

### 5.2 Request/Response Examples

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

---

## 6. Testing & Verification

### 6.1 Test Cases (20 Total)

#### Registration Flow (5 tests)

| #   | Test Case                     | Expected Result                 |
| --- | ----------------------------- | ------------------------------- |
| 1   | Register with valid data      | 201, OTP returned               |
| 2   | Register with duplicate email | 400, "Email already registered" |
| 3   | Register with weak password   | 422, Validation error           |
| 4   | Register with invalid email   | 422, Validation error           |
| 5   | Register with empty full name | 422, Validation error           |

#### OTP Verification Flow (5 tests)

| #   | Test Case                  | Expected Result         |
| --- | -------------------------- | ----------------------- |
| 6   | Verify with correct OTP    | 200, "Email verified"   |
| 7   | Verify with wrong OTP      | 400, "Invalid OTP"      |
| 8   | Verify with expired OTP    | 400, "OTP has expired"  |
| 9   | Verify with wrong OTP type | 400, "Invalid OTP type" |
| 10  | Resend OTP                 | 200, New OTP returned   |

#### Login Flow (4 tests)

| #   | Test Case                 | Expected Result              |
| --- | ------------------------- | ---------------------------- |
| 11  | Login before verification | 403, "Email not verified"    |
| 12  | Login after verification  | 200, Token returned          |
| 13  | Login with wrong password | 401, "Invalid credentials"   |
| 14  | Login with inactive user  | 403, "User account inactive" |

#### Password Reset Flow (4 tests)

| #   | Test Case                      | Expected Result                    |
| --- | ------------------------------ | ---------------------------------- |
| 15  | Forgot password (existing)     | 200, OTP returned                  |
| 16  | Forgot password (non-existing) | 200, Same message (protection)     |
| 17  | Reset with valid OTP           | 200, "Password reset successfully" |
| 18  | Reset with wrong OTP type      | 400, "Invalid OTP type"            |

#### Change Password Flow (2 tests)

| #   | Test Case                        | Expected Result                   |
| --- | -------------------------------- | --------------------------------- |
| 19  | Change with correct old password | 200, "Password changed"           |
| 20  | Change with wrong old password   | 400, "Current password incorrect" |

### 6.2 Running the Application

```bash
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Start the server
python main.py

# Or with uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Access API docs
# http://localhost:8000/docs
```

---

## 7. Progress Tracking

### Implementation Checklist

- [x] **Database Setup**

  - [x] MySQL 8+ on Aiven Cloud configured
  - [x] PyMySQL driver configured
  - [x] Connection pooling configured

- [x] **Core Implementation**

  - [x] `db/database.py` - MySQL connection
  - [x] `db/models.py` - User model with OTP fields + Stripe integration
  - [x] `db/schemas.py` - Pydantic schemas with validators
  - [x] `auth/exceptions.py` - Custom exceptions
  - [x] `auth/utils.py` - Password (bcrypt), JWT, OTP utilities
  - [x] `auth/dependencies.py` - FastAPI dependencies
  - [x] `auth/router.py` - API endpoints

- [x] **Integration**

  - [x] Auth router included in main.py
  - [x] Exception handlers registered
  - [x] CORS configured for frontend

- [x] **Email Service**

  - [x] Brevo integration (`email_services/` module)
  - [x] Email templates (OTP, Welcome, Password Changed)
  - [x] Auth router updated with email sending
  - [ ] Remove OTP from responses (for production)
  - [ ] Send OTP via email on registration
  - [ ] Send OTP via email on forgot password
  - [ ] Send OTP via email on resend OTP

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

## Changes from Original Spec

| Item                | Original               | Current                                 |
| ------------------- | ---------------------- | --------------------------------------- |
| DB Driver           | mysql-connector-python | PyMySQL (pymysql)                       |
| Password Hashing    | passlib[bcrypt]        | bcrypt direct (with 72-byte truncation) |
| Password Max Length | 128                    | 72 (bcrypt limit)                       |
| Database Host       | Local MySQL            | Aiven Cloud MySQL                       |
| User Model          | Basic auth fields      | + stripe_customer_id, relationships     |
| Schemas             | Auth only              | + Billing schemas                       |

---

**Status**: ✅ Core authentication implemented. ⏳ Email service integration pending.
