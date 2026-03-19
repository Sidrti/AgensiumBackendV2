"""
Tool registry for cached tool definitions.

Loads tool definitions from backend/tools once and reuses them across the app.
"""

import json
import os
from typing import Dict, Any

_TOOL_DEFINITIONS_CACHE: Dict[str, Dict[str, Any]] | None = None


def _load_tool_definitions_from_disk() -> Dict[str, Dict[str, Any]]:
    """Load tool definitions from tools directory on disk.
    
    Loads two types of tool definitions:
    1. Individual *_tool.json files (standard format)
    2. other_tools.json array (bulk tool definitions)
    """
    tool_definitions: Dict[str, Dict[str, Any]] = {}
    tools_dir = os.path.join(os.path.dirname(__file__), "tools")

    try:
        if os.path.exists(tools_dir):
            # Load individual *_tool.json files
            for filename in os.listdir(tools_dir):
                if filename.endswith("_tool.json"):
                    filepath = os.path.join(tools_dir, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            tool_def = json.load(f)
                        tool_id = tool_def.get("tool", {}).get("id", filename.replace("_tool.json", ""))
                        tool_definitions[tool_id] = tool_def
                        print(f"✓ Loaded tool: {tool_id} from {filename}")
                    except Exception as e:
                        print(f"Warning: Could not load tool from {filename}: {e}")
            
            # Load other_tools.json (array of tool objects)
            other_tools_path = os.path.join(tools_dir, "other_tools.json")
            if os.path.exists(other_tools_path):
                try:
                    with open(other_tools_path, "r", encoding="utf-8") as f:
                        other_tools = json.load(f)
                    
                    if isinstance(other_tools, list):
                        for tool_obj in other_tools:
                            tool_id = tool_obj.get("id")
                            if not tool_id:
                                print(f"Warning: Tool in other_tools.json missing 'id' field")
                                continue
                            
                            # Normalize: convert "tag" to "tags" if needed
                            tags = tool_obj.get("tags", tool_obj.get("tag", []))
                            
                            # Wrap in standard tool definition format
                            normalized_tool = {
                                "tool": {
                                    "id": tool_obj.get("id"),
                                    "name": tool_obj.get("name"),
                                    "description": tool_obj.get("description", ""),
                                    "icon": tool_obj.get("icon", "🔧"),
                                    "category": tool_obj.get("category") or "source",
                                    "isAvailable": tool_obj.get("isAvailable", True),
                                    "status": tool_obj.get("status", "Private"),
                                    "tags": tags,
                                    "show": tool_obj.get("show", True),
                                    "version": tool_obj.get("version", "1.0.0"),
                                    "available_agents": tool_obj.get("available_agents", []),
                                    "files": tool_obj.get("files", {})
                                },
                                "agents": {}
                            }
                            
                            tool_definitions[tool_id] = normalized_tool
                            print(f"✓ Loaded tool: {tool_id} from other_tools.json")
                    else:
                        print(f"Warning: other_tools.json is not an array")
                except Exception as e:
                    print(f"Warning: Could not load other_tools.json: {e}")
        else:
            print(f"Warning: Tools directory not found at {tools_dir}")
    except Exception as e:
        print(f"Warning: Error loading tool definitions: {e}")

    if not tool_definitions:
        print("Warning: No tools loaded!")

    return tool_definitions


def get_tool_definitions(force_reload: bool = False) -> Dict[str, Dict[str, Any]]:
    """Get cached tool definitions, loading from disk if needed."""
    global _TOOL_DEFINITIONS_CACHE

    if _TOOL_DEFINITIONS_CACHE is None or force_reload:
        _TOOL_DEFINITIONS_CACHE = _load_tool_definitions_from_disk()

    return _TOOL_DEFINITIONS_CACHE


def get_tool_config(tool_id: str) -> Dict[str, Any]:
    """Get a single tool definition by tool_id."""
    tool_definitions = get_tool_definitions()
    return tool_definitions.get(tool_id, {})
