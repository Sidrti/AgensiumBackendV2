"""
Custom exceptions for the billing module.

All billing-related exceptions inherit from BillingException.
Each exception includes an error_code for frontend handling.
"""

from typing import Optional, Dict, Any


class BillingException(Exception):
    """
    Base exception for all billing-related errors.
    
    Attributes:
        detail: Human-readable error message
        error_code: Machine-readable error code for frontend handling
        status_code: HTTP status code to return
        context: Additional context for debugging
    """
    
    def __init__(
        self,
        detail: str,
        error_code: str = "BILLING_ERROR",
        status_code: int = 400,
        context: Optional[Dict[str, Any]] = None
    ):
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code
        self.context = context or {}
        super().__init__(self.detail)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        return {
            "detail": self.detail,
            "error_code": self.error_code,
            "context": self.context
        }


class InsufficientCreditsError(BillingException):
    """
    Raised when user doesn't have enough credits for an operation.
    
    HTTP Status: 402 Payment Required
    """
    
    def __init__(
        self,
        available: int,
        required: int,
        agent_id: Optional[str] = None,
        tool_id: Optional[str] = None
    ):
        context = {
            "available": available,
            "required": required,
            "shortfall": required - available
        }
        if agent_id:
            context["agent_id"] = agent_id
        if tool_id:
            context["tool_id"] = tool_id
            
        super().__init__(
            detail=f"Insufficient credits. Required: {required}, Available: {available}",
            error_code="BILLING_INSUFFICIENT_CREDITS",
            status_code=402,
            context=context
        )
        
        self.available = available
        self.required = required
        self.agent_id = agent_id
        self.tool_id = tool_id


class AgentCostNotFoundError(BillingException):
    """
    Raised when agent cost is not found in the database.
    
    This is a configuration error - the agent_costs table should have all agents.
    HTTP Status: 500 Internal Server Error
    """
    
    def __init__(self, agent_id: str):
        super().__init__(
            detail=f"Agent cost not configured for: {agent_id}",
            error_code="BILLING_AGENT_COST_MISSING",
            status_code=500,
            context={"agent_id": agent_id}
        )
        self.agent_id = agent_id


class UserWalletNotFoundError(BillingException):
    """
    Raised when user doesn't have a wallet.
    
    This typically means the user hasn't purchased credits yet.
    HTTP Status: 404 Not Found
    """
    
    def __init__(self, user_id: int):
        super().__init__(
            detail=f"Wallet not found for user. Please purchase credits first.",
            error_code="BILLING_WALLET_NOT_FOUND",
            status_code=404,
            context={"user_id": user_id}
        )
        self.user_id = user_id


class InvalidPackageError(BillingException):
    """
    Raised when an invalid package ID is provided.
    
    HTTP Status: 400 Bad Request
    """
    
    def __init__(self, package_id: str, available_packages: Optional[list] = None):
        context = {"package_id": package_id}
        if available_packages:
            context["available_packages"] = available_packages
            
        super().__init__(
            detail=f"Invalid package: {package_id}",
            error_code="BILLING_INVALID_PACKAGE",
            status_code=400,
            context=context
        )
        self.package_id = package_id


class StripeWebhookError(BillingException):
    """
    Raised when there's an error processing a Stripe webhook.
    
    HTTP Status: 400 Bad Request
    """
    
    def __init__(self, detail: str, event_id: Optional[str] = None):
        context = {}
        if event_id:
            context["event_id"] = event_id
            
        super().__init__(
            detail=detail,
            error_code="BILLING_WEBHOOK_ERROR",
            status_code=400,
            context=context
        )


class InvalidSignatureError(StripeWebhookError):
    """
    Raised when Stripe webhook signature verification fails.
    
    HTTP Status: 400 Bad Request
    """
    
    def __init__(self):
        super().__init__(
            detail="Invalid Stripe webhook signature"
        )
        self.error_code = "BILLING_INVALID_SIGNATURE"


class DuplicateWebhookError(BillingException):
    """
    Raised when a webhook event has already been processed.
    
    This is not really an error - it's for idempotency.
    HTTP Status: 200 OK (we return success for idempotency)
    """
    
    def __init__(self, event_id: str):
        super().__init__(
            detail=f"Webhook event already processed: {event_id}",
            error_code="BILLING_DUPLICATE_WEBHOOK",
            status_code=200,  # Return 200 for idempotency
            context={"event_id": event_id}
        )
        self.event_id = event_id


class StripeCustomerCreationError(BillingException):
    """
    Raised when Stripe customer creation fails.
    
    HTTP Status: 500 Internal Server Error
    """
    
    def __init__(self, user_id: int, stripe_error: Optional[str] = None):
        context = {"user_id": user_id}
        if stripe_error:
            context["stripe_error"] = stripe_error
            
        super().__init__(
            detail="Failed to create Stripe customer",
            error_code="BILLING_STRIPE_CUSTOMER_ERROR",
            status_code=500,
            context=context
        )


class StripeCheckoutError(BillingException):
    """
    Raised when Stripe checkout session creation fails.
    
    HTTP Status: 500 Internal Server Error
    """
    
    def __init__(self, stripe_error: Optional[str] = None):
        context = {}
        if stripe_error:
            context["stripe_error"] = stripe_error
            
        super().__init__(
            detail="Failed to create checkout session",
            error_code="BILLING_CHECKOUT_ERROR",
            status_code=500,
            context=context
        )
