"""
Authentication API routes.
All input validation is handled by Pydantic schemas - routes stay clean.
"""
import logging
from fastapi import APIRouter, Depends, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from db.database import get_db
from db import models, schemas
from email_services.email_service import EmailService, get_email_service
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

logger = logging.getLogger(__name__)

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
async def register_user(
    user: schemas.UserCreate,  # Validation happens here automatically!
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service)
):
    """
    Register a new user with email verification.

    - Validates input via Pydantic schema
    - Checks for duplicate email
    - Creates user with is_verified=False
    - Sends OTP via email for verification
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

    # Send OTP via email (non-blocking)
    background_tasks.add_task(
        email_service.send_otp_email,
        to_email=db_user.email,
        to_name=db_user.full_name,
        otp_code=otp_code,
        otp_type="registration"
    )

    return schemas.RegisterResponse(
        id=db_user.id,
        email=db_user.email,
        full_name=db_user.full_name,
        is_active=db_user.is_active,
        message="Registration successful. Please check your email for the OTP.",
        otp=otp_code,  # TODO: Remove in production - only for testing
        otp_type="registration"
    )


@router.post(
    "/verify-otp",
    response_model=schemas.GenericResponse,
    summary="Verify OTP",
    description="Verify OTP for email verification or password reset."
)
async def verify_otp(
    data: schemas.VerifyOTP,  # Validation happens here automatically!
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service)
):
    """
    Verify OTP for registration or password reset.

    - Validates OTP format via Pydantic
    - Checks OTP existence and expiry
    - Validates OTP type matches expected flow
    - For registration: marks user as verified and sends welcome email
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

        # Send welcome email (non-blocking)
        background_tasks.add_task(
            email_service.send_welcome_email,
            to_email=user.email,
            to_name=user.full_name
        )

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
async def resend_otp(
    data: schemas.ResendOTP,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service)
):
    """
    Resend OTP to user's email.

    - Generates new OTP
    - Updates expiry time
    - Sends OTP via email
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

    # Send OTP via email (non-blocking)
    background_tasks.add_task(
        email_service.send_otp_email,
        to_email=user.email,
        to_name=user.full_name,
        otp_code=otp_code,
        otp_type=data.otp_type
    )

    return schemas.GenericResponse(
        message="OTP sent to your email.",
        otp=otp_code,  # TODO: Remove in production
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
async def forgot_password(
    data: schemas.ForgotPassword,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service)
):
    """
    Request password reset OTP.

    - Generates password_reset type OTP
    - Sends OTP via email
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

    # Send OTP via email (non-blocking)
    background_tasks.add_task(
        email_service.send_otp_email,
        to_email=user.email,
        to_name=user.full_name,
        otp_code=otp_code,
        otp_type="password_reset"
    )

    return schemas.GenericResponse(
        message="Password reset OTP sent to your email.",
        otp=otp_code,  # TODO: Remove in production
        otp_type="password_reset"
    )


@router.post(
    "/reset-password",
    response_model=schemas.GenericResponse,
    summary="Reset password",
    description="Reset password using OTP."
)
async def reset_password(
    data: schemas.ResetPassword,  # Password validation via Pydantic!
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service)
):
    """
    Reset password using OTP.

    - Validates new password via Pydantic schema
    - Verifies OTP is valid and correct type
    - Updates password and clears OTP fields
    - Sends password changed notification email
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

    # Send password changed notification (non-blocking)
    background_tasks.add_task(
        email_service.send_password_changed_email,
        to_email=user.email,
        to_name=user.full_name
    )

    return schemas.GenericResponse(
        message="Password reset successfully. Please login with your new password."
    )


@router.post(
    "/change-password",
    response_model=schemas.GenericResponse,
    summary="Change password",
    description="Change password for logged-in user."
)
async def change_password(
    data: schemas.ChangePassword,  # Validates old != new via Pydantic!
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service)
):
    """
    Change password for authenticated user.

    - Verifies current password
    - Validates new password via Pydantic (including old != new check)
    - Updates password
    - Sends password changed notification email
    """
    if not utils.verify_password(data.old_password, current_user.hashed_password):
        raise PasswordMismatchException()

    current_user.hashed_password = utils.get_password_hash(data.new_password)
    db.commit()

    # Send password changed notification (non-blocking)
    background_tasks.add_task(
        email_service.send_password_changed_email,
        to_email=current_user.email,
        to_name=current_user.full_name
    )

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
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service)
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
