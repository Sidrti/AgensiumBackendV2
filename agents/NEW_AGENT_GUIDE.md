# Agensium Agent Development Guide

This document outlines the standard pattern and architecture for creating new agents in the Agensium backend. All agents must follow this structure to ensure consistency, scalability, and seamless integration with the API and frontend.

## 1. File Structure & Naming

-   **File Name:** Snake_case (e.g., `my_new_agent.py`).
-   **Location:** `backend/agents/` directory.
-   **Imports:** Standard imports should include `polars`, `numpy`, `io`, `time`, and `typing`.

## 2. Main Entry Point

Every agent must expose a single main execution function named `execute_{agent_name}`.

### Signature

```python
def execute_my_agent_name(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
```

### Arguments

-   `file_contents` (**bytes**): The raw binary content of the file to be processed.
-   `filename` (**str**): The original name of the file (used for validation, e.g., checking `.csv` extension).
-   `parameters` (**Optional[Dict[str, Any]]**): Configuration parameters passed from the frontend/API (typically defined in `tools/my_agent_tool.json`).

## 3. Standard Return Structure

The return dictionary **MUST** contain the following keys:

| Key | Type | Description |
| :--- | :--- | :--- |
| `status` | `str` | `"success"` or `"error"`. |
| `agent_id` | `str` | Kebab-case ID (e.g., `"my-new-agent"`). |
| `agent_name` | `str` | Human-readable name (e.g., `"My New Agent"`). |
| `execution_time_ms` | `int` | Execution time in milliseconds. |
| `summary_metrics` | `Dict` | High-level counters (e.g., `total_rows_processed`, `issues_found`). |
| `data` | `Dict` | The core analysis results specific to the agent. |
| `alerts` | `List[Dict]` | High-priority notifications for the dashboard. |
| `issues` | `List[Dict]` | General system or column-level issues. |
| `row_level_issues` | `List[Dict]` | Specific row/cell issues. **Limit to 1000 items.** |
| `issue_summary` | `Dict` | Aggregated counts of issues by type and severity. |
| `recommendations` | `List[Dict]` | Actionable advice for the user. |
| `executive_summary` | `List[Dict]` | High-level summary cards for the UI. |
| `ai_analysis_text` | `str` | Natural language summary for LLM consumption. |
| `cleaned_file` | `Dict` | **(Optional)** Only for agents that modify data. Contains base64 encoded file. |

## 4. Code Template

```python
"""
Agent Name (Optimized)

Brief description of what the agent does.
Input: Expected input format (e.g., CSV file)
Output: Brief description of output
"""

import polars as pl
import numpy as np
import io
import time
import base64
from typing import Dict, Any, Optional, List

# Utility for JSON serialization of numpy types
def _convert_numpy_types(obj):
    if isinstance(obj, np.integer): return int(obj)
    elif isinstance(obj, np.floating): return float(obj)
    elif isinstance(obj, np.ndarray): return obj.tolist()
    return obj

def execute_my_new_agent(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Docstring explaining the function.
    """
    start_time = time.time()
    parameters = parameters or {}

    # 1. Parse Parameters with Defaults
    # Always provide sensible defaults matching the tool.json definition
    threshold = parameters.get("threshold", 0.5)
    
    try:
        # 2. Input Validation
        if not filename.endswith('.csv'):
             return {
                "status": "error",
                "agent_id": "my-new-agent",
                "error": f"Unsupported file format: {filename}. Only CSV is supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # 3. Data Loading (Polars)
        try:
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True)
            if df.height == 0:
                raise ValueError("File is empty")
        except Exception as e:
            return {
                "status": "error",
                "agent_id": "my-new-agent",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # 4. Core Logic
        # Delegate complex logic to private helper functions (_)
        # For modification agents:
        # df_cleaned, transformation_log = _apply_fixes(df, parameters)
        
        # For analysis agents:
        analysis_result = _perform_analysis(df, threshold)

        # 5. Generate Standard Artifacts
        alerts = _generate_alerts(analysis_result)
        issues = _generate_issues(analysis_result)
        row_level_issues = _generate_row_level_issues(df, analysis_result) # CAP AT 1000!
        recommendations = _generate_recommendations(analysis_result)
        
        # 6. Optional: Generate Cleaned File (For Fixing Agents)
        cleaned_file_payload = None
        # if agent_modifies_data:
        #     output = io.BytesIO()
        #     df_cleaned.write_csv(output)
        #     cleaned_bytes = output.getvalue()
        #     cleaned_file_payload = {
        #         "filename": f"cleaned_{filename}",
        #         "content": base64.b64encode(cleaned_bytes).decode('utf-8'),
        #         "size_bytes": len(cleaned_bytes),
        #         "format": "csv"
        #     }

        # 7. Construct Response
        return {
            "status": "success",
            "agent_id": "my-new-agent",
            "agent_name": "My New Agent",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_processed": df.height,
                "key_metric_1": analysis_result["some_count"],
            },
            "data": analysis_result,
            "alerts": alerts,
            "issues": issues,
            "row_level_issues": row_level_issues[:1000], # Enforce limit
            "issue_summary": {
                "total_issues": len(row_level_issues),
                "by_type": {}, # Populate counts
                "by_severity": {} # Populate counts
            },
            "recommendations": recommendations,
            "executive_summary": [{
                 "summary_id": "exec_summary_1",
                 "title": "Main Insight",
                 "value": "85/100",
                 "status": "good", # excellent, good, warning, critical
                 "description": "Brief textual summary."
            }],
            "ai_analysis_text": "Text block for LLM consumption...",
            "cleaned_file": cleaned_file_payload # Optional
        }

    except Exception as e:
        # Global Error Handler
        return {
            "status": "error",
            "agent_id": "my-new-agent",
            "agent_name": "My New Agent",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }

# Helper functions...
def _perform_analysis(df: pl.DataFrame, threshold: float) -> Dict[str, Any]:
    # ... logic ...
    pass
```

## 5. Artifact Details

### `alerts` (List[Dict])
High-level notifications displayed prominently.
```json
{
    "alert_id": "unique_id",
    "severity": "critical" | "high" | "medium" | "low",
    "category": "category_name",
    "message": "User-facing message",
    "affected_fields_count": 5,
    "recommendation": "Short action item"
}
```

### `issues` (List[Dict])
General issues found during processing.
```json
{
    "issue_id": "unique_id",
    "agent_id": "agent-id",
    "field_name": "field_or_scope",
    "issue_type": "type_code",
    "severity": "high",
    "message": "Description of the issue"
}
```

### `row_level_issues` (List[Dict])
Specific problems tied to a row/column index. Used for highlighting in the UI grid. **Limit this list (e.g., to 1000 items) to prevent performance issues.**
```json
{
    "row_index": 0,
    "column": "column_name",
    "issue_type": "type_code",
    "severity": "warning",
    "message": "Specific error message",
    "value": "The bad value"
}
```

### `issue_summary` (Dict)
Aggregated counts for the frontend dashboard.
```json
{
    "total_issues": 150,
    "by_type": { "null_value": 50, "type_mismatch": 100 },
    "by_severity": { "warning": 140, "critical": 10 },
    "affected_rows": 120,
    "affected_columns": ["col1", "col2"]
}
```

### `executive_summary` (List[Dict])
Summary cards for the dashboard.
```json
{
    "summary_id": "exec_1",
    "title": "Quality Score",
    "value": "95.0",
    "status": "excellent",
    "description": "Overall data quality is excellent."
}
```

## 6. Best Practices

1.  **Polars over Pandas:** Use Polars for data manipulation for performance.
2.  **Robust Error Handling:** Always wrap the main execution in a `try...except` block that returns a valid JSON error response, not a raw 500 stack trace.
3.  **Parameter Defaults:** Never assume a parameter exists. Use `.get('param', default_value)`.
4.  **Limits:** Cap the number of returned `row_level_issues` (e.g., 1000) and `alerts` to avoid overwhelming the frontend or network.
5.  **Numpy Types:** Use a helper function to convert Numpy types (int64, float64, NaN) to Python types before returning JSON.
6.  **Private Helpers:** Keep the main execution function clean by moving detailed logic to `_private_functions`.