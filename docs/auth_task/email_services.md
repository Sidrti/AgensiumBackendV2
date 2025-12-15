# Task: Email Services Implementation with Brevo

A comprehensive guide for implementing transactional email services using Brevo (formerly Sendinblue) for OTP delivery and authentication-related emails.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Email Types & Templates](#3-email-types--templates)
4. [Implementation](#4-implementation)
   - [4.1 Project Structure](#41-project-structure)
   - [4.2 Environment Configuration](#42-environment-configuration)
   - [4.3 Email Service Module](#43-email-service-module)
   - [4.4 Email Templates](#44-email-templates)
   - [4.5 Integration with Auth Router](#45-integration-with-auth-router)
5. [API Reference](#5-api-reference)
6. [Error Handling](#6-error-handling)
7. [Testing](#7-testing)
8. [Production Considerations](#8-production-considerations)
9. [Progress Tracking](#9-progress-tracking)

---

## 1. Overview

### 1.1 Goal

Implement a robust email service for Agensium Backend to:

- Send OTP codes for user registration verification
- Send OTP codes for password reset
- Handle OTP resend requests
- Provide consistent, branded email templates
- Track email delivery status

### 1.2 Key Features

| Feature                   | Description                                         |
| ------------------------- | --------------------------------------------------- |
| **Brevo Integration**     | Use Brevo's Transactional Email API                 |
| **Template-Based Emails** | Pre-designed HTML templates for all email types     |
| **OTP Emails**            | Registration and password reset OTP delivery        |
| **Async Email Sending**   | Non-blocking email delivery                         |
| **Error Handling**        | Graceful fallback when email service is unavailable |
| **Rate Limiting**         | Prevent abuse of email endpoints                    |
| **Delivery Tracking**     | Track email status via Brevo webhooks (optional)    |

### 1.3 Email Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     REGISTRATION EMAIL FLOW                             │
├─────────────────────────────────────────────────────────────────────────┤
│  User Registers → Generate OTP → Send Email via Brevo → User Verifies  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                   PASSWORD RESET EMAIL FLOW                             │
├─────────────────────────────────────────────────────────────────────────┤
│  Forgot Password → Generate OTP → Send Email via Brevo → User Resets   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      RESEND OTP EMAIL FLOW                              │
├─────────────────────────────────────────────────────────────────────────┤
│  User Requests Resend → Generate New OTP → Send Email → User Verifies  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.4 Why Brevo?

- **Free Tier**: 300 emails/day on free plan
- **Reliable Delivery**: High deliverability rates
- **Simple API**: Easy-to-use REST and Python SDK
- **Templates**: Support for transactional templates
- **Analytics**: Email open/click tracking
- **GDPR Compliant**: EU-based with strong privacy focus

---

## 2. Architecture

### 2.1 System Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   FastAPI   │────▶│ Email Service│────▶│    Brevo    │
│   Router    │     │   Module     │     │     API     │
└─────────────┘     └──────────────┘     └─────────────┘
       │                   │
       │                   ▼
       │            ┌──────────────┐
       │            │   Templates  │
       │            │   (HTML)     │
       │            └──────────────┘
       ▼
┌─────────────┐
│  Database   │
│  (OTP Store)│
└─────────────┘
```

### 2.2 Components

| Component            | Purpose                                   |
| -------------------- | ----------------------------------------- |
| `email_service.py`   | Core email service with Brevo integration |
| `email_templates.py` | HTML email templates                      |
| `email_schemas.py`   | Pydantic schemas for email operations     |
| `email_config.py`    | Email configuration and constants         |

---

## 3. Email Types & Templates

### 3.1 Email Types

| Email Type            | Trigger                  | Template             | OTP Type         |
| --------------------- | ------------------------ | -------------------- | ---------------- |
| Registration OTP      | User registration        | `otp_registration`   | `registration`   |
| Password Reset OTP    | Forgot password request  | `otp_password_reset` | `password_reset` |
| Resend Registration   | User requests new OTP    | `otp_registration`   | `registration`   |
| Resend Password Reset | User requests new OTP    | `otp_password_reset` | `password_reset` |
| Welcome Email         | After email verification | `welcome`            | N/A              |

### 3.2 Template Variables

#### OTP Templates

| Variable             | Description             | Example                |
| -------------------- | ----------------------- | ---------------------- |
| `{{user_name}}`      | User's full name        | "John Doe"             |
| `{{otp_code}}`       | 6-digit OTP code        | "123456"               |
| `{{expiry_minutes}}` | OTP validity in minutes | "10"                   |
| `{{otp_type}}`       | Type of OTP             | "registration"         |
| `{{support_email}}`  | Support email address   | "support@agensium.com" |
| `{{app_name}}`       | Application name        | "Agensium"             |

### 3.3 Email Subject Lines

| Email Type         | Subject                                            |
| ------------------ | -------------------------------------------------- |
| Registration OTP   | "Verify your Agensium account - OTP: {{otp_code}}" |
| Password Reset OTP | "Reset your Agensium password - OTP: {{otp_code}}" |
| Welcome Email      | "Welcome to Agensium, {{user_name}}!"              |

---

## 4. Implementation

### 4.1 Project Structure

```
backend/
├── email_services/
│   ├── __init__.py           # Module exports
│   ├── email_service.py      # Core Brevo integration
│   ├── email_templates.py    # HTML templates
│   └── email_config.py       # Configuration
├── auth/
│   └── router.py             # Updated to use email service
└── .env                      # Brevo API key
```

> **Note**: The module is named `email_services` (not `email`) to avoid conflict with Python's built-in `email` module.

### 4.2 Environment Configuration

Add to `.env`:

```env
# Brevo (Email Service) Configuration
BREVO_API_KEY=xkeysib-your-api-key-here
BREVO_SENDER_EMAIL=noreply@agensium.com
BREVO_SENDER_NAME=Agensium

# Email Configuration
EMAIL_OTP_EXPIRE_MINUTES=10
EMAIL_ENABLED=true
EMAIL_DEBUG=false
```

### 4.3 Email Service Module

**File:** `backend/email/email_service.py`

```python
"""
Email service using Brevo (Sendinblue) for transactional emails.
"""
import os
import logging
from typing import Optional, Dict, Any
from enum import Enum

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from dotenv import load_dotenv

from .email_templates import get_otp_template, get_welcome_template
from .email_config import EmailConfig

load_dotenv()
logger = logging.getLogger(__name__)


class EmailType(str, Enum):
    """Email types supported by the service."""
    OTP_REGISTRATION = "otp_registration"
    OTP_PASSWORD_RESET = "otp_password_reset"
    WELCOME = "welcome"


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

        if self.api_key and self.enabled:
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key['api-key'] = self.api_key
            self.api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
                sib_api_v3_sdk.ApiClient(configuration)
            )
            logger.info("✓ Brevo email service initialized")
        else:
            self.api_instance = None
            if not self.enabled:
                logger.info("Email service is disabled")
            else:
                logger.warning("⚠ BREVO_API_KEY not set - emails will not be sent")

    def _is_available(self) -> bool:
        """Check if email service is available."""
        return self.api_instance is not None and self.enabled

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
            return {
                "success": True,
                "message_id": "debug-mode",
                "email": to_email
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

            logger.info(f"✓ Email sent: {subject} to {to_email}")
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


# Global instance for dependency injection
email_service = EmailService()


def get_email_service() -> EmailService:
    """Dependency to get email service instance."""
    return email_service
```

### 4.4 Email Templates

**File:** `backend/email/email_templates.py`

```python
"""
HTML email templates for Agensium.
"""


def get_otp_template(
    user_name: str,
    otp_code: str,
    otp_type: str,
    expiry_minutes: int
) -> str:
    """
    Generate HTML template for OTP emails.

    Args:
        user_name: User's full name
        otp_code: 6-digit OTP code
        otp_type: 'registration' or 'password_reset'
        expiry_minutes: OTP validity in minutes

    Returns:
        HTML string
    """
    if otp_type == "registration":
        title = "Verify Your Email"
        message = "Thank you for registering with Agensium! Please use the following OTP to verify your email address:"
        action_text = "verify your email"
    else:
        title = "Reset Your Password"
        message = "We received a request to reset your password. Please use the following OTP to proceed:"
        action_text = "reset your password"

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f7;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 100%; max-width: 600px; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600;">
                                Agensium
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 20px; color: #333333; font-size: 24px; font-weight: 600;">
                                {title}
                            </h2>

                            <p style="margin: 0 0 20px; color: #666666; font-size: 16px; line-height: 1.6;">
                                Hi {user_name},
                            </p>

                            <p style="margin: 0 0 30px; color: #666666; font-size: 16px; line-height: 1.6;">
                                {message}
                            </p>

                            <!-- OTP Code Box -->
                            <div style="background-color: #f8f9fa; border: 2px dashed #667eea; border-radius: 8px; padding: 30px; text-align: center; margin: 0 0 30px;">
                                <p style="margin: 0 0 10px; color: #666666; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">
                                    Your OTP Code
                                </p>
                                <p style="margin: 0; color: #333333; font-size: 36px; font-weight: 700; letter-spacing: 8px; font-family: 'Courier New', monospace;">
                                    {otp_code}
                                </p>
                            </div>

                            <p style="margin: 0 0 20px; color: #999999; font-size: 14px; line-height: 1.6;">
                                ⏱️ This code will expire in <strong>{expiry_minutes} minutes</strong>.
                            </p>

                            <p style="margin: 0; color: #999999; font-size: 14px; line-height: 1.6;">
                                If you didn't request to {action_text}, please ignore this email or contact support if you have concerns.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0 0 10px; color: #999999; font-size: 12px;">
                                © 2025 Agensium. All rights reserved.
                            </p>
                            <p style="margin: 0; color: #999999; font-size: 12px;">
                                Need help? Contact us at
                                <a href="mailto:support@agensium.com" style="color: #667eea; text-decoration: none;">support@agensium.com</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def get_welcome_template(user_name: str) -> str:
    """
    Generate HTML template for welcome email.

    Args:
        user_name: User's full name

    Returns:
        HTML string
    """
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Agensium</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f7;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 100%; max-width: 600px; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600;">
                                🎉 Welcome to Agensium!
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 20px; color: #333333; font-size: 24px; font-weight: 600;">
                                Hi {user_name}!
                            </h2>

                            <p style="margin: 0 0 20px; color: #666666; font-size: 16px; line-height: 1.6;">
                                Your email has been successfully verified. Welcome to Agensium - your intelligent data mastering platform!
                            </p>

                            <p style="margin: 0 0 20px; color: #666666; font-size: 16px; line-height: 1.6;">
                                Here's what you can do:
                            </p>

                            <ul style="margin: 0 0 30px; padding-left: 20px; color: #666666; font-size: 16px; line-height: 1.8;">
                                <li><strong>Profile Your Data</strong> - Understand your data quality</li>
                                <li><strong>Clean Your Data</strong> - Fix issues automatically</li>
                                <li><strong>Master Your Data</strong> - Create golden records</li>
                            </ul>

                            <!-- CTA Button -->
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="https://agensium.com/login"
                                   style="display: inline-block; padding: 16px 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600;">
                                    Get Started →
                                </a>
                            </div>

                            <p style="margin: 0; color: #999999; font-size: 14px; line-height: 1.6;">
                                If you have any questions, feel free to reach out to our support team.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0 0 10px; color: #999999; font-size: 12px;">
                                © 2025 Agensium. All rights reserved.
                            </p>
                            <p style="margin: 0; color: #999999; font-size: 12px;">
                                Need help? Contact us at
                                <a href="mailto:support@agensium.com" style="color: #667eea; text-decoration: none;">support@agensium.com</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
```

### 4.5 Email Configuration

**File:** `backend/email/email_config.py`

```python
"""
Email configuration and constants.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class EmailConfig:
    """Email service configuration."""

    # Brevo settings
    api_key: Optional[str] = None
    sender_email: str = "noreply@agensium.com"
    sender_name: str = "Agensium"

    # Feature flags
    enabled: bool = True
    debug: bool = False

    # OTP settings
    otp_expire_minutes: int = 10

    # Rate limiting
    max_emails_per_hour: int = 10
    max_resend_per_hour: int = 3

    def __post_init__(self):
        """Load configuration from environment."""
        self.api_key = os.getenv("BREVO_API_KEY")
        self.sender_email = os.getenv("BREVO_SENDER_EMAIL", self.sender_email)
        self.sender_name = os.getenv("BREVO_SENDER_NAME", self.sender_name)
        self.enabled = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
        self.debug = os.getenv("EMAIL_DEBUG", "false").lower() == "true"
        self.otp_expire_minutes = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))
```

### 4.6 Integration with Auth Router

**Updates to:** `backend/auth/router.py`

```python
# Add import at top
from email_services.email_service import get_email_service, EmailService

# Update register_user endpoint
@router.post("/register", ...)
async def register_user(
    user: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service)
):
    # ... existing code to create user ...

    # Send OTP email
    email_result = await email_service.send_otp_email(
        to_email=db_user.email,
        to_name=db_user.full_name,
        otp_code=otp_code,
        otp_type="registration"
    )

    # Return response WITHOUT otp in production
    return schemas.RegisterResponse(
        id=db_user.id,
        email=db_user.email,
        full_name=db_user.full_name,
        is_active=db_user.is_active,
        message="Registration successful. Please check your email for the OTP.",
        # otp=otp_code,  # REMOVED in production
        otp_type="registration"
    )


# Update verify_otp endpoint
@router.post("/verify-otp", ...)
async def verify_otp(
    data: schemas.VerifyOTP,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service)
):
    # ... existing verification logic ...

    # For registration verification, send welcome email
    if data.otp_type == "registration":
        user.is_verified = True
        # ... clear OTP fields ...
        db.commit()

        # Send welcome email (fire and forget)
        await email_service.send_welcome_email(
            to_email=user.email,
            to_name=user.full_name
        )

        return schemas.GenericResponse(
            message="Email verified successfully. You can now login."
        )


# Update resend_otp endpoint
@router.post("/resend-otp", ...)
async def resend_otp(
    data: schemas.ResendOTP,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service)
):
    # ... existing logic ...

    # Send new OTP email
    await email_service.send_otp_email(
        to_email=user.email,
        to_name=user.full_name,
        otp_code=otp_code,
        otp_type=data.otp_type
    )

    return schemas.GenericResponse(
        message="OTP sent to your email."
        # otp=otp_code,  # REMOVED in production
    )


# Update forgot_password endpoint
@router.post("/forgot-password", ...)
async def forgot_password(
    data: schemas.ForgotPassword,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service)
):
    # ... existing logic ...

    if user:
        # Send password reset OTP email
        await email_service.send_otp_email(
            to_email=user.email,
            to_name=user.full_name,
            otp_code=otp_code,
            otp_type="password_reset"
        )

    return schemas.GenericResponse(
        message="If the email exists, a password reset OTP will be sent."
        # otp=otp_code,  # REMOVED in production
    )
```

---

## 5. API Reference

### 5.1 Email Service Methods

| Method               | Description                     | Parameters                                 |
| -------------------- | ------------------------------- | ------------------------------------------ |
| `send_email`         | Send generic email              | `to_email, to_name, subject, html_content` |
| `send_otp_email`     | Send OTP for auth               | `to_email, to_name, otp_code, otp_type`    |
| `send_welcome_email` | Send welcome after verification | `to_email, to_name`                        |

### 5.2 Brevo API Endpoints Used

| Endpoint                         | Purpose                     |
| -------------------------------- | --------------------------- |
| `POST /v3/smtp/email`            | Send transactional email    |
| `GET /v3/smtp/statistics/events` | Get email events (optional) |

---

## 6. Error Handling

### 6.1 Error Scenarios

| Scenario              | Handling                              |
| --------------------- | ------------------------------------- |
| Brevo API unavailable | Log error, continue without blocking  |
| Invalid API key       | Log warning at startup                |
| Rate limit exceeded   | Return 429 Too Many Requests          |
| Invalid email address | Brevo returns error, log and continue |
| Network timeout       | Log error, retry once, then continue  |

### 6.2 Graceful Degradation

The email service is designed to fail gracefully:

```python
# Email sending is non-blocking
email_result = await email_service.send_otp_email(...)

# Even if email fails, registration continues
# The OTP is stored in database, user can request resend
if not email_result["success"]:
    logger.warning(f"Email not sent: {email_result['error']}")
    # Optional: Return warning to user
```

---

## 7. Testing

### 7.1 Unit Tests

| Test                          | Description                                 |
| ----------------------------- | ------------------------------------------- |
| `test_otp_template`           | Verify OTP template generates correctly     |
| `test_welcome_template`       | Verify welcome template generates correctly |
| `test_email_service_disabled` | Service returns gracefully when disabled    |
| `test_email_service_debug`    | Debug mode doesn't send actual emails       |

### 7.2 Integration Tests

| Test                            | Description                          |
| ------------------------------- | ------------------------------------ |
| `test_registration_sends_email` | Registration triggers OTP email      |
| `test_forgot_password_email`    | Forgot password triggers reset email |
| `test_resend_otp_email`         | Resend triggers new OTP email        |
| `test_verify_sends_welcome`     | Verification triggers welcome email  |

### 7.3 Manual Testing

```bash
# Test with debug mode (no actual emails sent)
EMAIL_DEBUG=true python main.py

# Test email template preview
python -c "from email.email_templates import get_otp_template; print(get_otp_template('John', '123456', 'registration', 10))"
```

---

## 8. Production Considerations

### 8.1 Security

- [x] OTP codes not exposed in API responses
- [x] Rate limiting on email endpoints
- [x] User enumeration protection (same response for existing/non-existing)
- [ ] SPF/DKIM/DMARC configured for sender domain
- [ ] Brevo API key stored securely

### 8.2 Monitoring

- Log all email sends with status
- Track delivery rates via Brevo dashboard
- Alert on high failure rates
- Monitor daily email quota usage

### 8.3 Brevo Quotas

| Plan     | Daily Limit | Notes                      |
| -------- | ----------- | -------------------------- |
| Free     | 300/day     | Sufficient for development |
| Starter  | 20,000/mo   | ~650/day                   |
| Business | 100,000/mo  | ~3,300/day                 |

---

## 9. Progress Tracking

### Implementation Checklist

- [x] **Setup**

  - [x] Install `sib-api-v3-sdk` package
  - [x] Add Brevo configuration to `.env` template
  - [ ] Create Brevo account and get API key
  - [ ] Verify sender domain in Brevo

- [x] **Email Module**

  - [x] Create `email_services/__init__.py`
  - [x] Create `email_services/email_config.py`
  - [x] Create `email_services/email_templates.py`
  - [x] Create `email_services/email_service.py`

- [x] **Auth Integration**

  - [x] Update `auth/router.py` - register endpoint
  - [x] Update `auth/router.py` - verify-otp endpoint
  - [x] Update `auth/router.py` - resend-otp endpoint
  - [x] Update `auth/router.py` - forgot-password endpoint
  - [x] Update `auth/router.py` - reset-password endpoint
  - [x] Update `auth/router.py` - change-password endpoint
  - [ ] Remove OTP from responses (use email instead) - **For production**

- [ ] **Testing**

  - [ ] Test registration email flow
  - [ ] Test password reset email flow
  - [ ] Test resend OTP email flow
  - [ ] Test welcome email after verification
  - [ ] Test graceful degradation (disabled service)

- [ ] **Production Ready**
  - [ ] Set up sender domain verification
  - [ ] Configure SPF/DKIM/DMARC
  - [ ] Set EMAIL_DEBUG=false
  - [ ] Monitor Brevo dashboard
  - [ ] Document rate limits

---

## Quick Start

```bash
# 1. Install dependency
pip install sib-api-v3-sdk

# 2. Add to requirements.txt
echo "sib-api-v3-sdk>=7.0.0" >> requirements.txt

# 3. Add environment variables
# BREVO_API_KEY=xkeysib-xxx
# BREVO_SENDER_EMAIL=noreply@agensium.com
# BREVO_SENDER_NAME=Agensium
# EMAIL_ENABLED=true
# EMAIL_DEBUG=true  # Set to false in production

# 4. Create email module (see implementation above)

# 5. Update auth router

# 6. Test
python main.py
```

---

**Status**: ⏳ Ready for implementation
