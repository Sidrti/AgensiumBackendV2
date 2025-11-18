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
from dotenv import load_dotenv

# Load environment variables early
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router


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


# ============================================================================
# RUN
# ============================================================================


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=8000)

