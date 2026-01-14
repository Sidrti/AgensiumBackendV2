#!/usr/bin/env python3
"""
Fetch all agents with their costs from the database.

This script connects to the database and retrieves all AgentCost records,
displaying them in a formatted table.
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from db.database import SessionLocal
from db.models import AgentCost
from billing.agent_costs_service import AgentCostsService, DEFAULT_AGENT_COSTS


def fetch_all_agents():
    """Fetch all agents from database and display them."""
    db = SessionLocal()
    
    try:
        # Query all agent costs
        agent_costs = db.query(AgentCost).order_by(AgentCost.agent_id).all()
        
        if not agent_costs:
            print("❌ No agent costs found in database!")
            print("\n📋 Default agent costs available (not seeded):")
            print_default_costs()
            return
        
        print("=" * 90)
        print("📊 AGENT COSTS FROM DATABASE")
        print("=" * 90)
        print(f"\n{'Agent ID':<30} {'Cost (Credits)':<20} {'Description':<40}")
        print("-" * 90)
        
        total_agents = 0
        total_cost = 0
        
        for agent in agent_costs:
            description = agent.description or "N/A"
            print(f"{agent.agent_id:<30} {agent.cost:<20} {description:<40}")
            total_agents += 1
            total_cost += agent.cost
        
        print("-" * 90)
        print(f"{'TOTAL':<30} {total_agents} agents | {total_cost} total credits")
        print("=" * 90)
        
        # Check for missing agents from defaults
        db_agent_ids = {agent.agent_id for agent in agent_costs}
        default_agent_ids = set(DEFAULT_AGENT_COSTS.keys())
        missing = default_agent_ids - db_agent_ids
        
        if missing:
            print(f"\n⚠️  Missing agents from database ({len(missing)}):")
            for agent_id in sorted(missing):
                config = DEFAULT_AGENT_COSTS[agent_id]
                print(f"   - {agent_id:<30} {config['cost']} credits  (default)")
        
        # Extra agents in DB not in defaults
        extra = db_agent_ids - default_agent_ids
        if extra:
            print(f"\n✓ Extra agents in database ({len(extra)}):")
            for agent_id in sorted(extra):
                agent = next(a for a in agent_costs if a.agent_id == agent_id)
                print(f"   - {agent_id:<30} {agent.cost} credits")
        
    finally:
        db.close()


def print_default_costs():
    """Print default agent costs."""
    print(f"\n{'Agent ID':<30} {'Default Cost':<20} {'Description':<40}")
    print("-" * 90)
    
    for agent_id in sorted(DEFAULT_AGENT_COSTS.keys()):
        config = DEFAULT_AGENT_COSTS[agent_id]
        print(f"{agent_id:<30} {config['cost']:<20} {config['description']:<40}")


def seed_agents():
    """Seed the database with default agent costs."""
    from billing.agent_costs_service import seed_default_agent_costs
    
    db = SessionLocal()
    
    try:
        print("🌱 Seeding default agent costs...")
        seed_default_agent_costs(db)
        print("✓ Seeding complete!")
        
        # Show what was seeded
        fetch_all_agents()
        
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fetch agent costs from database")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed database with default agent costs if missing"
    )
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Show default agent costs (not from database)"
    )
    
    args = parser.parse_args()
    
    if args.defaults:
        print("=" * 90)
        print("📋 DEFAULT AGENT COSTS")
        print("=" * 90)
        print_default_costs()
    elif args.seed:
        seed_agents()
    else:
        fetch_all_agents()
