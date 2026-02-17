
import io
import json
import os
import sys
import base64
from pathlib import Path
import pandas as pd
from typing import Dict, List, Any, Optional, Union
from fastapi import UploadFile, HTTPException


# =============================================================================
# TRANSFORMER MAPPING
# =============================================================================

def get_transformer(tool_id: str):
    """
    Get the appropriate transformer function for a tool_id (v2.1 API).
    
    Lazy imports to avoid circular dependencies and improve startup time.
    Uses the same import pattern as routes.py which works correctly.
    
    CRITICAL: Ensures backend directory is in sys.path before importing transformers.
    This is needed in worker subprocess where path modifications from startup may not persist.
    
    Args:
        tool_id: The tool identifier (profile-my-data, clean-my-data, master-my-data, analyze-my-data, etc.)
        
    Returns:
        Async transformer function (v2.1 API)
        
    Raises:
        ValueError: If tool_id is unknown
    """
    # CRITICAL: Ensure backend directory is in sys.path
    # This is needed in the worker subprocess which may not have inherited the path modifications
    backend_dir = str(Path(__file__).resolve().parent.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    
    # Import the module first (same pattern as routes.py), then get the function
    if tool_id == "profile-my-data":
        from transformers import profile_my_data_transformer
        return profile_my_data_transformer.run_profile_my_data_analysis_v2_1
    
    elif tool_id == "clean-my-data":
        from transformers import clean_my_data_transformer
        return clean_my_data_transformer.run_clean_my_data_analysis_v2_1
    
    elif tool_id == "master-my-data":
        from transformers import master_my_data_transformer
        return master_my_data_transformer.run_master_my_data_analysis_v2_1

    elif tool_id == "analyze-my-data" or tool_id == "customer-segmentation" or tool_id == "experimental-design" or tool_id == "market-basket-sequence" or tool_id == "synthetic-control" or tool_id == "control-group-holdout-planner":
        from transformers import analyze_my_data_transformer
        return analyze_my_data_transformer.run_analyze_my_data_analysis_v2_1
    
    else:
        raise ValueError(f"Unknown tool_id: {tool_id}")


def get_transformer_legacy(tool_id: str):
    """
    Get the appropriate transformer function for a tool_id (legacy API).
    
    Lazy imports to avoid circular dependencies and improve startup time.
    This version is for the legacy /analyze endpoint.
    
    Args:
        tool_id: The tool identifier (profile-my-data, clean-my-data, master-my-data, analyze-my-data, etc.)
        
    Returns:
        Async transformer function (legacy API)
        
    Raises:
        ValueError: If tool_id is unknown
    """
    # Import the module first, then get the function
    if tool_id == "profile-my-data":
        from transformers import profile_my_data_transformer
        return profile_my_data_transformer.run_profile_my_data_analysis
    
    elif tool_id == "clean-my-data":
        from transformers import clean_my_data_transformer
        return clean_my_data_transformer.run_clean_my_data_analysis
    
    elif tool_id == "master-my-data":
        from transformers import master_my_data_transformer
        return master_my_data_transformer.run_master_my_data_analysis

    elif tool_id == "analyze-my-data" or tool_id == "customer-segmentation" or tool_id == "experimental-design" or tool_id == "market-basket-sequence" or tool_id == "synthetic-control" or tool_id == "control-group-holdout-planner":
        from transformers import analyze_my_data_transformer
        return analyze_my_data_transformer.run_analyze_my_data_analysis
    
    else:
        raise ValueError(f"Unknown tool_id: {tool_id}")


# =============================================================================
# FILE UTILITIES
# =============================================================================


def get_required_files(tool_id: str, agents: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Get required files for a tool and agents.
    
    Returns mapping of file_key -> file_definition
    """
    try:
        from main import TOOL_DEFINITIONS
    except ImportError:
        return {}
    
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


def determine_file_key(filename: str) -> str:
    """Determine file key from filename."""
    lower = filename.lower()
    if 'baseline' in lower:
        return 'baseline'
    return 'primary'


async def upload_outputs_to_s3(
    task: Any,  # models.Task
    downloads: List[Dict]
) -> int:
    """
    Upload download files to S3.
    
    Args:
        task: Task model
        downloads: List of download dicts with content_base64 and file_name
        
    Returns:
        Number of files uploaded
    """
    from services.s3_service import s3_service
    
    uploaded_count = 0
    
    for download in downloads:
        content_b64 = download.get("content_base64")
        filename = download.get("file_name")
        
        if not content_b64 or not filename:
            continue
        
        try:
            # Decode content
            content = base64.b64decode(content_b64)
            
            # Determine content type
            if filename.endswith('.xlsx'):
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif filename.endswith('.json'):
                content_type = "application/json"
            else:
                content_type = "text/csv"
            
            # Build S3 key
            key = f"{task.get_output_prefix()}{filename}"
            
            # Upload
            s3_service.upload_file(key, content, content_type)
            uploaded_count += 1
            print(f"[V2.1] Uploaded output: {filename} ({len(content)} bytes)")
            
        except Exception as e:
            print(f"[V2.1] Error uploading {filename}: {str(e)}")
    
    return uploaded_count


def build_agent_input(
    agent_id: str,
    files_map: Dict[str, tuple],
    parameters: Dict[str, Any],
    tool_def: Dict[str, Any]
) -> Dict[str, Any]:
    """Build agent-specific input based on tool definition."""
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
    """Update files map with cleaned file from agent result."""
    agent_id = result.get("agent_id", "unknown_agent")
    
    if result.get("status") == "success" and "cleaned_file" in result:
        cleaned_file = result["cleaned_file"]
        if cleaned_file and "content" in cleaned_file:
            try:
                # Decode base64 content
                new_content = base64.b64decode(cleaned_file["content"])
                new_filename = cleaned_file.get("filename", "cleaned_data.csv")
                
                # Update primary file for next agent
                files_map["primary"] = (new_content, new_filename)
                print(f"[{agent_id}] Successfully updated primary file: {new_filename}. New size: {len(new_content)} bytes")
            except Exception as e:
                print(f"[{agent_id}] Error updating file from result: {str(e)}")
                pass
    else:
        print(f"[{agent_id}] No cleaned file produced. Continuing with previous file.")


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


async def read_uploaded_files(
    uploaded_files: Dict[str, Optional[UploadFile]]
) -> Dict[str, tuple]:
    """
    Read uploaded files into memory.
    
    Args:
        uploaded_files: Dictionary of file_key -> UploadFile
        
    Returns:
        Dictionary of file_key -> (bytes, filename)
    """
    files_map = {}
    
    for file_key, file_obj in uploaded_files.items():
        if file_obj:
            file_contents = await file_obj.read()
            files_map[file_key] = (file_contents, file_obj.filename)
    
    return files_map


def convert_files_to_csv(
    files_map: Dict[str, tuple]
) -> Dict[str, tuple]:
    """
    Convert uploaded files to CSV format.
    Handles Excel (.xlsx, .xls) and JSON files with fallback strategies.
    
    Args:
        files_map: Dictionary of file_key -> (content, filename)
        
    Returns:
        Updated files_map with CSV content
        
    Raises:
        HTTPException: If conversion fails
    """
    for file_key, (content, filename) in list(files_map.items()):
        try:
            file_ext = filename.split(".")[-1].lower() if "." in filename else ""
            
            # Skip if already CSV
            if file_ext == "csv":
                continue
                
            df = None
            
            # Handle Excel files
            if file_ext in ["xlsx", "xls"]:
                try:
                    engine = "openpyxl" if file_ext == "xlsx" else "xlrd"
                    df = pd.read_excel(io.BytesIO(content), engine=engine)
                except Exception as first_error:
                    print(f"Primary engine {engine} failed for {filename}: {first_error}")
                    success = False
                    
                    # Strategy 1: Try the other Excel engine
                    if not success:
                        try:
                            fallback_engine = "xlrd" if engine == "openpyxl" else "openpyxl"
                            df = pd.read_excel(io.BytesIO(content), engine=fallback_engine)
                            success = True
                            print(f"Fallback to {fallback_engine} successful")
                        except Exception:
                            pass
                    
                    # Strategy 2: Try reading as CSV (files might be misnamed)
                    if not success:
                        try:
                            df = pd.read_csv(io.BytesIO(content))
                            success = True
                            print(f"Fallback to CSV reader successful")
                        except Exception:
                            pass
                    
                    if not success:
                        raise first_error
            
            # Handle JSON files
            elif file_ext == "json":
                df = pd.read_json(io.BytesIO(content))
            
            # If conversion was successful, update the file in memory
            if df is not None:
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                new_content = csv_buffer.getvalue().encode('utf-8')
                
                # Update filename
                base_name = ".".join(filename.split(".")[:-1]) if "." in filename else filename
                new_filename = f"{base_name}.csv"
                
                # Update map
                files_map[file_key] = (new_content, new_filename)
                
        except Exception as e:
            print(f"Error: Failed to convert {filename} to CSV: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to convert {filename} to CSV: {str(e)}")
    
    return files_map