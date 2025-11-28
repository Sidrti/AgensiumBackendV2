# Task: Migrate Authentication System from SQLite to MySQL

This document outlines the comprehensive plan to migrate the Agensium Backend authentication system from SQLite to MySQL 8+, with advanced features including OTP type differentiation for registration and password reset flows.

## 1. Overview

**Goal:** Implement a robust MySQL 8+ database solution for Agensium Backend authentication system with complete removal of SQLite dependency.

**Scope:**

- Configure database connection for MySQL (required, no fallback to SQLite).
- Refactor SQLAlchemy models for MySQL compatibility.
- Implement database migrations using Alembic.
- Implement OTP verification for registration.
- Implement Forgot Password and Reset Password flows with OTP type differentiation.
- Implement Change Password functionality.
- Verify authentication flows with enhanced security.

**Key Feature: OTP Type Differentiation**

- OTPs for registration are marked as `'registration'` type.
- OTPs for password reset are marked as `'password_reset'` type.
- System validates OTP type on verification to ensure correct flow usage.
- User cannot use a registration OTP for password reset and vice versa.

## 2. Prerequisites & Setup

### 2.1. Install Dependencies

```bash
pip install mysql-connector-python alembic
```

### 2.2. Environment Configuration

Create or update `.env` file:

```
DATABASE_URL=mysql+mysqlconnector://user:password@localhost:3306/agensium
SECRET_KEY=your-super-secret-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## 3. Implementation Steps

### Step 1: Update Database Connection (`backend/db/database.py`)

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# MySQL connection - REQUIRED env variable
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Please configure MySQL connection string.")

if "mysql" not in SQLALCHEMY_DATABASE_URL.lower():
    raise ValueError("Only MySQL database is supported. DATABASE_URL must contain mysql connection string.")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=3600    # Recycle connections every hour
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Step 2: Refactor Models for MySQL (`backend/db/models.py`)

```python
from sqlalchemy import Boolean, Column, Integer, String, DateTime
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))
    is_active = Column(Boolean, default=True)
    full_name = Column(String(100), nullable=True)

    # OTP & Verification Fields
    otp_code = Column(String(6), nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    otp_type = Column(String(50), nullable=True)  # 'registration' or 'password_reset'
    is_verified = Column(Boolean, default=False)
```

**Explanation:**

- `otp_type`: Stores the purpose of the OTP ('registration' or 'password_reset')
- `is_verified`: Tracks whether user's email has been verified
- User cannot login until `is_verified = True`

### Step 3: Initialize Migrations (Alembic)

```bash
cd backend
alembic init alembic
```

Edit `alembic/env.py`:

```python
from db.models import Base
from dotenv import load_dotenv
import os

load_dotenv()

# Inside run_migrations_online()
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))
target_metadata = Base.metadata
```

Apply migrations:

```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### Step 4: Update Schemas (`backend/db/schemas.py`)

```python
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class VerifyOTP(BaseModel):
    email: EmailStr
    otp: str
    otp_type: str = Field(..., description="'registration' or 'password_reset'")

class ForgotPassword(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    email: EmailStr
    otp: str
    new_password: str = Field(..., min_length=8)

class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

class GenericResponse(BaseModel):
    message: str
    otp: Optional[str] = None
    otp_type: Optional[str] = None
```

### Step 5: Update Utils (`backend/auth/utils.py`)

```python
import random
import string

def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return "".join(random.choices(string.digits, k=6))

# ... existing code for password hashing and JWT ...
```

### Step 6: Update Router (`backend/auth/router.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from db import database, models, schemas
from . import utils, dependencies

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=schemas.RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    """Register a new user with OTP verification."""
    # Field validation
    if not user.email or not user.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")

    if not user.password or not user.password.strip():
        raise HTTPException(status_code=400, detail="Password is required")

    if not user.full_name or not user.full_name.strip():
        raise HTTPException(status_code=400, detail="Full name is required")

    # Password validation
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")

    if not any(char.isupper() for char in user.password):
        raise HTTPException(status_code=400, detail="Password must contain at least one uppercase letter")

    if not any(char.islower() for char in user.password):
        raise HTTPException(status_code=400, detail="Password must contain at least one lowercase letter")

    if not any(char.isdigit() for char in user.password):
        raise HTTPException(status_code=400, detail="Password must contain at least one digit")

    if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?" for char in user.password):
        raise HTTPException(status_code=400, detail="Password must contain at least one special character")

    # Check duplicate email
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        otp_code = utils.generate_otp()
        otp_expires_at = datetime.utcnow() + timedelta(minutes=10)

        db_user = models.User(
            email=user.email,
            hashed_password=utils.get_password_hash(user.password),
            full_name=user.full_name,
            otp_code=otp_code,
            otp_expires_at=otp_expires_at,
            otp_type="registration",
            is_verified=False
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        return {
            "id": db_user.id,
            "email": db_user.email,
            "full_name": db_user.full_name,
            "is_active": db_user.is_active,
            "message": "User registered. Verify OTP to login.",
            "otp": otp_code,
            "otp_type": "registration"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Registration failed")

@router.post("/verify-otp", response_model=schemas.GenericResponse)
def verify_otp(data: schemas.VerifyOTP, db: Session = Depends(database.get_db)):
    """Verify OTP for registration or password reset."""
    user = db.query(models.User).filter(models.User.email == data.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.otp_code or user.otp_code != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if user.otp_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP has expired")

    if user.otp_type != data.otp_type:
        raise HTTPException(status_code=400, detail=f"Invalid OTP type. Expected '{user.otp_type}', got '{data.otp_type}'")

    try:
        if data.otp_type == "registration":
            user.is_verified = True
            user.otp_code = None
            user.otp_expires_at = None
            user.otp_type = None
            db.commit()
            return {"message": "Email verified. You can now login."}

        elif data.otp_type == "password_reset":
            return {"message": "OTP verified. Proceed to reset password."}

        else:
            raise HTTPException(status_code=400, detail="Unknown OTP type")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="OTP verification failed")

@router.post("/forgot-password", response_model=schemas.GenericResponse)
def forgot_password(data: schemas.ForgotPassword, db: Session = Depends(database.get_db)):
    """Request password reset OTP."""
    user = db.query(models.User).filter(models.User.email == data.email).first()

    if not user:
        return {"message": "If email exists, OTP will be sent."}  # User enumeration protection

    try:
        otp_code = utils.generate_otp()
        user.otp_code = otp_code
        user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
        user.otp_type = "password_reset"
        db.commit()

        return {
            "message": "OTP sent to your email.",
            "otp": otp_code,
            "otp_type": "password_reset"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to generate OTP")

@router.post("/reset-password", response_model=schemas.GenericResponse)
def reset_password(data: schemas.ResetPassword, db: Session = Depends(database.get_db)):
    """Reset password using OTP."""
    # Validate new password field
    if not data.new_password or not data.new_password.strip():
        raise HTTPException(status_code=400, detail="New password is required")

    # Password validation
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")

    if not any(char.isupper() for char in data.new_password):
        raise HTTPException(status_code=400, detail="Password must contain at least one uppercase letter")

    if not any(char.islower() for char in data.new_password):
        raise HTTPException(status_code=400, detail="Password must contain at least one lowercase letter")

    if not any(char.isdigit() for char in data.new_password):
        raise HTTPException(status_code=400, detail="Password must contain at least one digit")

    if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?" for char in data.new_password):
        raise HTTPException(status_code=400, detail="Password must contain at least one special character")

    user = db.query(models.User).filter(models.User.email == data.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.otp_code or user.otp_code != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if user.otp_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP has expired")

    if user.otp_type != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid OTP type for password reset")

    try:
        user.hashed_password = utils.get_password_hash(data.new_password)
        user.otp_code = None
        user.otp_expires_at = None
        user.otp_type = None
        db.commit()

        return {"message": "Password reset successfully. Login with new password."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to reset password")

@router.post("/change-password", response_model=schemas.GenericResponse)
def change_password(data: schemas.ChangePassword, current_user: models.User = Depends(dependencies.get_current_user), db: Session = Depends(database.get_db)):
    """Change password for logged-in user."""
    if not utils.verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Old password is incorrect")

    try:
        current_user.hashed_password = utils.get_password_hash(data.new_password)
        db.commit()
        return {"message": "Password changed successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to change password")

@router.post("/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    """Login to get access token."""
    user = db.query(models.User).filter(models.User.email == form_data.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not utils.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    # If email not verified, generate new OTP and return it
    if not user.is_verified:
        try:
            otp_code = utils.generate_otp()
            otp_expires_at = datetime.utcnow() + timedelta(minutes=10)

            user.otp_code = otp_code
            user.otp_expires_at = otp_expires_at
            user.otp_type = "registration"
            db.commit()

            raise HTTPException(
                status_code=403,
                detail="Email not verified. OTP sent to your email.",
                headers={"X-OTP": otp_code, "X-OTP-Type": "registration"}
            )
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to generate OTP")

    access_token_expires = timedelta(minutes=utils.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = utils.create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": utils.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_email": user.email
    }

@router.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(dependencies.get_current_user)):
    """Get current user profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "message": "User profile retrieved successfully"
    }
```

## 4. Testing & Verification

### 4.1. Test Cases (16 Total)

1. ✅ **Register User** → Returns OTP with `otp_type: "registration"`
2. ✅ **Login Before OTP Verification** → 403 Forbidden
3. ✅ **Verify OTP (Registration)** → Sets `is_verified = True`
4. ✅ **Login After Verification** → 200 OK, Token returned
5. ✅ **Forgot Password** → Returns OTP with `otp_type: "password_reset"`
6. ✅ **Verify OTP (Password Reset)** → Verifies OTP but doesn't clear it
7. ✅ **Reset Password** → Updates password and clears OTP fields
8. ✅ **Login with New Password** → 200 OK, Token returned
9. ✅ **Change Password** → Updates password for logged-in user
10. ✅ **Get Profile** → Returns user details
11. ✅ **Invalid OTP Type Mismatch** → 400 Bad Request
12. ✅ **Expired OTP** → 400 Bad Request
13. ✅ **Duplicate Registration** → 400 Bad Request
14. ✅ **User Enumeration Protection** → Same response for non-existent email
15. ✅ **Invalid OTP** → 400 Bad Request
16. ✅ **Wrong Old Password on Change** → 400 Bad Request

### 4.2. Running Tests

```bash
# Start MySQL
docker-compose up -d db

# Run backend
uvicorn main:app --reload

# Use Postman or curl to test endpoints
```

## 5. Progress Tracking

- [ ] **Step 1**: Database connection updated for MySQL
- [ ] **Step 2**: Models refactored with `otp_type` field
- [ ] **Step 3**: Alembic migrations initialized and applied
- [ ] **Step 4**: Schemas updated with OTP type support
- [ ] **Step 5**: Utils updated with OTP generation
- [ ] **Step 6**: Router updated with all endpoints and OTP type logic
- [ ] **Login Endpoint**: Updated to check `is_verified` flag
- [ ] **Test Case 1-5**: Registration and initial OTP flow verified
- [ ] **Test Case 6-10**: Password reset and change flows verified
- [ ] **Test Case 11-16**: Edge cases and security scenarios verified
- [ ] **Production Ready**: All tests passed and security validated

---

**Status**: Comprehensive task.md created with OTP type differentiation. Ready for implementation.
