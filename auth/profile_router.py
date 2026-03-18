"""
Profile API routes.
Handles all operations related to user profiles.
"""
import logging
import re
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from db import models, schemas
from auth import dependencies
from auth.exceptions import (
    ProfileNotFoundException,
    HandleTakenException,
    InvalidHandleException
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["User Profile"])


# ============================================================================
# PROFILE MANGEMENT
# ============================================================================

@router.get(
    "/me",
    response_model=schemas.CombinedProfileResponse,
    summary="Get full profile",
    description="Get the current authenticated user along with their extended profile."
)
async def get_my_profile(
    current_user: models.User = Depends(dependencies.get_current_user)
):
    """
    Get the current authenticated user's profile.

    - Requires valid JWT token
    - Returns combined user and profile data
    """
    profile = current_user.profile
    return schemas.CombinedProfileResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        auth_provider=current_user.auth_provider,
        profile_picture=current_user.profile_picture,
        
        display_name=profile.display_name if profile else None,
        public_handle=profile.public_handle if profile else None,
        company_name=profile.company_name if profile else None,
        industry_vertical=profile.industry_vertical if profile else None,
        business_email=profile.business_email if profile else None,
        
        message="Profile retrieved successfully"
    )


@router.put(
    "/me",
    response_model=schemas.CombinedProfileResponse,
    summary="Update profile",
    description="Update the current user's profile information."
)
async def update_my_profile(
    data: schemas.ProfileUpdate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update profile details for the authenticated user.

    - Modifies fields conditionally if they are provided
    - Validates uniqueness if public_handle is changed
    - Returns updated profile data
    """
    profile = current_user.profile
    if not profile:
        raise ProfileNotFoundException()

    # If updating handle, verify uniqueness
    if data.public_handle and data.public_handle != profile.public_handle:
        # Clean the input handle
        cleaned_handle = data.public_handle.lower().strip()
        cleaned_handle = re.sub(r'[^a-z0-9_]', '', cleaned_handle)
        
        if not cleaned_handle:
            raise InvalidHandleException()
            
        exists = db.query(models.Profile).filter(
            models.Profile.public_handle == cleaned_handle
        ).first()
        
        if exists:
            raise HandleTakenException()
            
        profile.public_handle = cleaned_handle

    if data.display_name is not None:
        profile.display_name = data.display_name
    if data.company_name is not None:
        profile.company_name = data.company_name
    if data.industry_vertical is not None:
        profile.industry_vertical = data.industry_vertical
    if data.business_email is not None:
        profile.business_email = data.business_email

    db.commit()
    db.refresh(profile)
    
    return schemas.CombinedProfileResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        auth_provider=current_user.auth_provider,
        profile_picture=current_user.profile_picture,
        
        display_name=profile.display_name,
        public_handle=profile.public_handle,
        company_name=profile.company_name,
        industry_vertical=profile.industry_vertical,
        business_email=profile.business_email,
        
        message="Profile updated successfully"
    )


@router.get(
    "/check-handle",
    response_model=schemas.HandleCheckResponse,
    summary="Check handle availability",
    description="Check if a specific handle string is available for claiming."
)
async def check_handle_availability(
    handle: str,
    db: Session = Depends(get_db)
):
    """
    Check if a specifically requested handle string is available.
    Useful for frontend forms throwing real-time validation warnings.

    - Cleans input handle formatting
    - Checks database for collisions
    - Returns boolean availability status
    """
    cleaned_handle = handle.lower().strip()
    cleaned_handle = re.sub(r'[^a-z0-9_]', '', cleaned_handle)
    
    if not cleaned_handle:
        return schemas.HandleCheckResponse(handle=handle, is_available=False)
        
    exists = db.query(models.Profile).filter(
        models.Profile.public_handle == cleaned_handle
    ).first()
    
    return schemas.HandleCheckResponse(
        handle=cleaned_handle,
        is_available=(exists is None)
    )
