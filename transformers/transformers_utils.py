
import io
import json
import os
import base64
from pathlib import Path
import pandas as pd
from typing import Dict, List, Any, Optional, Union
from fastapi import UploadFile, HTTPException


# ----------------------------
# Analysis storage helpers
# ----------------------------

def _uploads_root() -> Path:
    """Root folder used for persisting inputs/outputs.

    Can be overridden via env var AGENSIUM_UPLOADS_DIR.
    """
    root = os.getenv("AGENSIUM_UPLOADS_DIR", "uploads")
    return Path(root)


def _safe_filename(filename: Optional[str], fallback: str = "file") -> str:
    """Prevent path traversal and normalize empty names."""
    if not filename:
        return fallback
    name = Path(filename).name
    return name if name else fallback


def get_analysis_dirs(
    user_id: Union[str, int],
    analysis_id: str,
    root_dir: Optional[Union[str, Path]] = None
) -> Dict[str, Path]:
    """Create (if needed) and return analysis directory paths.

    Layout:
      uploads/<user_id>/<analysis_id>/inputs
      uploads/<user_id>/<analysis_id>/outputs
    """
    root = Path(root_dir) if root_dir is not None else _uploads_root()
    analysis_dir = root / str(user_id) / str(analysis_id)
    inputs_dir = analysis_dir / "inputs"
    outputs_dir = analysis_dir / "outputs"

    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    return {
        "root": root,
        "analysis_dir": analysis_dir,
        "inputs": inputs_dir,
        "outputs": outputs_dir,
    }


async def save_upload_file(
    upload_file: UploadFile,
    dest_path: Union[str, Path],
    *,
    chunk_size: int = 1024 * 1024,
    reset_pointer: bool = True
) -> int:
    """Persist an UploadFile to disk efficiently and (optionally) reset its pointer.

    Returns number of bytes written.
    """
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Ensure we copy from the start.
    try:
        await upload_file.seek(0)
    except Exception:
        # Some implementations might not support seek; ignore.
        pass

    bytes_written = 0
    with open(dest, "wb") as f:
        while True:
            chunk = await upload_file.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            bytes_written += len(chunk)

    if reset_pointer:
        try:
            await upload_file.seek(0)
        except Exception:
            pass

    return bytes_written


async def persist_analysis_inputs(
    *,
    user_id: Union[str, int],
    analysis_id: str,
    primary: Optional[UploadFile] = None,
    baseline: Optional[UploadFile] = None,
    parameters_json: Optional[str] = None,
    root_dir: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """Store incoming request inputs under uploads/<user_id>/<analysis_id>/inputs."""
    dirs = get_analysis_dirs(user_id=user_id, analysis_id=analysis_id, root_dir=root_dir)
    inputs_dir = dirs["inputs"]

    result: Dict[str, Any] = {
        "inputs_dir": str(inputs_dir),
        "primary_path": None,
        "baseline_path": None,
        "parameters_path": None,
        "primary_size": 0,
        "baseline_size": 0,
    }

    if primary:
        primary_name = _safe_filename(primary.filename, "primary")
        primary_path = inputs_dir / primary_name
        result["primary_size"] = await save_upload_file(primary, primary_path)
        result["primary_path"] = str(primary_path)

    if baseline:
        baseline_name = _safe_filename(baseline.filename, "baseline")
        baseline_path = inputs_dir / baseline_name
        result["baseline_size"] = await save_upload_file(baseline, baseline_path)
        result["baseline_path"] = str(baseline_path)

    if parameters_json is not None:
        params_path = inputs_dir / "parameters.json"
        with open(params_path, "w", encoding="utf-8") as f:
            f.write(parameters_json)
        result["parameters_path"] = str(params_path)

    return result


def persist_downloads_to_outputs(
    *,
    downloads: Any,
    user_id: Union[str, int],
    analysis_id: str,
    root_dir: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """Persist download artifacts (base64 payloads) under outputs folder.

    Expects downloads to be a list of dicts with keys: file_name, content_base64.
    Writes a manifest.json describing what was saved.
    """
    dirs = get_analysis_dirs(user_id=user_id, analysis_id=analysis_id, root_dir=root_dir)
    outputs_dir = dirs["outputs"]

    saved: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    if not isinstance(downloads, list):
        return {
            "outputs_dir": str(outputs_dir),
            "saved": saved,
            "errors": [{"error": "downloads is not a list"}],
        }

    for idx, item in enumerate(downloads):
        if not isinstance(item, dict):
            errors.append({"index": idx, "error": "download item is not a dict"})
            continue

        content_b64 = item.get("content_base64")
        file_name = item.get("file_name") or item.get("filename") or item.get("name")

        # Some error entries won't have file payloads.
        if not content_b64 or not file_name:
            errors.append({
                "index": idx,
                "download_id": item.get("download_id"),
                "error": "missing file_name/content_base64",
            })
            continue

        try:
            raw = base64.b64decode(content_b64)
            safe_name = _safe_filename(str(file_name), f"download_{idx}")

            # Avoid overwriting if duplicates
            dest = outputs_dir / safe_name
            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                dest = outputs_dir / f"{stem}_{idx}{suffix}"

            with open(dest, "wb") as f:
                f.write(raw)

            saved.append({
                "index": idx,
                "download_id": item.get("download_id"),
                "file_name": safe_name,
                "path": str(dest),
                "size_bytes": len(raw),
                "mimeType": item.get("mimeType"),
                "type": item.get("type"),
            })
        except Exception as e:
            errors.append({
                "index": idx,
                "download_id": item.get("download_id"),
                "error": f"failed to persist download: {str(e)}",
            })

    manifest = {
        "analysis_id": analysis_id,
        "outputs_dir": str(outputs_dir),
        "saved_count": len(saved),
        "error_count": len(errors),
        "saved": saved,
        "errors": errors,
    }

    try:
        with open(outputs_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    except Exception:
        # Don't fail if manifest write fails.
        pass

    return manifest



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
