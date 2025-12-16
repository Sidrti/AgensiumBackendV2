"""
Wallet Service

Handles credit wallet operations with atomic transactions and row-level locking.
Ensures no negative balances through database-level enforcement.
"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.models import User, CreditWallet, CreditTransaction, TransactionType
from .exceptions import (
    InsufficientCreditsError,
    UserWalletNotFoundError,
)
from .agent_costs_service import AgentCostsService, normalize_agent_id


class WalletService:
    """
    Service for managing credit wallets.
    
    Provides atomic operations for:
    - Getting wallet balance
    - Consuming credits for agent execution
    - Adding credits from purchases
    - Manual adjustments (admin)
    
    All debit operations use row-level locking to prevent race conditions.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the service with a database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._agent_costs_service = None
    
    @property
    def agent_costs_service(self) -> AgentCostsService:
        """Lazy-loaded agent costs service."""
        if self._agent_costs_service is None:
            self._agent_costs_service = AgentCostsService(self.db)
        return self._agent_costs_service
    
    def get_or_create_wallet(self, user_id: int) -> CreditWallet:
        """
        Get existing wallet or create a new one for the user.
        
        Args:
            user_id: User ID
            
        Returns:
            CreditWallet instance
        """
        wallet = self.db.query(CreditWallet).filter(
            CreditWallet.user_id == user_id
        ).first()
        
        if not wallet:
            wallet = CreditWallet(
                user_id=user_id,
                balance_credits=0
            )
            self.db.add(wallet)
            self.db.commit()
            self.db.refresh(wallet)
        
        return wallet
    
    def get_wallet(self, user_id: int) -> Optional[CreditWallet]:
        """
        Get wallet for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            CreditWallet or None if not found
        """
        return self.db.query(CreditWallet).filter(
            CreditWallet.user_id == user_id
        ).first()
    
    def get_balance(self, user_id: int) -> int:
        """
        Get current credit balance for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Current balance in credits (0 if no wallet)
        """
        wallet = self.get_wallet(user_id)
        return wallet.balance_credits if wallet else 0
    
    def consume_for_agent(
        self,
        user_id: int,
        agent_id: str,
        tool_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        cost: Optional[int] = None
    ) -> CreditTransaction:
        """
        Atomically debit credits for agent execution.
        
        Uses row-level locking to prevent race conditions.
        This is the primary method called by transformers before executing agents.
        
        Args:
            user_id: User ID
            agent_id: Agent identifier (will be normalized)
            tool_id: Optional tool identifier
            analysis_id: Optional analysis identifier
            cost: Optional explicit cost (if not provided, looks up from agent_costs)
            
        Returns:
            CreditTransaction record for the debit
            
        Raises:
            UserWalletNotFoundError: If user doesn't have a wallet
            InsufficientCreditsError: If balance is less than cost
            AgentCostNotFoundError: If agent cost is not configured (when cost not provided)
        """
        normalized_agent_id = normalize_agent_id(agent_id)
        
        # Get cost if not explicitly provided
        if cost is None:
            cost = self.agent_costs_service.get_agent_cost(agent_id)
        
        # Lock the wallet row for update
        wallet = self.db.query(CreditWallet).filter(
            CreditWallet.user_id == user_id
        ).with_for_update().first()
        
        if not wallet:
            raise UserWalletNotFoundError(user_id)
        
        # Check sufficient balance
        if wallet.balance_credits < cost:
            raise InsufficientCreditsError(
                available=wallet.balance_credits,
                required=cost,
                agent_id=normalized_agent_id,
                tool_id=tool_id
            )
        
        # Debit credits
        wallet.balance_credits -= cost
        
        # Record transaction
        transaction = CreditTransaction(
            user_id=user_id,
            delta_credits=-cost,  # Negative for consumption
            type=TransactionType.CONSUME.value,
            reason=f"Agent execution: {normalized_agent_id}",
            agent_id=normalized_agent_id,
            tool_id=tool_id,
            analysis_id=analysis_id
        )
        self.db.add(transaction)
        
        # Commit the transaction
        self.db.commit()
        self.db.refresh(transaction)
        
        return transaction
    
    def add_credits_from_purchase(
        self,
        user_id: int,
        amount: int,
        stripe_checkout_session_id: Optional[str] = None,
        stripe_payment_intent_id: Optional[str] = None,
        stripe_event_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> CreditTransaction:
        """
        Add credits from a Stripe purchase.
        
        Creates wallet if it doesn't exist.
        Uses Stripe IDs for idempotency.
        
        Args:
            user_id: User ID
            amount: Amount of credits to add (positive)
            stripe_checkout_session_id: Stripe checkout session ID
            stripe_payment_intent_id: Stripe payment intent ID
            stripe_event_id: Stripe event ID
            reason: Optional reason string
            
        Returns:
            CreditTransaction record for the purchase
            
        Raises:
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Get or create wallet
        wallet = self.get_or_create_wallet(user_id)
        
        # Lock the wallet row for update
        wallet = self.db.query(CreditWallet).filter(
            CreditWallet.user_id == user_id
        ).with_for_update().first()
        
        # Add credits
        wallet.balance_credits += amount
        
        # Record transaction
        transaction = CreditTransaction(
            user_id=user_id,
            delta_credits=amount,  # Positive for purchase
            type=TransactionType.PURCHASE.value,
            reason=reason or "Credit purchase",
            stripe_checkout_session_id=stripe_checkout_session_id,
            stripe_payment_intent_id=stripe_payment_intent_id,
            stripe_event_id=stripe_event_id
        )
        self.db.add(transaction)
        
        # Commit
        self.db.commit()
        self.db.refresh(transaction)
        
        return transaction
    
    def add_refund(
        self,
        user_id: int,
        amount: int,
        reason: str,
        stripe_event_id: Optional[str] = None
    ) -> CreditTransaction:
        """
        Add credits as a refund.
        
        Args:
            user_id: User ID
            amount: Amount of credits to refund (positive)
            reason: Reason for refund
            stripe_event_id: Optional Stripe event ID
            
        Returns:
            CreditTransaction record for the refund
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Get or create wallet
        wallet = self.get_or_create_wallet(user_id)
        
        # Lock and update
        wallet = self.db.query(CreditWallet).filter(
            CreditWallet.user_id == user_id
        ).with_for_update().first()
        
        wallet.balance_credits += amount
        
        transaction = CreditTransaction(
            user_id=user_id,
            delta_credits=amount,
            type=TransactionType.REFUND.value,
            reason=reason,
            stripe_event_id=stripe_event_id
        )
        self.db.add(transaction)
        
        self.db.commit()
        self.db.refresh(transaction)
        
        return transaction
    
    def grant_credits(
        self,
        user_id: int,
        amount: int,
        reason: str
    ) -> CreditTransaction:
        """
        Grant free credits to a user (admin function).
        
        This is used for promotional credits, compensation, or admin grants.
        Always adds credits (amount must be positive).
        
        Args:
            user_id: User ID
            amount: Amount of credits to grant (must be positive)
            reason: Reason for grant
            
        Returns:
            CreditTransaction record for the grant
            
        Raises:
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("Grant amount must be positive")
        
        # Get or create wallet
        wallet = self.get_or_create_wallet(user_id)
        
        # Lock the wallet row
        wallet = self.db.query(CreditWallet).filter(
            CreditWallet.user_id == user_id
        ).with_for_update().first()
        
        # Add credits
        wallet.balance_credits += amount
        
        transaction = CreditTransaction(
            user_id=user_id,
            delta_credits=amount,
            type=TransactionType.GRANT.value,
            reason=reason
        )
        self.db.add(transaction)
        
        self.db.commit()
        self.db.refresh(transaction)
        
        return transaction
    
    def add_adjustment(
        self,
        user_id: int,
        amount: int,
        reason: str
    ) -> CreditTransaction:
        """
        Add a manual credit adjustment (admin function).
        
        Can be positive (add) or negative (deduct).
        For free credit grants, prefer using grant_credits() method.
        
        Args:
            user_id: User ID
            amount: Amount of credits (can be positive or negative)
            reason: Reason for adjustment
            
        Returns:
            CreditTransaction record for the adjustment
            
        Raises:
            UserWalletNotFoundError: If user doesn't have a wallet (for deductions)
            InsufficientCreditsError: If trying to deduct more than available
        """
        # Get or create wallet for positive adjustments
        if amount > 0:
            wallet = self.get_or_create_wallet(user_id)
        else:
            wallet = self.get_wallet(user_id)
            if not wallet:
                raise UserWalletNotFoundError(user_id)
        
        # Lock the wallet row
        wallet = self.db.query(CreditWallet).filter(
            CreditWallet.user_id == user_id
        ).with_for_update().first()
        
        # Check for negative adjustment
        if amount < 0 and wallet.balance_credits < abs(amount):
            raise InsufficientCreditsError(
                available=wallet.balance_credits,
                required=abs(amount)
            )
        
        # Apply adjustment
        wallet.balance_credits += amount
        
        transaction = CreditTransaction(
            user_id=user_id,
            delta_credits=amount,
            type=TransactionType.ADJUSTMENT.value,
            reason=reason
        )
        self.db.add(transaction)
        
        self.db.commit()
        self.db.refresh(transaction)
        
        return transaction
    
    def get_transactions(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        transaction_type: Optional[str] = None
    ) -> List[CreditTransaction]:
        """
        Get transaction history for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip
            transaction_type: Optional filter by transaction type
            
        Returns:
            List of CreditTransaction records
        """
        query = self.db.query(CreditTransaction).filter(
            CreditTransaction.user_id == user_id
        )
        
        if transaction_type:
            query = query.filter(CreditTransaction.type == transaction_type)
        
        return query.order_by(
            CreditTransaction.created_at.desc()
        ).offset(offset).limit(limit).all()
    
    def get_transaction_count(
        self,
        user_id: int,
        transaction_type: Optional[str] = None
    ) -> int:
        """
        Get total count of transactions for a user.
        
        Args:
            user_id: User ID
            transaction_type: Optional filter by transaction type
            
        Returns:
            Total transaction count
        """
        query = self.db.query(func.count(CreditTransaction.id)).filter(
            CreditTransaction.user_id == user_id
        )
        
        if transaction_type:
            query = query.filter(CreditTransaction.type == transaction_type)
        
        return query.scalar() or 0
    
    def can_afford_agents(
        self,
        user_id: int,
        agent_ids: List[str]
    ) -> dict:
        """
        Check if user can afford to run a list of agents.
        
        Useful for pre-flight validation before starting analysis.
        
        Args:
            user_id: User ID
            agent_ids: List of agent IDs to check
            
        Returns:
            Dictionary with:
            - can_afford: Boolean indicating if all agents can be afforded
            - balance: Current balance
            - total_cost: Total cost of all agents
            - breakdown: Cost breakdown by agent
            - missing_agents: Agents without configured costs
            - shortfall: Amount needed if can't afford (0 if can afford)
        """
        balance = self.get_balance(user_id)
        cost_info = self.agent_costs_service.get_total_cost_for_agents(agent_ids)
        
        can_afford = balance >= cost_info["total_cost"] and not cost_info["missing_agents"]
        shortfall = max(0, cost_info["total_cost"] - balance)
        
        return {
            "can_afford": can_afford,
            "balance": balance,
            "total_cost": cost_info["total_cost"],
            "breakdown": cost_info["breakdown"],
            "missing_agents": cost_info["missing_agents"],
            "shortfall": shortfall
        }
