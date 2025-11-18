# Agensium Backend - API Reference

## Base URL

```
http://localhost:8000
```

## Authentication

Currently no authentication required. API key support can be added via middleware.

---

## Endpoints Summary

| Method | Path               | Purpose             |
| ------ | ------------------ | ------------------- |
| GET    | `/`                | Service information |
| GET    | `/health`          | Health check        |
| GET    | `/tools`           | List all tools      |
| GET    | `/tools/{tool_id}` | Get tool definition |
| POST   | `/analyze`         | Execute analysis    |
| POST   | `/chat`            | **Chat Q&A (NEW)**  |

---

## Endpoint Details

### 1. GET /

Get service information and available tools.

**Response**:

```json
{
  "service": "Agensium Backend",
  "version": "1.0.0",
  "tools": ["profile-my-data", "clean-my-data"],
  "documentation": "/docs"
}
```

---

### 2. GET /health

Health check endpoint for monitoring.

**Response**:

```json
{
  "status": "ok"
}
```

**HTTP Status**: 200 OK

---

### 3. GET /tools

List all available tools with basic information.

**Response**:

```json
{
  "tools": [
    {
      "id": "profile-my-data",
      "name": "Profile My Data",
      "description": "Comprehensive data profiling...",
      "icon": "📊",
      "available": true,
      "agents_count": 6
    },
    {
      "id": "clean-my-data",
      "name": "Clean My Data",
      "description": "Data cleaning and validation...",
      "icon": "🧹",
      "available": true,
      "agents_count": 5
    }
  ]
}
```

**HTTP Status**: 200 OK

---

### 4. GET /tools/{tool_id}

Get detailed tool definition including all agent specifications.

**Path Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| tool_id | string | Yes | Tool identifier (e.g., "profile-my-data") |

**Example**:

```bash
curl http://localhost:8000/tools/profile-my-data
```

**Response Structure**:

```json
{
  "tool": {
    "id": "profile-my-data",
    "name": "Profile My Data",
    "description": "...",
    "icon": "📊",
    "category": "source",
    "isAvailable": true,
    "version": "1.0.0",
    "available_agents": ["unified-profiler", "drift-detector", ...],
    "files": {
      "primary": {
        "description": "Current data file to profile",
        "required": true,
        "formats": ["csv", "json", "xlsx"],
        "max_size_mb": 500
      },
      "baseline": {
        "description": "Baseline data file for drift detection",
        "required": false,
        "formats": ["csv", "json", "xlsx"],
        "max_size_mb": 500
      }
    }
  },
  "agents": {
    "unified-profiler": {
      "id": "unified-profiler",
      "name": "Unified Profiler",
      "description": "Comprehensive data profiling with statistics...",
      "icon": "📈",
      "category": "Data Analysis",
      "accuracy": "99%",
      "version": "1.0.0",
      "required_files": ["primary"],
      "parameters": {
        "null_alert_threshold": {
          "type": "number",
          "default": 50,
          "min": 0,
          "max": 100
        },
        ...
      },
      "output_structure": {
        "agent_id": "string",
        "agent_name": "string",
        "status": "string",
        "execution_time_ms": "integer",
        "summary_metrics": {...},
        "data": {...}
      }
    },
    ...
  },
  "file_requirements": {...}
}
```

**HTTP Status**: 200 OK or 404 if tool not found

---

### 5. POST /analyze

Main analysis endpoint - execute tool and agents on uploaded data.

**Content-Type**: `multipart/form-data`

**Form Parameters**:

| Name            | Type   | Required | Description                         | Example                                            |
| --------------- | ------ | -------- | ----------------------------------- | -------------------------------------------------- |
| tool_id         | string | Yes      | Tool to execute                     | "profile-my-data"                                  |
| primary         | file   | Yes      | Primary data file (CSV/JSON/XLSX)   | data.csv                                           |
| baseline        | file   | No       | Baseline file for drift detection   | baseline.csv                                       |
| agents          | string | No       | Comma-separated agent IDs           | "unified-profiler,drift-detector"                  |
| parameters_json | string | No       | JSON with agent-specific parameters | `{"unified-profiler":{"null_alert_threshold":40}}` |

**File Constraints**:

- Formats: CSV, JSON, XLSX, XLS
- Max size: 500MB
- Required for most tools: primary file
- Optional: baseline file (for drift detection)

#### Example cURL Requests

**Basic Analysis (default agents)**:

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "tool_id=profile-my-data" \
  -F "primary=@data.csv"
```

**With Specific Agents**:

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "tool_id=profile-my-data" \
  -F "primary=@data.csv" \
  -F "agents=unified-profiler,drift-detector,score-risk"
```

**With Baseline File**:

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "tool_id=profile-my-data" \
  -F "primary=@current.csv" \
  -F "baseline=@baseline.csv" \
  -F "agents=drift-detector"
```

**With Custom Parameters**:

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "tool_id=profile-my-data" \
  -F "primary=@data.csv" \
  -F "agents=unified-profiler" \
  -F 'parameters_json={"unified-profiler":{"null_alert_threshold":30,"categorical_threshold":15}}'
```

**Clean Data Tool**:

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "tool_id=clean-my-data" \
  -F "primary=@data.csv" \
  -F "agents=null-handler,outlier-remover,type-fixer" \
  -F 'parameters_json={
        "null-handler":{"global_strategy":"column_specific"},
        "outlier-remover":{"detection_method":"iqr"},
        "type-fixer":{"auto_convert_numeric":true}
      }'
```

#### Example Python Code

```python
import requests
import json

# Prepare files
files = {
    'primary': open('data.csv', 'rb'),
}

# Prepare data
data = {
    'tool_id': 'profile-my-data',
    'agents': 'unified-profiler,drift-detector',
    'parameters_json': json.dumps({
        'unified-profiler': {
            'null_alert_threshold': 40
        }
    })
}

# Make request
response = requests.post(
    'http://localhost:8000/analyze',
    files=files,
    data=data
)

# Handle response
result = response.json()
print(f"Analysis ID: {result['analysis_id']}")
print(f"Status: {result['status']}")
print(f"Alerts: {len(result['report']['alerts'])}")
print(f"Execution time: {result['execution_time_ms']}ms")

# Close file
files['primary'].close()
```

---

## Response Format

### Success Response (200 OK)

```json
{
  "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
  "tool": "profile-my-data",
  "status": "success",
  "timestamp": "2025-11-17T12:34:56.789Z",
  "execution_time_ms": 5000,
  "report": {
    "alerts": [
      {
        "alert_id": "alert_quality_001",
        "severity": "high|medium|low",
        "category": "data_quality|governance|risk|drift|readiness",
        "message": "Data quality score is 65/100, below threshold of 80",
        "affected_fields_count": 5,
        "recommendation": "Review and improve data quality through cleaning"
      }
    ],
    "issues": [
      {
        "issue_id": "issue_null_age",
        "agent_id": "unified-profiler",
        "field_name": "age",
        "issue_type": "missing_values|type_mismatch|outlier|governance_violation|test_failure",
        "severity": "high|medium|warning",
        "message": "Column 'age' has 25% null values (high alert threshold: 50%)"
      }
    ],
    "recommendations": [
      {
        "recommendation_id": "rec_null_age",
        "agent_id": "null-handler",
        "field_name": "age",
        "priority": "high|medium|low",
        "recommendation": "Impute null values in 'age' using median strategy",
        "timeline": "1 week|2 weeks|3 weeks|4 weeks"
      }
    ],
    "executiveSummary": [
      {
        "summary_id": "exec_quality",
        "title": "Data Quality Score",
        "value": "65",
        "status": "excellent|good|fair|poor",
        "description": "Overall data quality grade: C (65/100)"
      },
      {
        "summary_id": "exec_fields",
        "title": "Fields Analyzed",
        "value": "45",
        "status": "success",
        "description": "45 fields processed and analyzed"
      },
      {
        "summary_id": "exec_risk",
        "title": "Data Risk Assessment",
        "value": "45",
        "status": "medium",
        "description": "Medium risk: 2 PII columns detected (email, phone)"
      },
      {
        "summary_id": "exec_readiness",
        "title": "Production Readiness",
        "value": "58",
        "status": "not_ready",
        "description": "Data requires improvements before production use"
      }
    ],
    "analysisSummary": {
      "status": "success|pending|error",
      "summary": "Data analysis shows moderate quality issues requiring attention. Null values in 5 columns and type inconsistencies in 3 columns are the primary concerns. Address these issues through cleaning before production deployment. Risk score indicates presence of personally identifiable information requiring governance controls.",
      "execution_time_ms": 1200,
      "model_used": "gpt-4|fallback-rule-based"
    },
    "routing_decisions": [
      {
        "recommendation_id": "route_1",
        "next_tool": "clean-my-data",
        "confidence_score": 0.95,
        "reason": "Data quality score is 65/100. Run Clean My Data to improve quality through null handling and type fixing.",
        "priority": 1,
        "path": "/results/clean-my-data",
        "required_files": {
          "primary": {
            "name": "data.csv",
            "available": true
          }
        },
        "parameters": {
          "selected_agents": ["null-handler", "outlier-remover", "type-fixer", "governance-checker"],
          "agent_parameters": {}
        },
        "expected_benefits": [
          "Improved data quality score",
          "Null values handled",
          "Type inconsistencies fixed",
          "Higher production readiness"
        ],
        "estimated_time_minutes": 10,
        "execution_steps": [
          "Run Clean My Data with selected agents",
          "Review cleaning results",
          "Compare metrics before/after",
          "Export cleaned dataset"
        ]
      }
    ],
    "downloads": [
      {
        "download_id": "report_2025_11_17",
        "name": "Complete Analysis Report",
        "format": "xlsx",
        "description": "Comprehensive analysis with all findings, metrics, and recommendations",
        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "blob": "UEsDBBQABgAIAAAAIQDfpq61yQAAAOoAAAALAAAAX3JlbHMvLnJlbHM...",
        "size_bytes": 45000
      }
    ],
    "unified-profiler": {
      "status": "success",
      "agent_id": "unified-profiler",
      "agent_name": "Unified Profiler",
      "execution_time_ms": 800,
      "summary_metrics": {
        "total_rows": 10000,
        "total_columns": 45,
        "columns_with_nulls": 5,
        "columns_with_issues": 15
      },
      "data": {
        "quality_summary": {...},
        "field_profiles": {...}
      }
    },
    "drift-detector": {
      "status": "success",
      "agent_id": "drift-detector",
      "agent_name": "Drift Detector",
      "execution_time_ms": 600,
      "summary_metrics": {
        "fields_compared": 45,
        "fields_with_drift": 8,
        "average_psi_score": 0.15
      },
      "data": {
        "drift_summary": {...}
      }
    }
  }
}
```

### Alert Object Structure

```json
{
  "alert_id": "alert_quality_001",
  "severity": "high|medium|low",
  "category": "data_quality|governance|risk|drift|readiness",
  "message": "Human-readable alert message",
  "affected_fields_count": 5,
  "recommendation": "Suggested action to address the alert"
}
```

**Alert Categories**:

- `data_quality`: Quality score issues
- `governance`: Compliance/governance gaps
- `risk`: Security/PII concerns
- `drift`: Distribution changes
- `readiness`: Production readiness issues
- `data_cleaning`: Cleaning quality issues
- `outliers`: Outlier detection
- `type_issues`: Type mismatch concerns
- `testing`: Test coverage issues

### Issue Object Structure

```json
{
  "issue_id": "issue_null_age",
  "agent_id": "agent-name",
  "field_name": "column_name",
  "issue_type": "missing_values|type_mismatch|outlier|drift|governance_violation",
  "severity": "high|medium|warning",
  "message": "Specific issue description"
}
```

### Recommendation Object Structure

```json
{
  "recommendation_id": "rec_null_age",
  "agent_id": "agent-name",
  "field_name": "column_name",
  "priority": "high|medium|low",
  "recommendation": "Specific action to take",
  "timeline": "1 week|2 weeks|3 weeks|4 weeks"
}
```

### Executive Summary Object Structure

```json
{
  "summary_id": "exec_quality|exec_fields|exec_risk|exec_readiness|exec_drift",
  "title": "Metric name",
  "value": "75",
  "status": "excellent|good|fair|poor|success|warning|error",
  "description": "Human-readable description"
}
```

---

## Error Responses

### 400 - Bad Request

Missing or invalid parameters:

```json
{
  "detail": "Tool 'invalid-tool' not found. Available tools: profile-my-data, clean-my-data"
}
```

```json
{
  "detail": "Required file 'primary' not provided"
}
```

```json
{
  "detail": "File format '.xls' not allowed for 'primary'. Allowed: csv, json, xlsx"
}
```

### 500 - Internal Server Error

Agent execution failure:

```json
{
  "detail": "Agent 'unified-profiler' failed: ValueError in analysis"
}
```

System error:

```json
{
  "detail": "System error: Unable to process file. Check server logs."
}
```

---

## Rate Limiting

Currently unlimited. Rate limiting can be added via middleware.

---

## File Upload Constraints

| Constraint          | Value                    |
| ------------------- | ------------------------ |
| Max file size       | 500 MB                   |
| Allowed formats     | CSV, JSON, XLSX, XLS     |
| Encoding            | UTF-8 (recommended)      |
| Timeout per request | 600 seconds (10 minutes) |

---

## Request Timeout

Large file analysis may take several minutes:

- Files < 10 MB: 15-30 seconds
- Files 10-100 MB: 30-120 seconds
- Files > 100 MB: 120+ seconds

Recommend timeout configuration: **600 seconds (10 minutes)**

---

## Best Practices

### 1. Error Handling

```python
if response.status_code != 200:
    error = response.json()
    print(f"Error: {error['detail']}")
else:
    result = response.json()
    # Process results
```

### 2. Large File Uploads

```python
# Show progress for large files
import requests_toolbelt
from requests_toolbelt.multipart.encoder import MultipartEncoder

# Create multipart encoder with progress callback
# (implementation omitted for brevity)
```

### 3. Result Processing

```python
result = response.json()

# Check for alerts
for alert in result['report']['alerts']:
    if alert['severity'] == 'high':
        print(f"⚠️ {alert['message']}")

# Check for routing recommendations
if result['report']['routing_decisions']:
    next_tool = result['report']['routing_decisions'][0]
    print(f"Next recommended tool: {next_tool['next_tool']}")
```

### 4. File Cleanup

```python
# Always close files after upload
files['primary'].close()
if 'baseline' in files:
    files['baseline'].close()
```

---

## 6. POST /chat (NEW)

Ask intelligent questions about analysis reports using LLM.

**Description**: Get natural language answers to questions about your analysis results. Powered by GPT-4o-mini.

**Request Headers**:

```
Content-Type: application/json
```

**Request Body**:

```json
{
  "agent_report": {...},           // The report object from /analyze response
  "user_question": "string",       // Question about the report
  "history": [                     // Optional - previous messages for context
    {
      "role": "user|assistant",
      "content": "message"
    }
  ]
}
```

**Parameters**:

| Name            | Type        | Required | Description                                  |
| --------------- | ----------- | -------- | -------------------------------------------- |
| `agent_report`  | JSON Object | Yes      | The `report` field from `/analyze` response  |
| `user_question` | String      | Yes      | Your question about the data analysis        |
| `history`       | Array       | No       | Previous chat messages for context awareness |

**Response** (200 OK):

```json
{
  "agent": "ChatAgent",
  "results": {
    "status": "success",
    "user_question": "What are the main data quality issues?",
    "answer": "Based on the analysis report, the main data quality issues are: 1) Customer ID field has 12% null values which affects data completeness. 2) Age field has type inconsistencies with mixed integers and strings. 3) Email field has 3 invalid formats detected. These issues should be addressed before using the data for ML models."
  }
}
```

**Error Response** (500 error):

```json
{
  "agent": "ChatAgent",
  "results": {
    "status": "error",
    "user_question": "What are the main issues?",
    "error": "Failed to get response from OpenAI. Error: API key not configured."
  }
}
```

### Chat Examples

#### Example 1: Understanding Quality Issues

**Request**:

```json
{
  "agent_report": {...full report object...},
  "user_question": "What are the main data quality issues?"
}
```

**Response**:

```json
{
  "agent": "ChatAgent",
  "results": {
    "status": "success",
    "user_question": "What are the main data quality issues?",
    "answer": "Based on the analysis, there are 5 quality issues: 1) Null values in customer_id (12%), 2) Type inconsistencies in age field, 3) Revenue field outliers (8 detected), 4) Email format issues (3 records), 5) Duplicate customer records (2.5% of data). The quality score is 72/100 (Grade C)."
  }
}
```

#### Example 2: Follow-up with Context

**Request**:

```json
{
  "agent_report": {...full report object...},
  "user_question": "How can we fix the type inconsistencies?",
  "history": [
    {"role": "user", "content": "What are the main data quality issues?"},
    {"role": "assistant", "content": "Based on the analysis, there are 5 quality issues: ..."}
  ]
}
```

**Response**:

```json
{
  "agent": "ChatAgent",
  "results": {
    "status": "success",
    "user_question": "How can we fix the type inconsistencies?",
    "answer": "The Type Fixer agent recommends converting the age field to integer type. The current inconsistency involves some values stored as integers (25) and others as strings ('25'). The conversion success rate is estimated at 98%. This will improve the quality score by approximately 8-10 points."
  }
}
```

#### Example 3: PII and Compliance

**Request**:

```json
{
  "agent_report": {...full report object...},
  "user_question": "Are we compliant with GDPR?"
}
```

**Response**:

```json
{
  "agent": "ChatAgent",
  "results": {
    "status": "success",
    "user_question": "Are we compliant with GDPR?",
    "answer": "According to the governance checker, your GDPR compliance status needs review. Three issues were identified: 1) PII data (customer names, emails) not encrypted, 2) Data retention policy not documented, 3) Two fields flagged as potentially sensitive require access control. Compliance score: 65/100. Recommend addressing these issues within 2-3 weeks."
  }
}
```

#### Example 4: Readiness Assessment

**Request**:

```json
{
  "agent_report": {...full report object...},
  "user_question": "Is this data ready for production?"
}
```

**Response**:

```json
{
  "agent": "ChatAgent",
  "results": {
    "status": "success",
    "user_question": "Is this data ready for production?",
    "answer": "The data readiness assessment shows a score of 68/100 with status 'needs_review'. While the data quality is acceptable (72/100), there are 3 areas requiring improvement: 1) Data completeness issues in key fields, 2) Test coverage insufficient (62/100), 3) Governance compliance at 65/100. Recommend addressing these items before production deployment."
  }
}
```

### Chat Configuration

**Environment Variable** (for OpenAI API):

```bash
export OPENAI_API_KEY="sk-your-openai-api-key-here"
```

**Model Used**: `gpt-4o-mini` (cost-effective and powerful)

**Without API Key**: Returns error message with instructions to set `OPENAI_API_KEY`

### Chat Error Handling

**Common Errors**:

| Error                    | Cause                       | Solution                  |
| ------------------------ | --------------------------- | ------------------------- |
| "API key not configured" | `OPENAI_API_KEY` not set    | Set environment variable  |
| "Rate limit exceeded"    | Too many requests to OpenAI | Wait before next request  |
| "Invalid model name"     | Wrong model in environment  | Use `gpt-4o-mini`         |
| "Connection timeout"     | Network issues to OpenAI    | Check internet connection |

**Example Error Response**:

```json
{
  "detail": "Failed to get response from OpenAI. Error: The model 'gpt-4o-mini' does not exist"
}
```

---

## Next Steps

- Read [03_TOOLS_OVERVIEW.md](./03_TOOLS_OVERVIEW.md) for agent parameters
- Read [07_DOWNLOADS_AND_CHAT.md](./07_DOWNLOADS_AND_CHAT.md) for detailed chat guide
- Read [02_ARCHITECTURE.md](./02_ARCHITECTURE.md) for system flow
- Read [05_AGENT_DEVELOPMENT.md](./05_AGENT_DEVELOPMENT.md) for creating agents
