"""
Stripe Service

Handles all Stripe integrations including:
- Credit package management
- Customer creation
- Checkout session creation
- Webhook processing
"""

import os
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

import stripe
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from db.models import User, StripeWebhookEvent
from .exceptions import (
    InvalidPackageError,
    InvalidSignatureError,
    DuplicateWebhookError,
    StripeCustomerCreationError,
    StripeCheckoutError,
    StripeWebhookError,
)
from .wallet_service import WalletService


# Load Stripe API key from environment
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Configure Stripe
if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY


def load_credit_packages() -> Dict[str, Dict[str, Any]]:
    """
    Load credit packages configuration from JSON file.
    
    Returns:
        Dictionary mapping package_id to package details
    """
    json_path = os.path.join(
        os.path.dirname(__file__),
        "credit_packages.json"
    )
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Convert list to dict for easy lookup
        packages = {}
        for pkg in config.get("packages", []):
            packages[pkg["package_id"]] = pkg
        
        return packages
    except FileNotFoundError:
        print(f"Warning: credit_packages.json not found at {json_path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in credit_packages.json: {e}")
        return {}


# Load packages on module import
CREDIT_PACKAGES = load_credit_packages()


def get_packages_list() -> List[Dict[str, Any]]:
    """
    Get list of all credit packages.
    
    Returns:
        List of package dictionaries
    """
    return list(CREDIT_PACKAGES.values())


def get_package(package_id: str) -> Dict[str, Any]:
    """
    Get a specific package by ID.
    
    Args:
        package_id: Package identifier
        
    Returns:
        Package dictionary
        
    Raises:
        InvalidPackageError: If package not found
    """
    if package_id not in CREDIT_PACKAGES:
        raise InvalidPackageError(
            package_id=package_id,
            available_packages=list(CREDIT_PACKAGES.keys())
        )
    
    return CREDIT_PACKAGES[package_id]


class StripeService:
    """
    Service for Stripe integration.
    
    Handles:
    - Customer management
    - Checkout session creation
    - Webhook processing
    """
    
    def __init__(self, db: Session):
        """
        Initialize the service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._wallet_service = None
    
    @property
    def wallet_service(self) -> WalletService:
        """Lazy-loaded wallet service."""
        if self._wallet_service is None:
            self._wallet_service = WalletService(self.db)
        return self._wallet_service
    
    def _ensure_stripe_configured(self) -> None:
        """
        Ensure Stripe is configured.
        
        Raises:
            RuntimeError: If Stripe API key is not set
        """
        if not STRIPE_API_KEY:
            raise RuntimeError(
                "STRIPE_API_KEY environment variable is not set. "
                "Please configure Stripe API key in .env file."
            )
    
    def get_or_create_stripe_customer(self, user: User) -> str:
        """
        Get existing Stripe customer ID or create new customer.
        
        Args:
            user: User model instance
            
        Returns:
            Stripe customer ID
            
        Raises:
            StripeCustomerCreationError: If customer creation fails
        """
        self._ensure_stripe_configured()
        
        # Return existing customer ID
        if user.stripe_customer_id:
            return user.stripe_customer_id
        
        try:
            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=user.email,
                name=user.full_name,
                metadata={
                    "user_id": str(user.id),
                    "created_from": "agensium"
                }
            )
            
            # Save customer ID to user
            user.stripe_customer_id = customer.id
            self.db.commit()
            
            return customer.id
            
        except stripe.error.StripeError as e:
            raise StripeCustomerCreationError(
                user_id=user.id,
                stripe_error=str(e)
            )
    
    def create_checkout_session(
        self,
        user: User,
        package_id: str,
        success_url: str,
        cancel_url: str
    ) -> Dict[str, Any]:
        """
        Create a Stripe checkout session for credit purchase.
        
        Args:
            user: User model instance
            package_id: Package ID to purchase
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect after cancelled payment
            
        Returns:
            Dictionary with checkout_url and session_id
            
        Raises:
            InvalidPackageError: If package not found
            StripeCheckoutError: If checkout creation fails
        """
        self._ensure_stripe_configured()
        
        # Validate package
        package = get_package(package_id)
        
        # Ensure customer exists
        customer_id = self.get_or_create_stripe_customer(user)
        
        try:
            # Create checkout session
            session = stripe.checkout.Session.create(
                mode="payment",
                customer=customer_id,
                line_items=[{
                    "price": package["stripe_price_id"],
                    "quantity": 1
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": str(user.id),
                    "package_id": package_id,
                    "credits": str(package["credits"])
                },
                payment_intent_data={
                    "metadata": {
                        "user_id": str(user.id),
                        "package_id": package_id,
                        "credits": str(package["credits"])
                    }
                }
            )
            
            return {
                "checkout_url": session.url,
                "session_id": session.id
            }
            
        except stripe.error.StripeError as e:
            raise StripeCheckoutError(stripe_error=str(e))
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        sig_header: str
    ) -> Dict[str, Any]:
        """
        Verify Stripe webhook signature and return event.
        
        Args:
            payload: Raw request body
            sig_header: Stripe-Signature header value
            
        Returns:
            Verified Stripe event dictionary
            
        Raises:
            InvalidSignatureError: If signature verification fails
        """
        if not STRIPE_WEBHOOK_SECRET:
            raise RuntimeError(
                "STRIPE_WEBHOOK_SECRET environment variable is not set."
            )
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
            return event
        except ValueError:
            raise InvalidSignatureError()
        except stripe.error.SignatureVerificationError:
            raise InvalidSignatureError()
    
    def is_event_processed(self, event_id: str) -> bool:
        """
        Check if a webhook event has already been processed.
        
        Args:
            event_id: Stripe event ID
            
        Returns:
            True if already processed, False otherwise
        """
        existing = self.db.query(StripeWebhookEvent).filter(
            StripeWebhookEvent.stripe_event_id == event_id
        ).first()
        
        return existing is not None
    
    def mark_event_processed(
        self,
        event_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> StripeWebhookEvent:
        """
        Mark a webhook event as processed.
        
        Args:
            event_id: Stripe event ID
            event_type: Event type (e.g., checkout.session.completed)
            payload: Optional event payload to store
            
        Returns:
            StripeWebhookEvent record
        """
        event_record = StripeWebhookEvent(
            stripe_event_id=event_id,
            event_type=event_type,
            processed_at=func.now(),
            payload_json=payload
        )
        self.db.add(event_record)
        self.db.commit()
        self.db.refresh(event_record)
        
        return event_record
    
    def process_checkout_completed(
        self,
        event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process checkout.session.completed webhook event.
        
        Grants credits to user wallet.
        
        Args:
            event: Stripe event dictionary
            
        Returns:
            Dictionary with processing result
            
        Raises:
            DuplicateWebhookError: If event already processed
            StripeWebhookError: If processing fails
        """
        event_id = event["id"]
        event_type = event["type"]
        
        # Check idempotency
        if self.is_event_processed(event_id):
            raise DuplicateWebhookError(event_id)
        
        # Extract session data
        session = event["data"]["object"]
        
        # Verify payment status
        if session.get("payment_status") != "paid":
            # Not paid yet, wait for payment
            return {
                "status": "pending",
                "message": "Payment not completed yet"
            }
        
        # Extract metadata
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        package_id = metadata.get("package_id")
        credits_str = metadata.get("credits")
        
        if not all([user_id, package_id, credits_str]):
            raise StripeWebhookError(
                detail="Missing required metadata in checkout session",
                event_id=event_id
            )
        
        try:
            user_id = int(user_id)
            credits = int(credits_str)
        except ValueError:
            raise StripeWebhookError(
                detail="Invalid user_id or credits in metadata",
                event_id=event_id
            )
        
        # Verify user exists
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise StripeWebhookError(
                detail=f"User not found: {user_id}",
                event_id=event_id
            )
        
        # Grant credits
        transaction = self.wallet_service.add_credits_from_purchase(
            user_id=user_id,
            amount=credits,
            stripe_checkout_session_id=session.get("id"),
            stripe_payment_intent_id=session.get("payment_intent"),
            stripe_event_id=event_id,
            reason=f"Credit purchase: {package_id} ({credits} credits)"
        )
        
        # Mark event as processed
        self.mark_event_processed(
            event_id=event_id,
            event_type=event_type,
            payload=None  # Don't store full payload for security
        )
        
        return {
            "status": "success",
            "user_id": user_id,
            "credits_granted": credits,
            "transaction_id": transaction.id,
            "new_balance": self.wallet_service.get_balance(user_id)
        }
    
    def handle_webhook_event(
        self,
        payload: bytes,
        sig_header: str
    ) -> Dict[str, Any]:
        """
        Handle incoming Stripe webhook event.
        
        Main entry point for webhook processing.
        
        Args:
            payload: Raw request body
            sig_header: Stripe-Signature header value
            
        Returns:
            Dictionary with processing result
        """
        # Verify signature
        event = self.verify_webhook_signature(payload, sig_header)
        
        event_type = event.get("type", "")
        
        # Route to appropriate handler
        if event_type == "checkout.session.completed":
            return self.process_checkout_completed(event)
        
        # Handle other event types as needed
        # For now, just acknowledge receipt
        return {
            "status": "received",
            "event_type": event_type,
            "message": f"Event type {event_type} received but not processed"
        }
    
    def get_customer_portal_url(
        self,
        user: User,
        return_url: str
    ) -> str:
        """
        Get Stripe customer portal URL for billing management.
        
        Args:
            user: User model instance
            return_url: URL to return to after portal session
            
        Returns:
            Customer portal URL
        """
        self._ensure_stripe_configured()
        
        if not user.stripe_customer_id:
            raise StripeCustomerCreationError(
                user_id=user.id,
                stripe_error="User has no Stripe customer ID"
            )
        
        try:
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=return_url
            )
            return session.url
        except stripe.error.StripeError as e:
            raise StripeCheckoutError(stripe_error=str(e))
