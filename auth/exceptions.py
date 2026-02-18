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
        # Keep WWW-Authenticate header but avoid sending OTP via headers for now.
        headers = {"WWW-Authenticate": "Bearer"}

        detail = (
            "Email not verified. An OTP has been sent to your email — "
            "please verify it to login."
        )
        if otp:
            # For now include the OTP in the detail message (useful for testing/debugging).
            detail = f"{detail} OTP: {otp}"

        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
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


class GoogleAuthException(AuthException):
    """Exception for Google OAuth errors."""

    def __init__(self, detail: str = "Google authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="AUTH_011",
            headers={"WWW-Authenticate": "Bearer"}
        )


class GoogleAccountNoPasswordException(AuthException):
    """Exception when a Google-only user tries an action requiring a password."""

    def __init__(self, detail: str = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail or "This account uses Google Sign-In. Please use 'Continue with Google' to login.",
            error_code="AUTH_012"
        )
