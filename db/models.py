"""
SQLAlchemy models for MySQL database.
"""
from sqlalchemy import Boolean, Column, Integer, String, DateTime, Enum, ForeignKey, JSON, Text, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
import enum


class OTPType(str, enum.Enum):
    """Enum for OTP types to ensure type safety."""
    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"


class TransactionType(str, enum.Enum):
    """Enum for credit transaction types."""
    PURCHASE = "PURCHASE"
    CONSUME = "CONSUME"
    REFUND = "REFUND"
    ADJUSTMENT = "ADJUSTMENT"


class User(Base):
    """User model with OTP verification support and Stripe integration."""

    __tablename__ = "users"

    # Primary Fields
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)

    # Stripe Integration
    stripe_customer_id = Column(String(255), unique=True, nullable=True, index=True)

    # Status Fields
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # OTP Fields
    otp_code = Column(String(6), nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    otp_type = Column(String(50), nullable=True)  # 'registration' or 'password_reset'

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    wallet = relationship("CreditWallet", back_populates="user", uselist=False)
    transactions = relationship("CreditTransaction", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, is_verified={self.is_verified})>"


class CreditWallet(Base):
    """
    Credit wallet model for storing user credit balance.
    Each user has exactly one wallet.
    Balance cannot go negative (enforced at application level with row-level locking).
    """

    __tablename__ = "credit_wallets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    balance_credits = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="wallet")

    # Constraint to ensure balance is never negative
    __table_args__ = (
        CheckConstraint('balance_credits >= 0', name='check_balance_non_negative'),
    )

    def __repr__(self):
        return f"<CreditWallet(user_id={self.user_id}, balance={self.balance_credits})>"


class CreditTransaction(Base):
    """
    Credit transaction ledger for audit trail.
    Records all credit changes: purchases, consumption, refunds, adjustments.
    """

    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Transaction details
    delta_credits = Column(Integer, nullable=False)  # Positive for credits in, negative for credits out
    type = Column(String(50), nullable=False)  # PURCHASE, CONSUME, REFUND, ADJUSTMENT
    reason = Column(String(500), nullable=True)  # Human-readable reason
    
    # Agent execution context (for CONSUME transactions)
    agent_id = Column(String(100), nullable=True, index=True)
    tool_id = Column(String(100), nullable=True)
    analysis_id = Column(String(100), nullable=True)
    
    # Stripe linkage (for PURCHASE transactions) - unique constraints for idempotency
    stripe_checkout_session_id = Column(String(255), unique=True, nullable=True)
    stripe_payment_intent_id = Column(String(255), unique=True, nullable=True)
    stripe_event_id = Column(String(255), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="transactions")

    def __repr__(self):
        return f"<CreditTransaction(id={self.id}, user_id={self.user_id}, delta={self.delta_credits}, type={self.type})>"


class StripeWebhookEvent(Base):
    """
    Stripe webhook event tracker for idempotency.
    Prevents duplicate processing of webhook events.
    """

    __tablename__ = "stripe_webhook_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    stripe_event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    
    # Processing status
    received_at = Column(DateTime, server_default=func.now(), nullable=False)
    processed_at = Column(DateTime, nullable=True)
    
    # Optional: Store payload for debugging (be careful with PII)
    payload_json = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<StripeWebhookEvent(id={self.id}, event_id={self.stripe_event_id}, type={self.event_type})>"


class AgentCost(Base):
    """
    Agent cost table for pricing.
    Stores the credit cost for each agent execution.
    All agent IDs are stored in hyphenated lowercase format.
    """

    __tablename__ = "agent_costs"

    agent_id = Column(String(100), primary_key=True)  # e.g., "semantic-mapper"
    cost = Column(Integer, nullable=False)  # Credits required per execution
    description = Column(String(255), nullable=True)  # Optional description
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<AgentCost(agent_id={self.agent_id}, cost={self.cost})>"
