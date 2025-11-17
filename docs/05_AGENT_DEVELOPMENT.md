# Agensium Backend - Agent Development Guide

## Creating a New Agent

This guide walks you through creating a new agent that integrates seamlessly with the Agensium Backend.

---

## Agent Architecture

All agents follow a **standardized interface** for consistency and integra with the framework.

### Standardized Interface

Every agent must implement a single execution function:

```python
def execute_AGENT_NAME(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute the agent analysis.

    Args:
        file_contents: Binary file contents
        filename: Original filename (used to detect format)
        parameters: Agent-specific parameters from tool definition

    Returns:
        Standardized output dictionary
    """
    pass
```

### Standardized Output Format

Every agent must return this structure:

```python
{
    "status": "success" | "error",
    "agent_id": "unique-agent-id",
    "agent_name": "Human Readable Name",
    "execution_time_ms": int,

    # Only for successful execution
    "summary_metrics": {
        "metric1": value,
        "metric2": value,
        # Custom metrics relevant to agent
    },

    # Only for successful execution
    "data": {
        "field1": {...},
        "field2": {...},
        # Custom analysis data
        "summary": "string description of results"
    },

    # Only for errors
    "error": "error message string"
}
```

---

## Step-by-Step: Creating an Agent

### Step 1: Create Agent Module

Create file: `backend/agents/my_agent.py`

```python
"""
My Custom Agent

Brief description of what this agent does.
Longer explanation of its purpose and capabilities.
"""

import pandas as pd
import numpy as np
import io
import time
from typing import Dict, Any, Optional, List


def execute_my_agent(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute my custom agent.

    Args:
        file_contents: Binary file contents (CSV/JSON/XLSX)
        filename: Original filename (used to detect format)
        parameters: Agent-specific parameters from tool definition

    Returns:
        Standardized agent output
    """

    start_time = time.time()
    parameters = parameters or {}

    # Extract parameters with defaults
    param1 = parameters.get("param1", "default_value")
    param2 = parameters.get("param2", 100)

    try:
        # 1. Read file based on format
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_contents), on_bad_lines='skip')
        elif filename.endswith('.json'):
            df = pd.read_json(io.BytesIO(file_contents))
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(file_contents))
        else:
            return {
                "status": "error",
                "agent_id": "my-agent",
                "error": f"Unsupported file format: {filename}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # 2. Validate data
        if df.empty:
            return {
                "status": "error",
                "agent_id": "my-agent",
                "agent_name": "My Agent",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # 3. Perform analysis
        analysis_result = _perform_analysis(df, param1, param2)

        # 4. Identify issues
        issues = _identify_issues(df, analysis_result)

        # 5. Build summary metrics
        summary_metrics = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "issues_found": len(issues),
            "analysis_score": analysis_result.get("score", 0)
        }

        # 6. Build response
        return {
            "status": "success",
            "agent_id": "my-agent",
            "agent_name": "My Agent",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": summary_metrics,
            "data": {
                "analysis": analysis_result,
                "issues": issues,
                "summary": f"Analysis completed. Found {len(issues)} issues."
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "my-agent",
            "agent_name": "My Agent",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _perform_analysis(df: pd.DataFrame, param1: str, param2: int) -> Dict[str, Any]:
    """Perform the main analysis logic."""
    # Your custom analysis code here
    return {
        "score": 75,
        "findings": [],
        "details": {}
    }


def _identify_issues(df: pd.DataFrame, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Identify issues from the analysis."""
    issues = []

    # Example issue identification
    if analysis.get("score", 0) < 70:
        issues.append({
            "type": "low_score",
            "severity": "medium",
            "message": f"Score {analysis['score']:.1f} is below threshold of 70"
        })

    return issues


def _convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        val = float(obj)
        if np.isnan(val):
            return None
        elif np.isinf(val):
            return str(val)
        return val
    elif isinstance(obj, (float, int)) and not isinstance(obj, bool):
        if isinstance(obj, float):
            if np.isnan(obj):
                return None
            elif np.isinf(obj):
                return str(obj)
        return obj
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: _convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy_types(item) for item in obj]
    else:
        return obj
```

### Step 2: Update Agent Exports

Edit: `backend/agents/__init__.py`

```python
# Agents package
from . import (
    unified_profiler,
    drift_detector,
    score_risk,
    readiness_rater,
    governance_checker,
    test_coverage_agent,
    null_handler,
    outlier_remover,
    type_fixer,
    my_agent  # Add this line
)

__all__ = [
    'unified_profiler',
    'drift_detector',
    'score_risk',
    'readiness_rater',
    'governance_checker',
    'test_coverage_agent',
    'null_handler',
    'outlier_remover',
    'type_fixer',
    'my_agent'  # Add this line
]
```

### Step 3: Register in Tool Definition

Edit: `backend/tools/clean_my_data_tool.json` (or `profile_my_data_tool.json`)

Add to `available_agents` array:

```json
"available_agents": [
  "null-handler",
  "my-agent"  // Add this
]
```

Add agent definition in `agents` object:

```json
"my-agent": {
  "id": "my-agent",
  "name": "My Agent",
  "description": "Brief description of what this agent does",
  "icon": "🔧",
  "category": "Analysis Category",
  "accuracy": "95%",
  "features": [
    "Feature 1",
    "Feature 2",
    "Feature 3"
  ],
  "input": { "type": "CSV, JSON, XLSX" },
  "version": "1.0.0",
  "required_files": ["primary"],
  "parameters": {
    "param1": {
      "type": "string",
      "description": "Description of parameter",
      "default": "default_value"
    },
    "param2": {
      "type": "integer",
      "description": "Another parameter",
      "default": 100,
      "min": 1,
      "max": 1000
    }
  },
  "output_structure": {
    "agent_id": "string",
    "agent_name": "string",
    "status": "string",
    "execution_time_ms": "integer",
    "summary_metrics": {
      "metric1": "type",
      "metric2": "type"
    },
    "data": {
      "analysis_result": "object",
      "issues": "array",
      "summary": "string"
    }
  }
}
```

### Step 4: Add Route Handler

Edit: `backend/api/routes.py`

Add import:

```python
from agents import my_agent
```

Add case in `execute_agent_flexible()`:

```python
elif agent_id == "my-agent":
    if "primary" not in files_map:
        return {
            "status": "error",
            "error": "My Agent requires 'primary' file",
            "execution_time_ms": 0
        }

    primary_bytes, primary_filename = files_map["primary"]

    return my_agent.execute_my_agent(
        primary_bytes,
        primary_filename,
        parameters
    )
```

### Step 5: Update Transformer (if creating new tool)

If creating a new tool (not adding to existing), create transformer:

`backend/transformers/my_tool_transformer.py`

```python
"""
My Tool Transformer

Aggregates results from my custom tool's agents.
"""

from typing import Dict, List, Any
from datetime import datetime
import base64
import io
from openpyxl import Workbook


def transform_my_tool_response(
    agent_results: Dict[str, Any],
    execution_time_ms: int,
    analysis_id: str
) -> Dict[str, Any]:
    """
    Transform individual agent outputs into final unified response.

    Args:
        agent_results: Dictionary of agent_id -> agent output
        execution_time_ms: Total execution time
        analysis_id: Unique analysis identifier

    Returns:
        Final unified response
    """

    all_alerts = []
    all_issues = []
    all_recommendations = []

    # Process agent results
    for agent_id, output in agent_results.items():
        if output.get("status") == "success":
            # Extract findings
            agent_data = output.get("data", {})

            # Create alerts
            if agent_data.get("issues"):
                for issue in agent_data["issues"]:
                    all_alerts.append({
                        "alert_id": f"alert_{agent_id}_{issue.get('type', 'unknown')}",
                        "severity": issue.get("severity", "medium"),
                        "category": "custom_analysis",
                        "message": issue.get("message", ""),
                        "affected_fields_count": 0,
                        "recommendation": ""
                    })

    # Build final response
    return {
        "analysis_id": analysis_id,
        "tool": "my-tool",
        "status": "success",
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "execution_time_ms": execution_time_ms,
        "report": {
            "alerts": all_alerts,
            "issues": all_issues,
            "recommendations": all_recommendations,
            "executiveSummary": [],
            "analysisSummary": {
                "status": "success",
                "summary": "Analysis completed successfully",
                "execution_time_ms": 0,
                "model_used": None
            },
            "routing_decisions": [],
            "downloads": []
        }
    }
```

### Step 6: Update Transformer Exports

Edit: `backend/transformers/__init__.py`

```python
from . import profile_my_data_transformer, clean_my_data_transformer, my_tool_transformer

__all__ = [
    'profile_my_data_transformer',
    'clean_my_data_transformer',
    'my_tool_transformer'
]
```

---

## Agent Development Best Practices

### 1. Error Handling

Always handle exceptions gracefully:

```python
try:
    # Analysis code
except Exception as e:
    return {
        "status": "error",
        "agent_id": "my-agent",
        "error": f"Analysis failed: {str(e)}",
        "execution_time_ms": int((time.time() - start_time) * 1000)
    }
```

### 2. Type Conversion

Convert numpy types to native Python for JSON serialization:

```python
# Before returning data
return {
    ...
    "data": _convert_numpy_types(analysis_result)
}
```

### 3. Performance

For large files, consider:

- Sample data instead of processing all rows
- Limit output to first N issues
- Use appropriate algorithms (O(n) vs O(n²))

```python
# Limit issues to first 100 for performance
issues = issues[:100]
```

### 4. Logging

Use print statements for debugging (visible in server logs):

```python
print(f"Processing {len(df)} rows...")
print(f"Found {len(issues)} issues")
```

### 5. Validation

Always validate input data:

```python
if df.empty:
    return {"status": "error", "error": "Empty file"}

if not any(col in df.columns for col in required_columns):
    return {"status": "error", "error": f"Missing required columns"}
```

### 6. Documentation

Document all parameters and outputs:

```python
"""
Execute my agent.

Parameters:
    param1 (str): Controls analysis mode
    param2 (int): Threshold value (0-100)

Returns:
    Dictionary with status, metrics, and analysis data

Example:
    result = execute_my_agent(file_bytes, "data.csv",
                             {"param1": "strict", "param2": 80})
"""
```

---

## Testing Your Agent

### Unit Test Example

```python
# test_my_agent.py
import pytest
import io
import pandas as pd
from agents.my_agent import execute_my_agent

def test_my_agent_success():
    # Create test data
    df = pd.DataFrame({
        'col1': [1, 2, 3, 4, 5],
        'col2': ['a', 'b', 'c', 'd', 'e']
    })

    # Save to CSV bytes
    csv_buffer = io.BytesIO()
    df.to_csv(csv_buffer, index=False)
    file_contents = csv_buffer.getvalue()

    # Execute agent
    result = execute_my_agent(file_contents, "test.csv")

    # Assert
    assert result["status"] == "success"
    assert result["agent_id"] == "my-agent"
    assert "execution_time_ms" in result
    assert "summary_metrics" in result
    assert "data" in result

def test_my_agent_empty_file():
    # Create empty CSV
    csv_buffer = io.BytesIO()
    file_contents = csv_buffer.getvalue()

    # Execute agent
    result = execute_my_agent(file_contents, "empty.csv")

    # Assert
    assert result["status"] == "error"
    assert "error" in result

def test_my_agent_with_parameters():
    df = pd.DataFrame({'col1': range(100)})
    csv_buffer = io.BytesIO()
    df.to_csv(csv_buffer, index=False)

    result = execute_my_agent(
        csv_buffer.getvalue(),
        "test.csv",
        {"param1": "custom", "param2": 50}
    )

    assert result["status"] == "success"

# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### Manual Testing

```bash
# Start server
python main.py

# Test agent via API
curl -X POST "http://localhost:8000/analyze" \
  -F "tool_id=clean-my-data" \
  -F "primary=@test_data.csv" \
  -F "agents=my-agent"
```

---

## Common Agent Patterns

### Pattern 1: Statistical Analysis

```python
def _analyze_statistics(df: pd.DataFrame) -> Dict[str, Any]:
    """Analyze basic statistics."""
    stats = {}
    for col in df.select_dtypes(include=[np.number]).columns:
        stats[col] = {
            "mean": float(df[col].mean()),
            "median": float(df[col].median()),
            "std": float(df[col].std()),
            "min": float(df[col].min()),
            "max": float(df[col].max())
        }
    return stats
```

### Pattern 2: Null Detection

```python
def _analyze_nulls(df: pd.DataFrame) -> Dict[str, Any]:
    """Analyze null values."""
    null_summary = {}
    for col in df.columns:
        null_count = df[col].isnull().sum()
        null_pct = (null_count / len(df)) * 100
        if null_count > 0:
            null_summary[col] = {
                "null_count": int(null_count),
                "null_percentage": round(null_pct, 2)
            }
    return null_summary
```

### Pattern 3: Pattern Detection

```python
import re

def _detect_patterns(df: pd.DataFrame, col: str) -> Dict[str, Any]:
    """Detect value patterns in column."""
    patterns = {
        "email": r".*@.*\\..*",
        "phone": r"^\\d{3}-\\d{3}-\\d{4}$",
        "ssn": r"^\\d{3}-\\d{2}-\\d{4}$"
    }

    detected = {}
    for pattern_name, pattern in patterns.items():
        matches = df[col].astype(str).str.match(pattern).sum()
        if matches > 0:
            detected[pattern_name] = int(matches)

    return detected
```

### Pattern 4: Quality Scoring

```python
def _calculate_quality_score(
    completeness: float,
    consistency: float,
    validity: float
) -> float:
    """Calculate weighted quality score."""
    weights = {
        "completeness": 0.4,
        "consistency": 0.3,
        "validity": 0.3
    }

    score = (
        completeness * weights["completeness"] +
        consistency * weights["consistency"] +
        validity * weights["validity"]
    )

    return round(score, 1)
```

---

## Checklist for New Agent

- [ ] Agent module created (`agents/my_agent.py`)
- [ ] Function signature matches standard interface
- [ ] Output format matches standard structure
- [ ] Agent exported in `agents/__init__.py`
- [ ] Tool definition updated with agent
- [ ] Route handler added to `routes.py`
- [ ] Transformer updated (if new tool)
- [ ] Transformer exported (if new tool)
- [ ] Parameters documented
- [ ] Error handling implemented
- [ ] Numpy type conversion included
- [ ] Unit tests created
- [ ] Manual API testing completed
- [ ] Documentation updated

---

## Next Steps

- Read [03_TOOLS_OVERVIEW.md](./03_TOOLS_OVERVIEW.md) for agent parameter examples
- Read [04_API_REFERENCE.md](./04_API_REFERENCE.md) for API integration
- Read [02_ARCHITECTURE.md](./02_ARCHITECTURE.md) for system context
