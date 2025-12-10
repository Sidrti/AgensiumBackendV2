
import io
import json
import pandas as pd
from typing import Dict, List, Any, Optional
from fastapi import UploadFile, HTTPException

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
