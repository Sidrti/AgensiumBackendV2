"""
Agensium Backend API

Unified API for data analysis and mastering tools.
Architecture:
1. Load tool definitions from tools directory
2. Initialize FastAPI app with CORS support
3. Import routes from api module
4. Routes handle agent execution and response transformation
"""

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
from api.task_routes import router as task_router  # V2.1: Task API
from auth.router import router as auth_router
from billing.router import router as billing_router
from billing.exceptions import BillingException
from db import models, database
from fastapi.responses import JSONResponse
from auth.exceptions import AuthException
from tool_registry import get_tool_definitions

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
# Use an environment variable for best practice
# FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Local development URL
        "https://agensium2.netlify.app"  # Production frontend URL from environment
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load tool definitions from tools directory
TOOL_DEFINITIONS = {}

def load_tool_definitions():
    """Dynamically load all tool definitions from tools registry"""
    global TOOL_DEFINITIONS
    TOOL_DEFINITIONS = get_tool_definitions(force_reload=True)

# Load tools on startup
load_tool_definitions()

if not TOOL_DEFINITIONS:
    print("Warning: No tools loaded!")

# Include API routes
app.include_router(router)
app.include_router(task_router)  # V2.1: Task API endpoints
app.include_router(auth_router)
app.include_router(billing_router)


# Global handler for AuthException so responses include the configured error_code
@app.exception_handler(AuthException)
async def handle_auth_exception(request, exc: AuthException):
    content = {"detail": exc.detail}
    if getattr(exc, "error_code", None):
        content["error_code"] = exc.error_code
    # Use the headers if present
    headers = exc.headers if getattr(exc, "headers", None) else None
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)


# Global handler for BillingException so responses include error_code and context
@app.exception_handler(BillingException)
async def handle_billing_exception(request, exc: BillingException):
    content = {
        "detail": exc.detail,
        "error_code": exc.error_code,
    }
    if exc.context:
        content["context"] = exc.context
    return JSONResponse(status_code=exc.status_code, content=content)


# ============================================================================
# RUN
# ============================================================================


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=8000)

