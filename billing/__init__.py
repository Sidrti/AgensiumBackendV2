"""
Billing module for prepaid credit-based billing system.

This module provides:
- Credit wallet management
- Stripe integration for payments
- Agent cost tracking
- Transaction ledger for audit trails
- Billing context for task execution
"""

from .exceptions import (
    BillingException,
    InsufficientCreditsError,
    AgentCostNotFoundError,
    UserWalletNotFoundError,
    InvalidPackageError,
    StripeWebhookError,
    DuplicateWebhookError,
)

from .agent_costs_service import AgentCostsService, normalize_agent_id
from .wallet_service import WalletService
from .stripe_service import StripeService, load_credit_packages
from .billing_context import BillingContext

__all__ = [
    # Exceptions
    "BillingException",
    "InsufficientCreditsError",
    "AgentCostNotFoundError",
    "UserWalletNotFoundError",
    "InvalidPackageError",
    "StripeWebhookError",
    "DuplicateWebhookError",
    # Services
    "AgentCostsService",
    "WalletService",
    "StripeService",
    # Context
    "BillingContext",
    # Utilities
    "normalize_agent_id",
    "load_credit_packages",
]
