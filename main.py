"""
Agensium Backend API

Unified API for data analysis and mastering tools.
Architecture:
1. Load tool definitions from tools directory
2. Initialize FastAPI app with CORS support
3. Import routes from api module
4. Routes handle agent execution and response transformation
"""

import json
import os
import sys
from dotenv import load_dotenv

# Add project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables early
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router
from auth.router import router as auth_router
from db import models, database
from fastapi.responses import JSONResponse
from auth.exceptions import AuthException

# Create database tables - wrapped in try-except to prevent startup failures
# Note: create_all is currently causing a silent crash on some environments.
# If tables are missing, please use a separate migration script.
try:
    # models.Base.metadata.create_all(bind=database.engine)
    # print("✓ Database tables created successfully")
    pass
except Exception as e:
    print(f"⚠ Warning: Could not create database tables at startup: {e}")
    print("  Tables will be created when database becomes available.")

# ============================================================================
# INITIALIZE APP
# ============================================================================

app = FastAPI(
    title="Agensium Backend",
    description="Data Analysis and Mastering Platform",
    version="1.0.0"
)

# Load environment variables from .env file (if present)
load_dotenv()

# Configure CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173") # Use an environment variable for best practice

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "https://agensium2.netlify.app" # The specific URL causing the error
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load tool definitions from tools directory
TOOL_DEFINITIONS = {}
TOOLS_DIR = os.path.join(os.path.dirname(__file__), "tools")

def load_tool_definitions():
    """Dynamically load all tool definitions from tools directory"""
    global TOOL_DEFINITIONS
    
    try:
        # List all JSON files in tools directory
        if os.path.exists(TOOLS_DIR):
            for filename in os.listdir(TOOLS_DIR):
                if filename.endswith("_tool.json"):
                    filepath = os.path.join(TOOLS_DIR, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            tool_def = json.load(f)
                            # Extract tool ID from definition
                            tool_id = tool_def.get("tool", {}).get("id", filename.replace("_tool.json", ""))
                            TOOL_DEFINITIONS[tool_id] = tool_def
                            print(f"✓ Loaded tool: {tool_id} from {filename}")
                    except Exception as e:
                        print(f"Warning: Could not load tool from {filename}: {e}")
        else:
            print(f"Warning: Tools directory not found at {TOOLS_DIR}")
    except Exception as e:
        print(f"Warning: Error loading tool definitions: {e}")

# Load tools on startup
load_tool_definitions()

if not TOOL_DEFINITIONS:
    print("Warning: No tools loaded!")

# Include API routes
app.include_router(router)
app.include_router(auth_router)


# Global handler for AuthException so responses include the configured error_code
@app.exception_handler(AuthException)
async def handle_auth_exception(request, exc: AuthException):
    content = {"detail": exc.detail}
    if getattr(exc, "error_code", None):
        content["error_code"] = exc.error_code
    # Use the headers if present
    headers = exc.headers if getattr(exc, "headers", None) else None
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)


# ============================================================================
# RUN
# ============================================================================


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=8000)

