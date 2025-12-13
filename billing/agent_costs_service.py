"""
Agent Costs Service

Handles agent pricing lookup with ID normalization.
All agent IDs are stored in hyphenated lowercase format.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from db.models import AgentCost
from .exceptions import AgentCostNotFoundError


def normalize_agent_id(agent_id: str) -> str:
    """
    Normalize agent ID to hyphenated lowercase format.
    
    Converts snake_case and other formats to hyphenated lowercase.
    This ensures consistent lookup regardless of input format.
    
    Examples:
        normalize_agent_id("semantic_mapper") -> "semantic-mapper"
        normalize_agent_id("SEMANTIC_MAPPER") -> "semantic-mapper"
        normalize_agent_id("semantic-mapper") -> "semantic-mapper"
        normalize_agent_id("SemanticMapper") -> "semanticmapper" (camelCase not supported)
    
    Args:
        agent_id: Agent identifier in any format
        
    Returns:
        Normalized agent ID in hyphenated lowercase
    """
    if not agent_id:
        return ""
    return agent_id.lower().strip().replace("_", "-")


class AgentCostsService:
    """
    Service for managing agent costs/pricing.
    
    Provides methods for:
    - Looking up agent costs
    - Listing all agent costs
    - Creating/updating agent costs (admin)
    """
    
    def __init__(self, db: Session):
        """
        Initialize the service with a database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def get_agent_cost(self, agent_id: str) -> int:
        """
        Get the credit cost for an agent.
        
        Args:
            agent_id: Agent identifier (will be normalized)
            
        Returns:
            Cost in credits
            
        Raises:
            AgentCostNotFoundError: If agent cost is not configured
        """
        normalized_id = normalize_agent_id(agent_id)
        
        agent_cost = self.db.query(AgentCost).filter(
            AgentCost.agent_id == normalized_id
        ).first()
        
        if not agent_cost:
            raise AgentCostNotFoundError(normalized_id)
        
        return agent_cost.cost
    
    def get_agent_cost_record(self, agent_id: str) -> Optional[AgentCost]:
        """
        Get the full AgentCost record for an agent.
        
        Args:
            agent_id: Agent identifier (will be normalized)
            
        Returns:
            AgentCost record or None if not found
        """
        normalized_id = normalize_agent_id(agent_id)
        
        return self.db.query(AgentCost).filter(
            AgentCost.agent_id == normalized_id
        ).first()
    
    def list_all_costs(self) -> List[AgentCost]:
        """
        List all agent costs.
        
        Returns:
            List of all AgentCost records
        """
        return self.db.query(AgentCost).order_by(AgentCost.agent_id).all()
    
    def set_agent_cost(
        self,
        agent_id: str,
        cost: int,
        description: Optional[str] = None
    ) -> AgentCost:
        """
        Set or update the cost for an agent.
        
        Creates a new record if it doesn't exist, otherwise updates existing.
        
        Args:
            agent_id: Agent identifier (will be normalized)
            cost: Cost in credits (must be positive)
            description: Optional description for the agent
            
        Returns:
            The created/updated AgentCost record
            
        Raises:
            ValueError: If cost is not positive
        """
        if cost <= 0:
            raise ValueError("Cost must be a positive integer")
        
        normalized_id = normalize_agent_id(agent_id)
        
        agent_cost = self.db.query(AgentCost).filter(
            AgentCost.agent_id == normalized_id
        ).first()
        
        if agent_cost:
            # Update existing
            agent_cost.cost = cost
            if description is not None:
                agent_cost.description = description
        else:
            # Create new
            agent_cost = AgentCost(
                agent_id=normalized_id,
                cost=cost,
                description=description
            )
            self.db.add(agent_cost)
        
        self.db.commit()
        self.db.refresh(agent_cost)
        
        return agent_cost
    
    def delete_agent_cost(self, agent_id: str) -> bool:
        """
        Delete an agent cost record.
        
        Args:
            agent_id: Agent identifier (will be normalized)
            
        Returns:
            True if deleted, False if not found
        """
        normalized_id = normalize_agent_id(agent_id)
        
        agent_cost = self.db.query(AgentCost).filter(
            AgentCost.agent_id == normalized_id
        ).first()
        
        if agent_cost:
            self.db.delete(agent_cost)
            self.db.commit()
            return True
        
        return False
    
    def get_total_cost_for_agents(self, agent_ids: List[str]) -> Dict[str, Any]:
        """
        Calculate the total cost for a list of agents.
        
        Useful for pre-flight cost estimation before running agents.
        
        Args:
            agent_ids: List of agent identifiers
            
        Returns:
            Dictionary with:
            - total_cost: Total credits required
            - breakdown: Dict of agent_id -> cost
            - missing_agents: List of agents without configured costs
        """
        total_cost = 0
        breakdown = {}
        missing_agents = []
        
        for agent_id in agent_ids:
            normalized_id = normalize_agent_id(agent_id)
            
            try:
                cost = self.get_agent_cost(agent_id)
                breakdown[normalized_id] = cost
                total_cost += cost
            except AgentCostNotFoundError:
                missing_agents.append(normalized_id)
        
        return {
            "total_cost": total_cost,
            "breakdown": breakdown,
            "missing_agents": missing_agents
        }


# Default agent costs - used for initial seeding
DEFAULT_AGENT_COSTS = {
    # Profile My Data agents
    "unified-profiler": {"cost": 30, "description": "Data profiling and statistics"},
    "readiness-rater": {"cost": 25, "description": "Data readiness assessment"},
    "drift-detector": {"cost": 40, "description": "Data drift detection"},
    "score-risk": {"cost": 35, "description": "Risk scoring"},
    "governance-checker": {"cost": 45, "description": "Governance compliance check"},
    "test-coverage-agent": {"cost": 30, "description": "Test coverage analysis"},
    
    # Clean My Data agents
    "null-handler": {"cost": 30, "description": "Null value handling"},
    "outlier-remover": {"cost": 35, "description": "Outlier detection and removal"},
    "type-fixer": {"cost": 25, "description": "Data type correction"},
    "duplicate-resolver": {"cost": 50, "description": "Duplicate detection and resolution"},
    "field-standardization": {"cost": 40, "description": "Field value standardization"},
    "quarantine-agent": {"cost": 35, "description": "Data quarantine management"},
    "cleanse-writeback": {"cost": 30, "description": "Cleaned data writeback"},
    "cleanse-previewer": {"cost": 20, "description": "Cleanse preview generation"},
    
    # Master My Data agents
    "key-identifier": {"cost": 45, "description": "Key field identification"},
    "contract-enforcer": {"cost": 75, "description": "Data contract enforcement"},
    "semantic-mapper": {"cost": 50, "description": "Semantic mapping"},
    "lineage-tracer": {"cost": 55, "description": "Data lineage tracing"},
    "golden-record-builder": {"cost": 150, "description": "Golden record construction"},
    "survivorship-resolver": {"cost": 100, "description": "Survivorship rule resolution"},
    "master-writeback-agent": {"cost": 60, "description": "Master data writeback"},
    "stewardship-flagger": {"cost": 40, "description": "Data stewardship flagging"},
}


def seed_default_agent_costs(db: Session) -> None:
    """
    Seed the database with default agent costs.
    
    Only creates records that don't already exist.
    
    Args:
        db: SQLAlchemy database session
    """
    service = AgentCostsService(db)
    
    for agent_id, config in DEFAULT_AGENT_COSTS.items():
        existing = service.get_agent_cost_record(agent_id)
        if not existing:
            service.set_agent_cost(
                agent_id=agent_id,
                cost=config["cost"],
                description=config.get("description")
            )
            print(f"✓ Seeded agent cost: {agent_id} = {config['cost']} credits")
