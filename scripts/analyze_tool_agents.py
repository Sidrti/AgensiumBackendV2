#!/usr/bin/env python3
"""
Analyze tool definitions and find agents missing from database.
"""

import sys
import json
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from db.database import SessionLocal
from db.models import AgentCost


def analyze_tools():
    """Analyze all tool definitions to extract agent IDs."""
    tools_dir = Path(__file__).parent.parent / "tools"
    
    # Extract agents from tool definitions
    tool_agents = {}  # tool_id -> list of agent_ids
    all_agent_ids = set()
    
    for tool_file in sorted(tools_dir.glob("*_tool.json")):
        try:
            with open(tool_file, "r", encoding="utf-8") as f:
                tool_def = json.load(f)
                
            tool_id = tool_def.get("tool", {}).get("id")
            agents = tool_def.get("tool", {}).get("available_agents", [])
            
            if tool_id and agents:
                tool_agents[tool_id] = agents
                all_agent_ids.update(agents)
                
        except Exception as e:
            print(f"Error reading {tool_file}: {e}")
    
    return tool_agents, all_agent_ids


def main():
    """Main analysis function."""
    # Get agents from tools
    tool_agents, all_agent_ids = analyze_tools()
    
    # Get agents from database
    db = SessionLocal()
    try:
        db_agents = {cost.agent_id for cost in db.query(AgentCost).all()}
    finally:
        db.close()
    
    print("=" * 100)
    print("📊 AGENT DEFINITION ANALYSIS")
    print("=" * 100)
    
    print(f"\nTools Loaded: {len(tool_agents)}")
    for tool_id, agents in sorted(tool_agents.items()):
        print(f"  • {tool_id:<30} → {len(agents)} agents")
    
    print(f"\nTotal Unique Agents in Tools: {len(all_agent_ids)}")
    print(f"Total Agents in Database: {len(db_agents)}")
    
    # Find missing agents
    missing = all_agent_ids - db_agents
    extra = db_agents - all_agent_ids
    
    print("\n" + "=" * 100)
    print("🔴 AGENTS DEFINED IN TOOLS BUT MISSING FROM DATABASE")
    print("=" * 100)
    
    if missing:
        print(f"\n⚠️  {len(missing)} agents are referenced in tools but have NO COST defined:\n")
        for agent_id in sorted(missing):
            # Find which tools use this agent
            tools_using = [tool_id for tool_id, agents in tool_agents.items() if agent_id in agents]
            print(f"  ❌ {agent_id:<40} (used in: {', '.join(tools_using)})")
    else:
        print("\n✓ All tool agents have costs defined!")
    
    print("\n" + "=" * 100)
    print("🟢 AGENTS IN DATABASE BUT NOT IN TOOLS")
    print("=" * 100)
    
    if extra:
        print(f"\n✓ {len(extra)} agents in database but not currently used:\n")
        for agent_id in sorted(extra):
            print(f"  ○ {agent_id}")
    else:
        print("\n✓ No extra agents in database!")
    
    print("\n" + "=" * 100)
    print("⚡ IMPACT ANALYSIS")
    print("=" * 100)
    
    if missing:
        print(f"""
🚨 CRITICAL ISSUE DETECTED:

If a user tries to run any of these {len(missing)} agents, the system will:
  1. Hit the billing validation in validate_and_consume_all()
  2. The validation will succeed (because missing costs are skipped with warning)
  3. The agent cost loop will skip these agents (continue)
  4. Analysis completes "successfully" but agent NEVER RUNS
  5. User gets NO ERROR, NO ALERT - SILENT FAILURE ⚠️

Affected Tools:
""")
        
        affected_tools = set()
        for tool_id, agents in tool_agents.items():
            if any(agent in missing for agent in agents):
                affected_tools.add(tool_id)
                missing_in_tool = [a for a in agents if a in missing]
                print(f"  • {tool_id}")
                for agent in missing_in_tool:
                    print(f"    └─ ❌ {agent}")
    else:
        print("\n✓ No critical issues - all agents have costs defined!")
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
