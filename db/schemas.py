"""
Pydantic schemas with built-in validators for input validation.
All validation logic is centralized here - route handlers stay clean.
"""
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime
from enum import Enum
import re


# ============================================================================
# CONSTANTS & ENUMS
# ============================================================================

class OTPTypeEnum(str, Enum):
    """Valid OTP types."""
    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"


class TaskStatusEnum(str, Enum):
    """Task status enumeration for V2.1."""
    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


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


# ============================================================================
# BILLING SCHEMAS
# ============================================================================

class CreditPackage(BaseModel):
    """Credit package schema for purchase options."""
    package_id: str = Field(..., description="Unique package identifier")
    credits: int = Field(..., gt=0, description="Number of credits in package")
    stripe_price_id: str = Field(..., description="Stripe Price ID")
    amount_cents: int = Field(..., gt=0, description="Price in cents")
    currency: str = Field(default="usd", description="Currency code")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "package_id": "pack_5k",
                    "credits": 5000,
                    "stripe_price_id": "price_xxx",
                    "amount_cents": 4499,
                    "currency": "usd"
                }
            ]
        }
    }


class PackagesResponse(BaseModel):
    """Response schema for available credit packages."""
    packages: List["CreditPackage"]


class CheckoutRequest(BaseModel):
    """Request schema for creating checkout session."""
    package_id: str = Field(..., description="Package ID to purchase")

    @field_validator("package_id")
    @classmethod
    def validate_package_id(cls, v: str) -> str:
        """Validate package_id is not empty."""
        if not v or not v.strip():
            raise ValueError("Package ID is required")
        return v.strip()


class CheckoutResponse(BaseModel):
    """Response schema for checkout session creation."""
    checkout_url: str = Field(..., description="Stripe checkout URL")
    session_id: str = Field(..., description="Stripe session ID")


class TransactionResponse(BaseModel):
    """Response schema for a credit transaction."""
    id: str  # ULID format (26 chars)
    delta_credits: int
    type: str
    reason: Optional[str] = None
    agent_id: Optional[str] = None
    tool_id: Optional[str] = None
    analysis_id: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


class WalletResponse(BaseModel):
    """Response schema for wallet information."""
    balance_credits: int = Field(..., description="Current credit balance")
    status: str = Field(default="active", description="Wallet status")
    recent_transactions: List[TransactionResponse] = Field(
        default_factory=list,
        description="Recent transactions"
    )


class AgentCostResponse(BaseModel):
    """Response schema for agent cost."""
    agent_id: str
    cost: int
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class AgentCostsListResponse(BaseModel):
    """Response schema for listing agent costs."""
    agent_costs: List[AgentCostResponse]


class UpdateAgentCostRequest(BaseModel):
    """Request schema for updating agent cost."""
    cost: int = Field(..., gt=0, description="New cost in credits")


class AdminGrantRequest(BaseModel):
    """Request schema for admin credit grant."""
    user_id: int = Field(..., description="User ID to grant credits to")
    amount_credits: int = Field(..., description="Amount of credits to grant (can be negative for deduction)")
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for grant")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate reason is not empty."""
        if not v or not v.strip():
            raise ValueError("Reason is required")
        return v.strip()


class AdminGrantResponse(BaseModel):
    """Response schema for admin credit grant."""
    new_balance: int
    transaction_id: str  # ULID format (26 chars)


class BillingErrorResponse(BaseModel):
    """Error response schema for billing errors."""
    detail: str
    error_code: str
    context: Optional[dict] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detail": "Insufficient credits for agent execution",
                    "error_code": "BILLING_INSUFFICIENT_CREDITS",
                    "context": {
                        "agent_id": "semantic-mapper",
                        "required": 50,
                        "available": 10
                    }
                }
            ]
        }
    }


# ============================================================================
# TASK SCHEMAS (V2.1)
# ============================================================================

class TaskCreateRequest(BaseModel):
    """
    Request schema for creating a task (V2.1).
    
    Note: Parameters are NOT included here - they're uploaded to S3 separately.
    """
    tool_id: str = Field(..., description="Tool identifier: profile-my-data, clean-my-data, master-my-data")
    agents: Optional[List[str]] = Field(None, description="Agent IDs to run (defaults to tool's available_agents)")

    @field_validator('tool_id')
    @classmethod
    def validate_tool_id(cls, v: str) -> str:
        """Validate tool_id is valid."""
        valid_tools = ['profile-my-data', 'clean-my-data', 'master-my-data']
        if v not in valid_tools:
            raise ValueError(f"Invalid tool_id. Must be one of: {valid_tools}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tool_id": "profile-my-data",
                    "agents": ["unified-profiler", "score-risk"]
                }
            ]
        }
    }


class FileMetadata(BaseModel):
    """File metadata for upload URL generation."""
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(default="text/csv", description="MIME type")


class UploadUrlsRequest(BaseModel):
    """Request schema for getting upload URLs."""
    files: Dict[str, FileMetadata] = Field(..., description="Files to upload: {primary: {...}, baseline: {...}}")
    has_parameters: bool = Field(default=False, description="Whether to include parameters URL")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "files": {
                        "primary": {"filename": "data.csv", "content_type": "text/csv"},
                        "baseline": {"filename": "baseline.csv", "content_type": "text/csv"}
                    },
                    "has_parameters": True
                }
            ]
        }
    }


class UploadUrlInfo(BaseModel):
    """Upload URL information."""
    url: str = Field(..., description="Presigned upload URL")
    key: str = Field(..., description="S3 object key")
    method: str = Field(default="PUT", description="HTTP method to use")
    headers: Dict[str, str] = Field(..., description="Headers to include in upload request")
    expires_at: datetime = Field(..., description="URL expiration time")


class UploadUrlsResponse(BaseModel):
    """Response with presigned upload URLs."""
    task_id: str
    status: str
    uploads: Dict[str, UploadUrlInfo] = Field(..., description="Upload URLs for each file")
    expires_in_seconds: int = Field(default=900, description="URL expiration in seconds")
    message: str

    model_config = {"from_attributes": True}


class FileVerification(BaseModel):
    """File verification info."""
    key: str
    size_bytes: int
    verified_at: str


class ProcessResponse(BaseModel):
    """Response for process trigger."""
    task_id: str
    status: str
    message: str
    files_verified: Optional[Dict[str, FileVerification]] = None


class ProgressDetail(BaseModel):
    """Detailed progress information."""
    current_agent: Optional[str] = None
    agents_total: int
    agents_completed: int


class TaskResponse(BaseModel):
    """
    Response schema for task status.
    
    Note: Full results are NOT included - use /downloads endpoint.
    """
    task_id: str
    status: TaskStatusEnum
    tool_id: str
    agents: List[str]
    progress: int = Field(default=0, ge=0, le=100)

    # Timestamps
    created_at: datetime
    upload_started_at: Optional[datetime] = None
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None

    # Results availability
    downloads_available: bool = Field(default=False, description="Whether downloads are ready")
    execution_time_ms: Optional[int] = None

    # Error info (when failed)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Optional message
    message: Optional[str] = None

    model_config = {"from_attributes": True}


class TaskCreateResponse(BaseModel):
    """Response for task creation."""
    task_id: str
    status: TaskStatusEnum
    tool_id: str
    agents: List[str]
    created_at: datetime
    message: str

    model_config = {"from_attributes": True}


class DownloadInfo(BaseModel):
    """Download file information."""
    download_id: str = Field(..., description="Unique download identifier")
    filename: str = Field(..., description="Original filename")
    type: str = Field(..., description="File type: report, data")
    mime_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="File size in bytes")
    url: str = Field(..., description="Presigned download URL")
    expires_at: datetime = Field(..., description="URL expiration time")


class DownloadsResponse(BaseModel):
    """Response with download URLs."""
    task_id: str
    downloads: List[DownloadInfo] = Field(default_factory=list)
    expires_in_seconds: int = Field(default=3600, description="URL expiration in seconds")


class TaskListItem(BaseModel):
    """Task item for list response (minimal info)."""
    task_id: str
    status: TaskStatusEnum
    tool_id: str
    progress: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginationInfo(BaseModel):
    """Pagination information."""
    total: int
    limit: int
    offset: int
    has_more: bool


class TaskListResponse(BaseModel):
    """Response for listing tasks."""
    tasks: List[TaskListItem]
    pagination: PaginationInfo


class TaskCancelResponse(BaseModel):
    """Response for task cancellation."""
    task_id: str
    status: TaskStatusEnum
    message: str
    cancelled_at: Optional[datetime] = None


class TaskDeleteResponse(BaseModel):
    """Response for task deletion."""
    task_id: str
    message: str
    files_deleted: int = Field(default=0, description="Number of S3 files deleted")


class TaskReportResponse(BaseModel):
    """
    Response schema for task report (V2.1).
    
    Returns the complete analysis report in the format expected by the results page.
    This is used by ResultWrapper2 to display completed task results.
    """
    analysis_id: str = Field(..., description="Task/Analysis ID")
    tool: str = Field(..., description="Tool identifier")
    status: str = Field(default="success", description="Analysis status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    execution_time_ms: Optional[int] = Field(None, description="Execution time in milliseconds")
    report: Dict[str, Any] = Field(..., description="Complete analysis report with all agent outputs")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
                    "tool": "clean-my-data",
                    "status": "success",
                    "timestamp": "2025-12-20T10:00:00Z",
                    "execution_time_ms": 15000,
                    "report": {
                        "alerts": [],
                        "issues": [],
                        "recommendations": [],
                        "executiveSummary": [],
                        "analysisSummary": {},
                        "downloads": []
                    }
                }
            ]
        }
    }
