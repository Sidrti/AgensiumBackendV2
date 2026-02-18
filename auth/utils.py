"""
Utility functions for authentication.
Includes password hashing, JWT handling, and OTP generation.
"""
import os
import random
import string
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from dotenv import load_dotenv
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")


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
    # Truncate to 72 bytes (bcrypt limit)
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """
    Hash a plain password using bcrypt.

    Args:
        password: The plain text password to hash

    Returns:
        The hashed password string
    """
    # Truncate to 72 bytes (bcrypt limit)
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


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


# ============================================================================
# GOOGLE OAUTH FUNCTIONS
# ============================================================================

def verify_google_token(credential: str) -> dict:
    """
    Verify a Google ID token and extract user info.

    Args:
        credential: The Google ID token (JWT) from the frontend

    Returns:
        Dict with: email, name, sub (google_id), picture, email_verified

    Raises:
        ValueError: If the token is invalid, expired, or audience doesn't match
    """
    if not GOOGLE_CLIENT_ID:
        raise ValueError("Google Client ID is not configured on the server")

    idinfo = google_id_token.verify_oauth2_token(
        credential,
        google_requests.Request(),
        GOOGLE_CLIENT_ID
    )

    # Verify the issuer
    if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
        raise ValueError("Invalid token issuer")

    return {
        "email": idinfo.get("email", "").lower(),
        "name": idinfo.get("name", ""),
        "google_id": idinfo.get("sub"),
        "picture": idinfo.get("picture"),
        "email_verified": idinfo.get("email_verified", False),
    }
