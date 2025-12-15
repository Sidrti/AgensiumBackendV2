"""
Email configuration and constants.
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class EmailConfig:
    """Email service configuration."""
    
    # Brevo settings
    api_key: Optional[str] = field(default=None)
    sender_email: str = field(default="noreply@agensium.com")
    sender_name: str = field(default="Agensium")
    
    # Feature flags
    enabled: bool = field(default=True)
    debug: bool = field(default=False)
    
    # OTP settings
    otp_expire_minutes: int = field(default=10)
    
    # Rate limiting
    max_emails_per_hour: int = field(default=10)
    max_resend_per_hour: int = field(default=3)
    
    def __post_init__(self):
        """Load configuration from environment."""
        self.api_key = os.getenv("BREVO_API_KEY")
        self.sender_email = os.getenv("BREVO_SENDER_EMAIL", self.sender_email)
        self.sender_name = os.getenv("BREVO_SENDER_NAME", self.sender_name)
        self.enabled = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
        self.debug = os.getenv("EMAIL_DEBUG", "false").lower() == "true"
        self.otp_expire_minutes = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))

    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return bool(self.api_key) and self.enabled

    def __repr__(self) -> str:
        """String representation (hide API key)."""
        api_status = "configured" if self.api_key else "not configured"
        return (
            f"EmailConfig(api_key={api_status}, "
            f"sender={self.sender_email}, "
            f"enabled={self.enabled}, "
            f"debug={self.debug})"
        )


# Global config instance
email_config = EmailConfig()
