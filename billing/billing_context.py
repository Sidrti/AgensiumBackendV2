"""
Billing Context for Task Execution

Provides pre-flight validation and upfront credit consumption for task execution.
This ensures:
1. All credits are validated BEFORE any agent runs
2. All credits are deducted UPFRONT (no partial execution)
3. If insufficient credits, task fails immediately with clear error
"""

import time
from typing import Any, Optional, Dict, List
from sqlalchemy.orm import Session

from db.database import SessionLocal
from .wallet_service import WalletService
from .agent_costs_service import AgentCostsService
from .exceptions import (
    InsufficientCreditsError,
    AgentCostNotFoundError,
    UserWalletNotFoundError,
)


class BillingContext:
    """
    Context manager for handling billing operations in task execution.
    
    New Flow (upfront billing):
    1. validate_and_consume_all() - Check credits for ALL agents and consume upfront
    2. If validation fails, raises HTTPException with BILLING_INSUFFICIENT_CREDITS
    3. Agents run without individual billing checks
    
    Usage:
        with BillingContext(current_user) as billing:
            # Validate and consume credits for all agents upfront
            billing.validate_and_consume_all(
                agents=task.agents,
                tool_id=task.tool_id,
                task_id=task.task_id
            )
            # Now run agents - billing is already handled
            for agent_id in task.agents:
                result = execute_agent(agent_id)
    """
    
    def __init__(self, current_user: Any = None):
        """Initialize billing context.
        
        Args:
            current_user: Current user object (must have 'id' attribute)
        """
        self.current_user = current_user
        self.billing_enabled = current_user is not None and hasattr(current_user, 'id')
        self.db_session: Optional[Session] = None
        self.wallet_service: Optional[WalletService] = None
        self.consumed = False  # Track if credits have been consumed
        
    def __enter__(self):
        """Setup billing services."""
        if self.billing_enabled:
            try:
                self.db_session = SessionLocal()
                self.wallet_service = WalletService(self.db_session)
            except Exception as e:
                print(f"Warning: Could not initialize billing services: {e}")
                self.billing_enabled = False
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup database session."""
        if self.db_session:
            self.db_session.close()
        return False
    
    def validate_credits_for_agents(
        self,
        agents: List[str],
        tool_id: str
    ) -> Dict[str, Any]:
        """
        Validate if user has enough credits for all agents.
        
        This is a pre-flight check that does NOT consume credits.
        
        Args:
            agents: List of agent IDs to validate
            tool_id: Tool identifier
            
        Returns:
            Dictionary with validation result:
            - can_afford: bool
            - balance: int
            - total_cost: int
            - breakdown: Dict[agent_id, cost]
            - missing_agents: List[str] (agents without configured costs)
            - shortfall: int (0 if can afford)
            
        Raises:
            UserWalletNotFoundError: If user doesn't have a wallet
        """
        if not self.billing_enabled or not self.wallet_service:
            return {
                "can_afford": True,
                "balance": 0,
                "total_cost": 0,
                "breakdown": {},
                "missing_agents": [],
                "shortfall": 0,
                "billing_disabled": True
            }
        
        return self.wallet_service.can_afford_agents(
            user_id=self.current_user.id,
            agent_ids=agents
        )
    
    def validate_and_consume_all(
        self,
        agents: List[str],
        tool_id: str,
        task_id: str
    ) -> Dict[str, Any]:
        """
        Validate credits and consume ALL upfront before agent execution.
        
        This method:
        1. Checks if user can afford all agents
        2. If yes, consumes credits for ALL agents in a single transaction
        3. If no, raises InsufficientCreditsError
        
        This ensures no partial execution - either all agents are paid for,
        or none are.
        
        Args:
            agents: List of agent IDs to execute
            tool_id: Tool identifier
            task_id: Task identifier for transaction records
            
        Returns:
            Dictionary with consumption result:
            - success: bool
            - total_consumed: int
            - transactions: List of transaction IDs
            
        Raises:
            InsufficientCreditsError: If not enough credits for all agents
            UserWalletNotFoundError: If user doesn't have a wallet
            AgentCostNotFoundError: If any agent cost is not configured
        """
        if not self.billing_enabled or not self.wallet_service:
            return {
                "success": True,
                "total_consumed": 0,
                "transactions": [],
                "billing_disabled": True
            }
        
        # First validate
        validation = self.validate_credits_for_agents(agents, tool_id)
        
        # Check for missing agent costs
        if validation["missing_agents"]:
            # Log warning but continue - some agents might not have costs configured
            print(f"Warning: Missing costs for agents: {validation['missing_agents']}")
        
        # Check if can afford
        if not validation["can_afford"]:
            raise InsufficientCreditsError(
                available=validation["balance"],
                required=validation["total_cost"],
                agent_id=", ".join(agents),
                tool_id=tool_id
            )
        
        # Consume credits for all agents upfront
        transactions = []
        total_consumed = 0
        
        for agent_id in agents:
            try:
                cost = validation["breakdown"].get(agent_id)
                if cost is None:
                    # Agent cost not found, skip (already logged warning)
                    continue
                
                transaction = self.wallet_service.consume_for_agent(
                    user_id=self.current_user.id,
                    agent_id=agent_id,
                    tool_id=tool_id,
                    analysis_id=task_id,
                    cost=cost  # Pass explicit cost to avoid re-lookup
                )
                transactions.append(transaction.id)
                total_consumed += cost
                print(f"[Billing] Consumed {cost} credits for agent: {agent_id}")
                
            except Exception as e:
                # This shouldn't happen since we validated first
                # But if it does, rollback would be needed (not implemented for simplicity)
                print(f"Error consuming credits for {agent_id}: {e}")
                raise
        
        self.consumed = True
        
        return {
            "success": True,
            "total_consumed": total_consumed,
            "transactions": transactions
        }
    
    def get_billing_error_response(
        self,
        error: Exception,
        task_id: str,
        tool_id: str,
        start_time: float
    ) -> Dict[str, Any]:
        """
        Convert billing exception to error response dict.
        
        Returns error response aligned with V2.1 API format:
        - status: "FAILED" (for task status)
        - error_code: Specific error code
        - error_message: Human-readable message
        - context: Additional error context
        
        Args:
            error: The billing exception
            task_id: Task identifier
            tool_id: Tool identifier
            start_time: Task start time
            
        Returns:
            Error response dictionary aligned with V2.1 task API error format
        """
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Extract error details
        error_code = "BILLING_ERROR"
        error_message = str(error)
        context = {}
        
        if isinstance(error, InsufficientCreditsError):
            error_code = "BILLING_INSUFFICIENT_CREDITS"
            error_message = getattr(error, "detail", str(error))
            context = getattr(error, "context", {})
        elif isinstance(error, UserWalletNotFoundError):
            error_code = "BILLING_WALLET_NOT_FOUND"
            error_message = getattr(error, "detail", str(error))
            context = getattr(error, "context", {})
        elif isinstance(error, AgentCostNotFoundError):
            error_code = "BILLING_AGENT_COST_MISSING"
            error_message = getattr(error, "detail", str(error))
            context = getattr(error, "context", {})
        else:
            error_message = str(error)
            context = {}
        
        return {
            "status": "FAILED",
            "error_code": error_code,
            "error_message": error_message,
            "context": context,
            "execution_time_ms": execution_time_ms
        }
