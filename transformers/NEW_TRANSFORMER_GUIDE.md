# Agensium Transformer Development Guide

This document outlines the standard pattern and architecture for creating new **Transformers** in the Agensium backend. Transformers act as the orchestration layer for Tools, managing file I/O, billing, agent execution loops, and result aggregation.

## 1. File Structure & Naming

-   **File Name:** Snake_case ending in `_transformer.py` (e.g., `analyze_my_data_transformer.py`).
-   **Location:** `backend/transformers/` directory.
-   **Registration:** Must be exported in `transformers/__init__.py`.

## 2. Core Responsibilities

Each transformer must implement two primary entry points to support both synchronous (API) and asynchronous (Celery/S3) workflows:

1.  **V1 Entry Point (`run_{tool}_analysis`):** Handles direct HTTP uploads (FastAPI `UploadFile`).
2.  **V2.1 Entry Point (`run_{tool}_analysis_v2_1`):** Handles background tasks using S3/Backblaze B2 storage and database `Task` models.

## 3. Standard Code Template

### Imports

Standard imports required for all transformers:

```python
import time
import json
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from datetime import datetime
from fastapi import UploadFile, HTTPException

# Agent Imports
from agents import my_new_agent, another_agent 

# AI & Download Handlers
from ai.analysis_summary_ai import AnalysisSummaryAI
from downloads.my_tool_downloads import MyToolDownloads

# Shared Utilities (CRITICAL)
from transformers.transformers_utils import (
    get_required_files,
    validate_files,
    read_uploaded_files,
    convert_files_to_csv,
    determine_file_key,
    upload_outputs_to_s3,
    build_agent_input,
    update_files_from_result # Only if agent chaining is needed
)

# Services & Billing
from billing import BillingContext, InsufficientCreditsError, UserWalletNotFoundError, AgentCostNotFoundError
from services.s3_service import s3_service

if TYPE_CHECKING:
    from db import models
```

### 1. V1 Entry Point (HTTP/Synchronous)

Handles immediate analysis requests from the API.

```python
async def run_my_tool_analysis(
    tool_id: str,
    agents: Optional[str],
    parameters_json: Optional[str],
    primary: Optional[UploadFile],
    baseline: Optional[UploadFile],
    analysis_id: str,
    current_user: Any = None
) -> Dict[str, Any]:
    start_time = time.time()
    
    try:
        from main import TOOL_DEFINITIONS
        
        # 1. Validation & Setup
        if tool_id not in TOOL_DEFINITIONS:
            raise HTTPException(status_code=400, detail=f"Tool '{tool_id}' not found")
        tool_def = TOOL_DEFINITIONS[tool_id]
        
        agents_to_run = tool_def["tool"]["available_agents"]
        if agents:
            agents_to_run = [a.strip() for a in agents.split(",")]
            
        required_files = get_required_files(tool_id, agents_to_run)
        
        # 2. File Handling
        uploaded_files = { "primary": primary, "baseline": baseline }
        uploaded_files = {k: v for k, v in uploaded_files.items() if v is not None}
        
        if errors := validate_files(uploaded_files, required_files):
            raise HTTPException(status_code=400, detail=f"File validation failed: {errors}")
            
        files_map = await read_uploaded_files(uploaded_files)
        files_map = convert_files_to_csv(files_map)
        
        # 3. Parameter Parsing
        parameters = {}
        if parameters_json:
            try:
                parameters = json.loads(parameters_json)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid parameters JSON")
        
        # 4. Upfront Billing
        with BillingContext(current_user) as billing:
            try:
                billing.validate_and_consume_all(agents=agents_to_run, tool_id=tool_id, task_id=analysis_id)
            except (InsufficientCreditsError, UserWalletNotFoundError, AgentCostNotFoundError) as e:
                return billing.get_billing_error_response(error=e, task_id=analysis_id, tool_id=tool_id, start_time=start_time)
        
        # 5. Agent Execution Loop
        agent_results = {}
        for agent_id in agents_to_run:
            try:
                agent_input = build_agent_input(agent_id, files_map, parameters, tool_def)
                result = _execute_agent(agent_id, agent_input)
                agent_results[agent_id] = result
                
                # Optional: Chaining (pass output of one agent as input to next)
                # update_files_from_result(files_map, result)
                
            except Exception as e:
                agent_results[agent_id] = {"status": "error", "error": str(e), "execution_time_ms": 0}
        
        # 6. Response Transformation
        return transform_my_tool_response(agent_results, int((time.time() - start_time) * 1000), analysis_id, current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        return {"analysis_id": analysis_id, "status": "error", "error": str(e), "execution_time_ms": int((time.time() - start_time) * 1000)}
```

### 2. V2.1 Entry Point (S3/Asynchronous)

Handles background tasks triggered via Celery.

```python
async def run_my_tool_analysis_v2_1(
    task: "models.Task",
    current_user: Any,
    db: Any
) -> Dict[str, Any]:
    from main import TOOL_DEFINITIONS
    start_time = time.time()
    
    try:
        tool_def = TOOL_DEFINITIONS[task.tool_id]
        
        # 1. S3 File Loading
        input_files = s3_service.list_input_files(task.user_id, task.task_id)
        if not input_files:
            return {"status": "error", "error": "No input files found in S3", "error_code": "NO_INPUT_FILES"}
            
        files_map = {}
        for file_info in input_files:
            file_key = determine_file_key(file_info['filename']) # Helper in utils
            content = s3_service.get_file_bytes(file_info['key'])
            files_map[file_key] = (content, file_info['filename'])
            
        files_map = convert_files_to_csv(files_map)
        parameters = s3_service.get_parameters(task.user_id, task.task_id) or {}
        
        # 2. Upfront Billing
        with BillingContext(current_user) as billing:
            try:
                billing.validate_and_consume_all(agents=task.agents, tool_id=task.tool_id, task_id=task.task_id)
            except Exception as e:
                return billing.get_billing_error_response(error=e, task_id=task.task_id, tool_id=task.tool_id, start_time=start_time)
        
        # 3. Execution Loop with Progress Updates
        agent_results = {}
        completed = 0
        for agent_id in task.agents:
            try:
                # Update DB Progress
                task.current_agent = agent_id
                task.progress = 15 + int((completed / len(task.agents)) * 80)
                db.commit()
                
                agent_input = build_agent_input(agent_id, files_map, parameters, tool_def)
                result = _execute_agent(agent_id, agent_input)
                agent_results[agent_id] = result
                
                # Optional: Chaining
                # update_files_from_result(files_map, result)
                
                completed += 1
            except Exception as e:
                agent_results[agent_id] = {"status": "error", "error": str(e), "execution_time_ms": 0}
        
        # 4. Transformation & S3 Upload
        final_result = transform_my_tool_response(agent_results, int((time.time() - start_time) * 1000), task.task_id, current_user)
        
        await upload_outputs_to_s3(task=task, downloads=final_result.get("report", {}).get("downloads", []))
        
        return {"status": "success"}
        
    except Exception as e:
        return {"status": "error", "error": str(e), "error_code": "PROCESSING_ERROR"}
```

### 3. Execution Dispatcher (`_execute_agent`)

Maps agent IDs to their execution functions.

```python
def _execute_agent(agent_id: str, agent_input: Dict[str, Any]) -> Dict[str, Any]:
    files = agent_input.get("files", {})
    params = agent_input.get("parameters", {})
    
    if agent_id == "my-agent-id":
        if "primary" not in files:
            return {"status": "error", "error": "Agent requires 'primary' file", "execution_time_ms": 0}
        
        content, filename = files["primary"]
        return my_new_agent.execute_my_new_agent(content, filename, params)
        
    # ... other agents ...
    
    else:
        return {"status": "error", "error": f"Unknown agent: {agent_id}", "execution_time_ms": 0}
```

### 4. Result Aggregator (`transform_..._response`)

Consolidates outputs into the final JSON report.

```python
def transform_my_tool_response(
    agent_results: Dict[str, Any],
    execution_time_ms: int,
    analysis_id: str,
    current_user: Any = None
) -> Dict[str, Any]:
    
    # 1. Aggregate Lists
    all_alerts = []
    all_issues = []
    all_recommendations = []
    # ... aggregate from agent_results ...
    
    # 2. Build Executive Summary
    executive_summary = []
    # Add standard cards (Time, Agents Used)
    # Add agent-specific cards
    
    # 3. Generate AI Analysis
    # Combine agent AI texts and call AnalysisSummaryAI
    
    # 4. Generate Downloads
    # Use tool-specific Downloads class
    
    # 5. Return Final Structure
    return {
        "analysis_id": analysis_id,
        "tool": "my-tool-id",
        "status": "success",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "execution_time_ms": execution_time_ms,
        "report": {
            "alerts": all_alerts,
            "issues": all_issues,
            "recommendations": all_recommendations,
            "executiveSummary": executive_summary,
            "analysisSummary": analysis_summary,
            "downloads": downloads,
            **agent_results # Include raw outputs
        }
    }
```

## 4. Key Utilities (`transformers_utils.py`)

Always use these shared functions instead of rewriting logic:

*   **`get_required_files(tool_id, agents)`**: Resolves file requirements from `main.py`.
*   **`validate_files(uploaded, required)`**: Checks for missing files or invalid formats.
*   **`read_uploaded_files(uploaded)`**: Async reading of FastAPI UploadFiles.
*   **`convert_files_to_csv(files_map)`**: Auto-converts Excel/JSON to CSV.
*   **`build_agent_input(id, files_map, params, tool_def)`**: Prepares standardized input dict.
*   **`determine_file_key(filename)`**: Maps filenames to 'primary'/'baseline'.
*   **`upload_outputs_to_s3(task, downloads)`**: Handles S3 uploads for V2.1 workflow.
*   **`update_files_from_result(files_map, result)`**: Updates the in-memory file map if an agent produced a `cleaned_file` (used for Chaining).

## 5. Best Practices

1.  **Agent Chaining:** If your tool modifies data (like Clean or Master), call `update_files_from_result` after each agent execution in the loop. If it's read-only (like Profile or Analyze), do not call it.
2.  **Error Handling:** Never let an agent failure crash the entire transformer. Catch exceptions inside the loop and return an error status for that specific agent.
3.  **Billing:** Always use the `BillingContext` context manager. It handles credit validation, consumption, and error reporting automatically.
4.  **S3 Integration:** Never assume local file paths. Always work with byte streams (`bytes`) loaded into memory.
