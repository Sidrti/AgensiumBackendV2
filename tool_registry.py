"""
Tool registry for cached tool definitions.

Loads tool definitions from backend/tools once and reuses them across the app.
"""

import json
import os
from typing import Dict, Any

_TOOL_DEFINITIONS_CACHE: Dict[str, Dict[str, Any]] | None = None


def _load_tool_definitions_from_disk() -> Dict[str, Dict[str, Any]]:
    """Load tool definitions from tools directory on disk."""
    tool_definitions: Dict[str, Dict[str, Any]] = {}
    tools_dir = os.path.join(os.path.dirname(__file__), "tools")

    try:
        if os.path.exists(tools_dir):
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
