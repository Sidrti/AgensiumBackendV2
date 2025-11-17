"""
API Dependencies and Utilities

Shared functions for agent execution and file handling.
"""

import base64
from typing import Dict, Any, Optional
from fastapi import HTTPException


def decode_base64_file(base64_data: str) -> bytes:
    """Decode base64-encoded file."""
    try:
        return base64.b64decode(base64_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 encoding: {str(e)}")
