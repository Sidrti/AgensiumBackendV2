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
PASSWORD_MAX_LENGTH = 72  # bcrypt has a 72-byte limit
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


class TokenData(BaseModel):
    """Token data for internal use."""
    email: Optional[str] = None


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
