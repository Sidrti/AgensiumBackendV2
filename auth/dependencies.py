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

    print(f"User found: {user.email}, Active: {user.is_active}, Verified: {user.is_verified}")
    print(f"User ID: {user.id}, Created at: {user.created_at}")

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
