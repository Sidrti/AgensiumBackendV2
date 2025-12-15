"""
Email service using Brevo (Sendinblue) for transactional emails.
"""
import os
import logging
from typing import Optional, Dict, Any
from enum import Enum

from dotenv import load_dotenv

from email_services.email_templates import get_otp_template, get_welcome_template, get_password_changed_template
from email_services.email_config import EmailConfig

load_dotenv()
logger = logging.getLogger(__name__)

# Try to import Brevo SDK, handle if not installed
try:
    import sib_api_v3_sdk
    from sib_api_v3_sdk.rest import ApiException
    BREVO_AVAILABLE = True
except ImportError:
    BREVO_AVAILABLE = False
    logger.warning("⚠ sib-api-v3-sdk not installed. Email service will be disabled.")
    logger.warning("  Install with: pip install sib-api-v3-sdk")


class EmailType(str, Enum):
    """Email types supported by the service."""
    OTP_REGISTRATION = "otp_registration"
    OTP_PASSWORD_RESET = "otp_password_reset"
    WELCOME = "welcome"
    PASSWORD_CHANGED = "password_changed"


class EmailService:
    """
    Email service for sending transactional emails via Brevo.
    
    Usage:
        email_service = EmailService()
        await email_service.send_otp_email(
            to_email="user@example.com",
            to_name="John Doe",
            otp_code="123456",
            otp_type="registration"
        )
    """

    def __init__(self):
        """Initialize Brevo API client."""
        self.config = EmailConfig()
        self.api_key = os.getenv("BREVO_API_KEY")
        self.sender_email = os.getenv("BREVO_SENDER_EMAIL", "noreply@agensium.com")
        self.sender_name = os.getenv("BREVO_SENDER_NAME", "Agensium")
        self.enabled = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
        self.debug = os.getenv("EMAIL_DEBUG", "false").lower() == "true"
        self.api_instance = None

        if not BREVO_AVAILABLE:
            logger.warning("⚠ Brevo SDK not available - emails will not be sent")
            return

        if self.api_key and self.enabled:
            try:
                configuration = sib_api_v3_sdk.Configuration()
                configuration.api_key['api-key'] = self.api_key
                self.api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
                    sib_api_v3_sdk.ApiClient(configuration)
                )
                logger.info("✓ Brevo email service initialized")
            except Exception as e:
                logger.error(f"✗ Failed to initialize Brevo: {e}")
                self.api_instance = None
        else:
            if not self.enabled:
                logger.info("ℹ Email service is disabled (EMAIL_ENABLED=false)")
            elif not self.api_key:
                logger.warning("⚠ BREVO_API_KEY not set - emails will not be sent")

    def _is_available(self) -> bool:
        """Check if email service is available."""
        return self.api_instance is not None and self.enabled and BREVO_AVAILABLE

    async def send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        tags: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Send a transactional email via Brevo.

        Args:
            to_email: Recipient email address
            to_name: Recipient name
            subject: Email subject
            html_content: HTML body content
            text_content: Plain text body (optional)
            tags: Tags for email tracking (optional)

        Returns:
            Dict with status and message_id or error
        """
        if not self._is_available():
            logger.warning(f"Email not sent (service unavailable): {subject} to {to_email}")
            return {
                "success": False,
                "error": "Email service not available",
                "email": to_email
            }

        if self.debug:
            logger.info(f"[DEBUG] Would send email: {subject} to {to_email}")
            logger.debug(f"[DEBUG] HTML Content length: {len(html_content)} chars")
            return {
                "success": True,
                "message_id": "debug-mode",
                "email": to_email,
                "debug": True
            }

        try:
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                sender=sib_api_v3_sdk.SendSmtpEmailSender(
                    email=self.sender_email,
                    name=self.sender_name
                ),
                to=[sib_api_v3_sdk.SendSmtpEmailTo(
                    email=to_email,
                    name=to_name
                )],
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                tags=tags or []
            )

            api_response = self.api_instance.send_transac_email(send_smtp_email)
            
            logger.info(f"✓ Email sent: {subject} to {to_email} (ID: {api_response.message_id})")
            return {
                "success": True,
                "message_id": api_response.message_id,
                "email": to_email
            }

        except ApiException as e:
            logger.error(f"✗ Failed to send email to {to_email}: {e}")
            return {
                "success": False,
                "error": str(e),
                "email": to_email
            }
        except Exception as e:
            logger.error(f"✗ Unexpected error sending email to {to_email}: {e}")
            return {
                "success": False,
                "error": str(e),
                "email": to_email
            }

    async def send_otp_email(
        self,
        to_email: str,
        to_name: str,
        otp_code: str,
        otp_type: str
    ) -> Dict[str, Any]:
        """
        Send an OTP email for registration or password reset.

        Args:
            to_email: Recipient email address
            to_name: Recipient name
            otp_code: 6-digit OTP code
            otp_type: 'registration' or 'password_reset'

        Returns:
            Dict with send status
        """
        expiry_minutes = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))
        
        # Get appropriate template
        html_content = get_otp_template(
            user_name=to_name,
            otp_code=otp_code,
            otp_type=otp_type,
            expiry_minutes=expiry_minutes
        )

        # Set subject based on OTP type
        if otp_type == "registration":
            subject = f"Verify your Agensium account - OTP: {otp_code}"
            email_type = EmailType.OTP_REGISTRATION
        else:
            subject = f"Reset your Agensium password - OTP: {otp_code}"
            email_type = EmailType.OTP_PASSWORD_RESET

        return await self.send_email(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            html_content=html_content,
            tags=[email_type.value, "otp", "auth"]
        )

    async def send_welcome_email(
        self,
        to_email: str,
        to_name: str
    ) -> Dict[str, Any]:
        """
        Send a welcome email after successful verification.

        Args:
            to_email: Recipient email address
            to_name: Recipient name

        Returns:
            Dict with send status
        """
        html_content = get_welcome_template(user_name=to_name)
        subject = f"Welcome to Agensium, {to_name}!"

        return await self.send_email(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            html_content=html_content,
            tags=[EmailType.WELCOME.value, "onboarding"]
        )

    async def send_password_changed_email(
        self,
        to_email: str,
        to_name: str
    ) -> Dict[str, Any]:
        """
        Send a notification email when password is changed.

        Args:
            to_email: Recipient email address
            to_name: Recipient name

        Returns:
            Dict with send status
        """
        html_content = get_password_changed_template(user_name=to_name)
        subject = "Your Agensium password has been changed"

        return await self.send_email(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            html_content=html_content,
            tags=[EmailType.PASSWORD_CHANGED.value, "security"]
        )


# Global instance for dependency injection
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Dependency to get email service instance (singleton)."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
