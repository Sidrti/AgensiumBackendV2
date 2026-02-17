#!/usr/bin/env python3
"""
Add missing agents from analyze-my-data tool with cost = 1 credit each.

This script adds the three agents that are defined in the analyze-my-data tool
but are missing from the agent_costs table in the database.
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from db.database import SessionLocal
from db.models import AgentCost
from datetime import datetime


def add_analyze_my_data_agents():
    """Add the missing agents from analyze-my-data tool."""
    
    # Define the agents to add
    missing_agents = [
        {
            "agent_id": "synthetic-control-agent",
            "cost": 1,
            "description": "Synthetic control for campaign impact measurement"
        },
        {
            "agent_id": "control-group-holdout-planner-agent",
            "cost": 1,
            "description": "Control group holdout planning and sample size calculation"
        }
    ]
    
    db = SessionLocal()
    
    try:
        print("=" * 90)
        print("📝 ADDING MISSING AGENTS FROM ANALYZE-MY-DATA TOOL")
        print("=" * 90)
        
        added_count = 0
        skipped_count = 0
        
        for agent_config in missing_agents:
            agent_id = agent_config["agent_id"]
            
            # Check if agent already exists
            existing = db.query(AgentCost).filter(
                AgentCost.agent_id == agent_id
            ).first()
            
            if existing:
                print(f"\n⏭️  SKIPPED: {agent_id}")
                print(f"   Already exists with cost: {existing.cost}")
                skipped_count += 1
            else:
                # Create new agent cost record
                agent_cost = AgentCost(
                    agent_id=agent_id,
                    cost=agent_config["cost"],
                    description=agent_config["description"],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(agent_cost)
                print(f"\n✅ ADDED: {agent_id}")
                print(f"   Cost: {agent_config['cost']} credit(s)")
                print(f"   Description: {agent_config['description']}")
                added_count += 1
        
        # Commit all changes
        if added_count > 0:
            db.commit()
            print("\n" + "=" * 90)
            print(f"✓ Successfully added {added_count} agent(s) to database")
            print(f"✓ Skipped {skipped_count} agent(s) (already exist)")
            print("=" * 90)
        else:
            print("\n" + "=" * 90)
            print(f"✓ All agents already exist in database")
            print("=" * 90)
        
        # Show all agents in analyze-my-data tool
        print("\n📊 All Analyze-My-Data Agents in Database Now:")
        print("-" * 90)
        
        all_analyze_agents = db.query(AgentCost).filter(
            AgentCost.agent_id.in_([a["agent_id"] for a in missing_agents])
        ).order_by(AgentCost.agent_id).all()
        
        for agent in all_analyze_agents:
            print(f"  ✓ {agent.agent_id:<40} {agent.cost} credit  | {agent.description}")
        
        print("-" * 90)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    add_analyze_my_data_agents()
