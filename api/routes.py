"""
API Routes and Endpoints

All API endpoints for tool management and data analysis.
Supports flexible file handling based on tool definitions.
"""

import json
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Depends

from transformers import profile_my_data_transformer, clean_my_data_transformer, master_my_data_transformer
from transformers.transformers_utils import persist_analysis_inputs
from ai import ChatAgent
from auth.dependencies import get_current_active_verified_user
from db import models

# Create router for API routes
router = APIRouter()


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/")
async def root():
    """Root endpoint with API information."""
    # Import here to avoid circular dependency
    from main import TOOL_DEFINITIONS
    
    return {
        "service": "Agensium Backend",
        "version": "1.0.0",
        "tools": list(TOOL_DEFINITIONS.keys()),
        "documentation": "/docs"
    }


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/tools")
async def list_tools():
    """List all available tools."""
    from main import TOOL_DEFINITIONS
    
    tools = []
    for tool_id, tool_def in TOOL_DEFINITIONS.items():
        tools.append({
            "id": tool_id,
            "name": tool_def["tool"]["name"],
            "description": tool_def["tool"]["description"],
            "icon": tool_def["tool"].get("icon", "🔧"),
            "category": tool_def["tool"].get("category", "source"),
            "isAvailable": tool_def["tool"].get("isAvailable", True),
            "available_agents": tool_def["tool"]["available_agents"],
            "required_files": list(tool_def["tool"].get("files", {}).keys())
        })
    return {"tools": tools}


@router.get("/tools/{tool_id}")
async def get_tool(tool_id: str):
    """Get tool definition with file requirements and agent specifications."""
    from main import TOOL_DEFINITIONS
    
    if tool_id not in TOOL_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    
    tool_def = TOOL_DEFINITIONS[tool_id]
    
    # Enhance tool definition with category and availability
    enhanced_tool = {
        **tool_def["tool"],
        "category": tool_def["tool"].get("category", "source"),
        "isAvailable": tool_def["tool"].get("isAvailable", True)
    }
    
    # Return tool definition with file requirements highlighted
    return {
        "tool": enhanced_tool,
        "agents": tool_def.get("agents", {}),
        "file_requirements": tool_def["tool"].get("files", {})
    }


@router.post("/analyze")
async def analyze(
    tool_id: str = Form(...),
    agents: Optional[str] = Form(None),
    parameters_json: Optional[str] = Form(None),
    primary: Optional[UploadFile] = File(None),
    baseline: Optional[UploadFile] = File(None),
    current_user: models.User = Depends(get_current_active_verified_user)
):
    """
    Analyze data using specified tool and agents.
    
    Args:
        tool_id: Tool identifier (e.g., "profile-my-data")
        agents: Comma-separated agent IDs (optional, uses tool defaults)
        parameters_json: JSON string with agent-specific parameters
        primary: Primary data file (required for most tools)
        baseline: Optional baseline/reference file (for drift detection and comparisons)
        current_user: Authenticated user
        
    Returns:
        Unified analysis response with analysis_id, status, and results
    """
    print(f"Analysis requested by user: {current_user.id} ({current_user.email})")
    
    analysis_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Persist inputs under uploads/<user_id>/<analysis_id>/inputs
        # NOTE: This will reset file pointers so transformers can read them again.
        # _ = await persist_analysis_inputs(
        #     user_id=current_user.id,
        #     analysis_id=analysis_id,
        #     primary=primary,
        #     baseline=baseline,
        #     parameters_json=parameters_json,
        # )
        
        # Execute analysis via transformer
        if tool_id == "profile-my-data":
            final_response = await profile_my_data_transformer.run_profile_my_data_analysis(
                tool_id,
                agents,
                parameters_json,
                primary,
                baseline,
                analysis_id,
                current_user
            )
        elif tool_id == "clean-my-data":
            final_response = await clean_my_data_transformer.run_clean_my_data_analysis(
                tool_id,
                agents,
                parameters_json,
                primary,
                baseline,
                analysis_id,
                current_user
            )
        elif tool_id == "master-my-data":
            final_response = await master_my_data_transformer.run_master_my_data_analysis(
                tool_id,
                agents,
                parameters_json,
                primary,
                baseline,
                analysis_id,
                current_user
            )
        else:
            # Default behavior for unknown tools (or just return error)
            final_response = {
                "analysis_id": analysis_id,
                "tool": tool_id,
                "status": "error",
                "error": f"Tool '{tool_id}' not supported for analysis execution",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }
        
        return final_response
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "analysis_id": analysis_id,
            "status": "error",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


# ============================================================================
# CHAT ENDPOINT
# ============================================================================

@router.post("/chat")
async def chat(
    question: str = Form(...),
    report_json: str = Form(...),
    conversation_history_json: Optional[str] = Form(None),
    current_user: models.User = Depends(get_current_active_verified_user)
):
    """
    Chat endpoint for Q&A on analysis reports.
    
    Ask questions about any analysis report and get AI-powered answers.
    Supports all tools (profile-my-data, clean-my-data, etc.) and conversation history for follow-up questions.
    
    Args:
        question: User's question about the report
        report_json: Full report JSON from /analyze endpoint response
        conversation_history_json: Optional JSON string with previous messages
            Format: [{"role": "user"|"assistant", "content": "message"}, ...]
        current_user: Authenticated user
        
    Returns:
        Chat response with answer, sources, and confidence
        
    Example:
        POST /chat
        question="What are the main quality issues?"
        report_json='{...full report JSON...}'
        conversation_history_json='[]'
    """
    
    start_time = time.time()
    
    print(f"Chat requested by user: {current_user.id} ({current_user.email})")
    
    try:
        # Validate inputs
        if not question or not question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty"
            )
        
        if not report_json:
            raise HTTPException(
                status_code=400,
                detail="Report JSON is required"
            )
        
        # Parse report JSON
        try:
            report = json.loads(report_json)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid report JSON: {str(e)}"
            )
        
        # Parse conversation history if provided
        conversation_history = []
        if conversation_history_json:
            try:
                conversation_history = json.loads(conversation_history_json)
                # Validate history format
                for msg in conversation_history:
                    if "role" not in msg or "content" not in msg:
                        raise ValueError("Each message must have 'role' and 'content'")
                    if msg["role"] not in ["user", "assistant", "system"]:
                        raise ValueError("Role must be 'user', 'assistant', or 'system'")
            except (json.JSONDecodeError, ValueError) as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid conversation history: {str(e)}"
                )
        
        # Initialize chat agent
        chat_agent = ChatAgent()
        
        # Get answer
        result = chat_agent.answer_question(
            question=question,
            report=report,
            conversation_history=conversation_history
        )
        
        # Return response
        return {
            "chat_id": str(uuid.uuid4()),
            "question": question,
            "status": result.get("status"),
            "answer": result.get("answer"),
            "sources": result.get("sources", []),
            "confidence_score": result.get("confidence", 0),
            "model_used": result.get("model_used"),
            "execution_time_ms": result.get("execution_time_ms", int((time.time() - start_time) * 1000)),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": result.get("error") if result.get("status") == "error" else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat processing failed: {str(e)}"
        )




