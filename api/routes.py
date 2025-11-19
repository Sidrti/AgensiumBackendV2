"""
API Routes and Endpoints

All API endpoints for tool management and data analysis.
Supports flexible file handling based on tool definitions.
"""

import json
import uuid
import time
import base64
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, File, UploadFile, Form

from agents import readiness_rater, unified_profiler, drift_detector, score_risk, governance_checker, test_coverage_agent, null_handler, outlier_remover, type_fixer, duplicate_resolver, quarantine_agent, cleanse_writeback, field_standardization, cleanse_previewer
from transformers import profile_my_data_transformer, clean_my_data_transformer
from ai import ChatAgent
from .dependencies import decode_base64_file

# Create router for API routes
router = APIRouter()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_tool_definitions() -> Dict[str, Any]:
    """Get cached tool definitions from main module."""
    try:
        from main import TOOL_DEFINITIONS
        return TOOL_DEFINITIONS
    except ImportError:
        return {}


def get_required_files(tool_id: str, agents: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Get required files for a tool and agents.
    
    Returns mapping of file_key -> file_definition
    """
    from main import TOOL_DEFINITIONS
    
    if tool_id not in TOOL_DEFINITIONS:
        return {}
    
    tool_def = TOOL_DEFINITIONS[tool_id]
    tool_files = tool_def.get("tool", {}).get("files", {})
    required_files = {}
    
    # Start with tool-level files
    for file_key, file_def in tool_files.items():
        required_files[file_key] = file_def
    
    # Check agent-level requirements
    agents_def = tool_def.get("agents", {})
    for agent_id in agents:
        if agent_id in agents_def:
            agent_required = agents_def[agent_id].get("required_files", [])
            for file_key in agent_required:
                if file_key in tool_files:
                    required_files[file_key] = tool_files[file_key]
    
    return required_files


def validate_files(
    uploaded_files: Dict[str, Optional[UploadFile]],
    required_files: Dict[str, Dict[str, Any]]
) -> Dict[str, str]:
    """
    Validate uploaded files against tool requirements.
    
    Returns:
        Dictionary of errors (if any)
    """
    errors = {}
    
    for file_key, file_def in required_files.items():
        is_required = file_def.get("required", False)
        
        # Check if required file is provided
        if is_required and file_key not in uploaded_files:
            errors[file_key] = f"Required file '{file_key}' not provided"
        elif is_required and uploaded_files.get(file_key) is None:
            errors[file_key] = f"Required file '{file_key}' is empty"
        
        # Check file format if provided
        if file_key in uploaded_files and uploaded_files[file_key]:
            file_obj = uploaded_files[file_key]
            allowed_formats = file_def.get("formats", [])
            
            if allowed_formats and file_obj.filename:
                file_ext = file_obj.filename.split(".")[-1].lower()
                if file_ext not in allowed_formats:
                    errors[file_key] = f"File format '.{file_ext}' not allowed. Allowed: {', '.join(allowed_formats)}"
    
    return errors


def build_agent_input(
    agent_id: str,
    files_map: Dict[str, tuple],  # file_key -> (bytes, filename)
    parameters: Dict[str, Any],
    tool_def: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build agent-specific input based on tool definition.
    
    Args:
        agent_id: Agent identifier
        files_map: Map of file_key -> (content, filename)
        parameters: Agent parameters
        tool_def: Tool definition
        
    Returns:
        Dictionary with agent-specific inputs
    """
    agent_def = tool_def.get("agents", {}).get(agent_id, {})
    required_files = agent_def.get("required_files", [])
    
    # Build files dictionary for agent
    agent_files = {}
    for file_key in required_files:
        if file_key in files_map:
            agent_files[file_key] = files_map[file_key]
    
    # Get agent parameters
    agent_params = parameters.get(agent_id, {})
    
    return {
        "agent_id": agent_id,
        "files": agent_files,
        "parameters": agent_params
    }


def update_files_from_result(
    files_map: Dict[str, tuple],
    result: Dict[str, Any]
) -> None:
    """
    Update files map with cleaned file from agent result.
    Modifies files_map in place to chain agent outputs.
    
    Args:
        files_map: Current files map (file_key -> (bytes, filename))
        result: Result from previous agent execution
    """
    agent_id = result.get("agent_id", "unknown_agent")
    
    if result.get("status") == "success" and "cleaned_file" in result:
        cleaned_file = result["cleaned_file"]
        if cleaned_file and "content" in cleaned_file:
            try:
                # Decode base64 content
                new_content = base64.b64decode(cleaned_file["content"])
                new_filename = cleaned_file.get("filename", "cleaned_data.csv")
                
                # Update primary file for next agent
                # This enables the chaining of data cleaning operations
                files_map["primary"] = (new_content, new_filename)
                print(f"[{agent_id}] Successfully updated primary file: {new_filename}. New size: {len(new_content)} bytes")
            except Exception as e:
                # If decoding fails, we keep the previous file
                # This prevents the chain from breaking completely on a bad output
                print(f"[{agent_id}] Error updating file from result: {str(e)}")
                pass
    else:
        print(f"[{agent_id}] No cleaned file produced. Continuing with previous file.")


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
):
    """
    Analyze data using specified tool and agents.
    
    Args:
        tool_id: Tool identifier (e.g., "profile-my-data")
        agents: Comma-separated agent IDs (optional, uses tool defaults)
        parameters_json: JSON string with agent-specific parameters
        primary: Primary data file (required for most tools)
        baseline: Optional baseline/reference file (for drift detection and comparisons)
        
    Returns:
        Unified analysis response with analysis_id, status, and results
    """
    from main import TOOL_DEFINITIONS
    
    analysis_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Validate tool
        if tool_id not in TOOL_DEFINITIONS:
            raise HTTPException(status_code=400, detail=f"Tool '{tool_id}' not found")
        
        tool_def = TOOL_DEFINITIONS[tool_id]
        
        # Determine which agents to run
        agents_to_run = tool_def["tool"]["available_agents"]
        
        if agents:
            agents_to_run = [a.strip() for a in agents.split(",")]
        
        # Get required files for tool and agents
        required_files = get_required_files(tool_id, agents_to_run)
        
        # Build uploaded files dictionary from explicit parameters
        uploaded_files = {
            "primary": primary,
            "baseline": baseline
        }
        # Remove None values
        uploaded_files = {k: v for k, v in uploaded_files.items() if v is not None}
        
        # Validate files against requirements
        validation_errors = validate_files(uploaded_files, required_files)
        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail=f"File validation failed: {validation_errors}"
            )
        
        # Read all uploaded files into memory
        files_map = {}  # file_key -> (bytes, filename)
        
        for file_key, file_obj in uploaded_files.items():
            if file_obj:
                file_contents = await file_obj.read()
                files_map[file_key] = (file_contents, file_obj.filename)
        
        # Parse parameters
        parameters = {}
        if parameters_json:
            try:
                parameters = json.loads(parameters_json)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid parameters JSON")
        
        # Execute agents
        agent_results = {}
        
        for agent_id in agents_to_run:
            try:
                # Build agent-specific input
                agent_input = build_agent_input(agent_id, files_map, parameters, tool_def)
                
                # Execute agent with flexible file handling
                result = execute_agent_flexible(
                    agent_id,
                    agent_input
                )
                
                agent_results[agent_id] = result
                
                # Update files map for next agent (only for clean-my-data)
                if tool_id == "clean-my-data":
                    update_files_from_result(files_map, result)
            except Exception as e:
                agent_results[agent_id] = {
                    "status": "error",
                    "error": str(e),
                    "execution_time_ms": 0
                }
        
        # Transform results based on tool
        if tool_id == "profile-my-data":
            final_response = profile_my_data_transformer.transform_profile_my_data_response(
                agent_results,
                int((time.time() - start_time) * 1000),
                analysis_id
            )
        elif tool_id == "clean-my-data":
            final_response = clean_my_data_transformer.transform_clean_my_data_response(
                agent_results,
                int((time.time() - start_time) * 1000),
                analysis_id
            )
        else:
            # Default transformer (just return raw results)
            final_response = {
                "analysis_id": analysis_id,
                "tool": tool_id,
                "status": "success",
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "agent_results": agent_results
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


def execute_agent_flexible(
    agent_id: str,
    agent_input: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute agent with flexible file handling.
    
    Args:
        agent_id: Agent identifier
        agent_input: Dictionary with 'files' and 'parameters'
        
    Returns:
        Agent output
    """
    files_map = agent_input.get("files", {})
    parameters = agent_input.get("parameters", {})
    
    # Map file keys to function arguments
    if agent_id == "drift-detector":
        if "primary" not in files_map or "baseline" not in files_map:
            return {
                "status": "error",
                "error": "Drift detector requires 'primary' and 'baseline' files",
                "execution_time_ms": 0
            }
        
        baseline_bytes, baseline_filename = files_map["baseline"]
        primary_bytes, primary_filename = files_map["primary"]
        
        return drift_detector.detect_drift(
            baseline_bytes,
            baseline_filename,
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "readiness-rater":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Readiness rater requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return readiness_rater.rate_readiness(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "unified-profiler":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Unified profiler requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return unified_profiler.profile_data(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "score-risk":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Risk scorer requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return score_risk.score_risk(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "governance-checker":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Governance checker requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return governance_checker.execute_governance(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "test-coverage-agent":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Test coverage agent requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return test_coverage_agent.execute_test_coverage(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "quarantine-agent":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Quarantine agent requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return quarantine_agent.execute_quarantine_agent(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "null-handler":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Null handler requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return null_handler.execute_null_handler(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "outlier-remover":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Outlier remover requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return outlier_remover.execute_outlier_remover(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "type-fixer":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Type fixer requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return type_fixer.execute_type_fixer(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "duplicate-resolver":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Duplicate resolver requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return duplicate_resolver.execute_duplicate_resolver(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "field-standardization":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Field standardization requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return field_standardization.execute_field_standardization(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "cleanse-writeback":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Cleanse writeback requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return cleanse_writeback.execute_cleanse_writeback(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "cleanse-previewer":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Cleanse previewer requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return cleanse_previewer.execute_cleanse_previewer(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    else:
        return {
            "status": "error",
            "error": f"Unknown agent: {agent_id}",
            "execution_time_ms": 0
        }


# ============================================================================
# CHAT ENDPOINT
# ============================================================================

@router.post("/chat")
async def chat(
    question: str = Form(...),
    report_json: str = Form(...),
    conversation_history_json: Optional[str] = Form(None),
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
        
    Returns:
        Chat response with answer, sources, and confidence
        
    Example:
        POST /chat
        question="What are the main quality issues?"
        report_json='{...full report JSON...}'
        conversation_history_json='[]'
    """
    
    start_time = time.time()
    
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




