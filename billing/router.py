"""
Billing Router

FastAPI router for billing endpoints.
Handles wallet management, credit purchases, and admin operations.
"""

import os
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session

from db.database import get_db
from db import models
from db.schemas import (
    WalletResponse,
    TransactionResponse,
    PackagesResponse,
    CreditPackage,
    CheckoutRequest,
    CheckoutResponse,
    AgentCostsListResponse,
    AgentCostResponse,
    UpdateAgentCostRequest,
    AdminGrantRequest,
    AdminGrantResponse,
    BillingErrorResponse,
)
from auth.dependencies import get_current_active_verified_user

from .wallet_service import WalletService
from .agent_costs_service import AgentCostsService, seed_default_agent_costs
from .stripe_service import StripeService, get_packages_list
from .exceptions import (
    BillingException,
    InsufficientCreditsError,
    DuplicateWebhookError,
)


# Create router
router = APIRouter(prefix="/billing", tags=["billing"])


# Environment variables for URLs
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", f"{FRONTEND_URL}/billing/success")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", f"{FRONTEND_URL}/billing/cancel")


# ============================================================================
# WALLET ENDPOINTS
# ============================================================================

@router.get(
    "/wallet",
    response_model=WalletResponse,
    summary="Get wallet information",
    description="Get current credit balance and recent transactions"
)
async def get_wallet(
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Get wallet information for the current user.
    
    Returns:
    - Current credit balance
    - Wallet status
    - Recent transactions (last 20)
    """
    wallet_service = WalletService(db)
    
    # Get or create wallet
    wallet = wallet_service.get_or_create_wallet(current_user.id)
    
    # Get recent transactions
    transactions = wallet_service.get_transactions(
        user_id=current_user.id,
        limit=20
    )
    
    # Convert transactions to response format
    transaction_responses = [
        TransactionResponse(
            id=t.id,
            delta_credits=t.delta_credits,
            type=t.type,
            reason=t.reason,
            agent_id=t.agent_id,
            tool_id=t.tool_id,
            analysis_id=t.analysis_id,
            created_at=t.created_at.isoformat() + "Z" if t.created_at else None
        )
        for t in transactions
    ]
    
    return WalletResponse(
        balance_credits=wallet.balance_credits,
        status="active",
        recent_transactions=transaction_responses
    )


@router.get(
    "/balance",
    summary="Get credit balance",
    description="Get current credit balance (quick endpoint)"
)
async def get_balance(
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Quick endpoint to get just the credit balance.
    """
    wallet_service = WalletService(db)
    balance = wallet_service.get_balance(current_user.id)
    
    return {"balance_credits": balance}


@router.get(
    "/transactions",
    summary="Get transaction history",
    description="Get paginated transaction history"
)
async def get_transactions(
    limit: int = 20,
    offset: int = 0,
    transaction_type: Optional[str] = None,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Get paginated transaction history.
    
    Args:
        limit: Maximum transactions to return (default 20, max 100)
        offset: Number of transactions to skip
        transaction_type: Filter by type (PURCHASE, CONSUME, REFUND, ADJUSTMENT)
    """
    # Validate limit
    if limit > 100:
        limit = 100
    
    wallet_service = WalletService(db)
    
    transactions = wallet_service.get_transactions(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        transaction_type=transaction_type
    )
    
    total = wallet_service.get_transaction_count(
        user_id=current_user.id,
        transaction_type=transaction_type
    )
    
    return {
        "transactions": [
            TransactionResponse(
                id=t.id,
                delta_credits=t.delta_credits,
                type=t.type,
                reason=t.reason,
                agent_id=t.agent_id,
                tool_id=t.tool_id,
                analysis_id=t.analysis_id,
                created_at=t.created_at.isoformat() + "Z" if t.created_at else None
            )
            for t in transactions
        ],
        "total": total,
        "limit": limit,
        "offset": offset
    }


# ============================================================================
# PACKAGE & CHECKOUT ENDPOINTS
# ============================================================================

@router.get(
    "/packages",
    response_model=PackagesResponse,
    summary="Get available credit packages",
    description="Get list of credit packages available for purchase"
)
async def get_packages(
    current_user: models.User = Depends(get_current_active_verified_user)
):
    """
    Get available credit packages for purchase.
    
    Returns list of packages with:
    - package_id: Unique identifier
    - credits: Number of credits
    - amount_cents: Price in cents
    - currency: Currency code (USD)
    """
    packages = get_packages_list()
    
    return PackagesResponse(
        packages=[
            CreditPackage(
                package_id=p["package_id"],
                credits=p["credits"],
                stripe_price_id=p["stripe_price_id"],
                amount_cents=p["amount_cents"],
                currency=p["currency"]
            )
            for p in packages
        ]
    )


@router.post(
    "/checkout-session",
    response_model=CheckoutResponse,
    summary="Create checkout session",
    description="Create a Stripe checkout session for credit purchase"
)
async def create_checkout_session(
    request: CheckoutRequest,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Create a Stripe checkout session.
    
    Returns:
    - checkout_url: URL to redirect user for payment
    - session_id: Stripe session ID
    """
    stripe_service = StripeService(db)
    
    # Build success/cancel URLs
    success_url = f"{STRIPE_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = STRIPE_CANCEL_URL
    
    result = stripe_service.create_checkout_session(
        user=current_user,
        package_id=request.package_id,
        success_url=success_url,
        cancel_url=cancel_url
    )
    
    return CheckoutResponse(
        checkout_url=result["checkout_url"],
        session_id=result["session_id"]
    )


@router.get(
    "/customer-portal",
    summary="Get customer portal URL",
    description="Get Stripe customer portal URL for billing management"
)
async def get_customer_portal(
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Get Stripe customer portal URL for managing billing.
    
    User must have made at least one purchase.
    """
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing history found. Make a purchase first."
        )
    
    stripe_service = StripeService(db)
    return_url = f"{FRONTEND_URL}/billing"
    
    portal_url = stripe_service.get_customer_portal_url(
        user=current_user,
        return_url=return_url
    )
    
    return {"portal_url": portal_url}


# ============================================================================
# WEBHOOK ENDPOINT
# ============================================================================

@router.post(
    "/webhook",
    summary="Stripe webhook handler",
    description="Process Stripe webhook events (called by Stripe)"
)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Stripe webhook events.
    
    This endpoint is called by Stripe, not by frontend.
    Verifies signature and processes payment events.
    
    Important: Always returns 200 OK to prevent Stripe retries
    (except for signature verification failures).
    """
    # Get raw body and signature
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    
    if not sig_header:
        # Log but return 200 to prevent retries
        print("Warning: Stripe webhook called without signature header")
        return {"status": "error", "message": "Missing signature"}
    
    stripe_service = StripeService(db)
    
    try:
        result = stripe_service.handle_webhook_event(
            payload=payload,
            sig_header=sig_header
        )
        return result
        
    except DuplicateWebhookError as e:
        # Already processed - return success for idempotency
        return {"status": "already_processed", "event_id": e.event_id}
        
    except BillingException as e:
        # Log error but return 200 to prevent retries
        print(f"Webhook processing error: {e.detail}")
        return {"status": "error", "message": e.detail}
        
    except Exception as e:
        # Log unexpected errors but return 200
        print(f"Unexpected webhook error: {str(e)}")
        return {"status": "error", "message": "Internal error"}


# ============================================================================
# COST ESTIMATION ENDPOINTS
# ============================================================================

@router.post(
    "/estimate-cost",
    summary="Estimate cost for agents",
    description="Calculate total cost for running specified agents"
)
async def estimate_cost(
    agent_ids: list[str],
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Estimate total cost for running specified agents.
    
    Useful for pre-flight validation before starting analysis.
    
    Returns:
    - can_afford: Whether user has enough credits
    - balance: Current balance
    - total_cost: Total cost of all agents
    - breakdown: Cost per agent
    - shortfall: How many more credits needed (if any)
    """
    wallet_service = WalletService(db)
    
    result = wallet_service.can_afford_agents(
        user_id=current_user.id,
        agent_ids=agent_ids
    )
    
    return result


# ============================================================================
# AGENT COSTS ENDPOINTS
# ============================================================================

@router.get(
    "/agent-costs",
    response_model=AgentCostsListResponse,
    summary="List agent costs",
    description="Get cost configuration for all agents"
)
async def list_agent_costs(
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Get all agent costs.
    
    Returns list of agents with their credit costs.
    """
    agent_costs_service = AgentCostsService(db)
    costs = agent_costs_service.list_all_costs()
    
    return AgentCostsListResponse(
        agent_costs=[
            AgentCostResponse(
                agent_id=c.agent_id,
                cost=c.cost,
                description=c.description
            )
            for c in costs
        ]
    )


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.post(
    "/admin/grant",
    response_model=AdminGrantResponse,
    summary="Grant credits (admin)",
    description="Manually grant or deduct credits for a user"
)
async def admin_grant_credits(
    request: AdminGrantRequest,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to grant or deduct credits.
    
    NOTE: In production, this should require admin role verification.
    Currently just requires authenticated user for development.
    
    Args:
        user_id: Target user ID
        amount_credits: Credits to add (positive) or remove (negative)
        reason: Reason for adjustment
    """
    # TODO: Add admin role check in production
    # For now, allow any verified user (for development)
    
    # Verify target user exists
    target_user = db.query(models.User).filter(
        models.User.id == request.user_id
    ).first()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    wallet_service = WalletService(db)
    
    transaction = wallet_service.add_adjustment(
        user_id=request.user_id,
        amount=request.amount_credits,
        reason=f"Admin adjustment by {current_user.email}: {request.reason}"
    )
    
    new_balance = wallet_service.get_balance(request.user_id)
    
    return AdminGrantResponse(
        new_balance=new_balance,
        transaction_id=transaction.id
    )


@router.put(
    "/admin/agent-costs/{agent_id}",
    response_model=AgentCostResponse,
    summary="Update agent cost (admin)",
    description="Update the credit cost for an agent"
)
async def admin_update_agent_cost(
    agent_id: str,
    request: UpdateAgentCostRequest,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to update agent cost.
    
    NOTE: In production, this should require admin role verification.
    """
    # TODO: Add admin role check in production
    
    agent_costs_service = AgentCostsService(db)
    
    agent_cost = agent_costs_service.set_agent_cost(
        agent_id=agent_id,
        cost=request.cost
    )
    
    return AgentCostResponse(
        agent_id=agent_cost.agent_id,
        cost=agent_cost.cost,
        description=agent_cost.description
    )


@router.post(
    "/admin/seed-costs",
    summary="Seed default agent costs (admin)",
    description="Seed the database with default agent costs"
)
async def admin_seed_costs(
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Seed database with default agent costs.
    
    Only adds agents that don't already have costs configured.
    """
    # TODO: Add admin role check in production
    
    seed_default_agent_costs(db)
    
    # Return updated list
    agent_costs_service = AgentCostsService(db)
    costs = agent_costs_service.list_all_costs()
    
    return {
        "status": "success",
        "message": "Default agent costs seeded",
        "agent_costs": [
            {"agent_id": c.agent_id, "cost": c.cost}
            for c in costs
        ]
    }
