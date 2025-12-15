"""
Email services module for Agensium.
Provides Brevo integration for transactional emails.
"""
from email_services.email_service import EmailService, get_email_service, EmailType
from email_services.email_config import EmailConfig

__all__ = [
    "EmailService",
    "get_email_service",
    "EmailType",
    "EmailConfig",
]
