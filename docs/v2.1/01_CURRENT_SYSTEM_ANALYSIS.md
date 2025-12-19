# Current System Analysis - Agensium V2.1 Backend

**Document Version:** 2.1  
**Created:** December 19, 2025  
**Updated:** December 19, 2025  
**Purpose:** Comprehensive analysis of the current synchronous system before V2.1 migration

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture Overview](#current-architecture-overview)
3. [API Routes Analysis](#api-routes-analysis)
4. [Transformers System](#transformers-system)
5. [Agent System](#agent-system)
6. [Database Models](#database-models)
7. [File Handling](#file-handling)
8. [Downloads System](#downloads-system)
9. [Billing Integration](#billing-integration)
10. [Current Pain Points](#current-pain-points)
11. [What Needs to Change](#what-needs-to-change)

---

## Executive Summary

The current Agensium backend is a **synchronous FastAPI application** that processes data files in real-time. Users upload files directly to the backend, which processes them immediately through multiple agents and returns results in a single HTTP response.

### Key Characteristics

| Aspect              | Current State                                  |
| ------------------- | ---------------------------------------------- |
| **Architecture**    | Synchronous, single-request processing         |
| **File Upload**     | Direct to backend server (multipart/form-data) |
| **File Storage**    | In-memory processing (no persistent storage)   |
| **Processing**      | Sequential agent execution, blocking           |
| **Response Time**   | 10-60+ seconds depending on file size          |
| **Scalability**     | Limited by single-request memory/CPU           |
| **File Size Limit** | ~500MB (practical limit ~100MB)                |

---

## Current Architecture Overview

### High-Level Flow

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Frontend  │────►│  POST /analyze   │────►│   Transformer    │
│   (React)   │     │  (FastAPI)       │     │   (profile/clean/│
└─────────────┘     └──────────────────┘     │   master)        │
                            │                └────────┬─────────┘
                            │                         │
                            │                         ▼
                            │                ┌────────────────────┐
                            │                │     Agents         │
                            │                │  (unified-profiler,│
                            │                │   drift-detector,  │
                            │                │   score-risk, etc) │
                            │                └────────┬───────────┘
                            │                         │
                            │                         ▼
                            │                ┌────────────────────┐
                            │                │   Downloads        │
                            │                │  (Excel, JSON)     │
                            ◄────────────────│  base64 encoded    │
                                             └────────────────────┘
```

### Component Architecture

```
backend/
├── main.py                  # FastAPI app, CORS, tool definitions loader
├── api/
│   └── routes.py            # POST /analyze, POST /chat, GET /tools
├── transformers/
│   ├── profile_my_data_transformer.py
│   ├── clean_my_data_transformer.py
│   ├── master_my_data_transformer.py
│   └── transformers_utils.py    # File handling, billing context
├── agents/
│   ├── unified_profiler.py
│   ├── drift_detector.py
│   ├── score_risk.py
│   └── ... (20+ agents)
├── downloads/
│   ├── profile_my_data_downloads.py
│   ├── clean_my_data_downloads.py
│   └── master_my_data_downloads.py
├── tools/
│   ├── profile_my_data_tool.json
│   ├── clean_my_data_tool.json
│   └── master_my_data_tool.json
├── db/
│   ├── database.py          # MySQL connection
│   ├── models.py            # User, Wallet, Transaction
│   └── schemas.py           # Pydantic validation
├── auth/                    # JWT authentication
├── billing/                 # Credit wallet system
└── ai/                      # OpenAI integrations
```

---

## API Routes Analysis

### Main Endpoint: POST /analyze

**Location:** `api/routes.py`

**Current Implementation:**

```python
@router.post("/analyze")
async def analyze(
    tool_id: str = Form(...),
    agents: Optional[str] = Form(None),
    parameters_json: Optional[str] = Form(None),
    primary: Optional[UploadFile] = File(None),
    baseline: Optional[UploadFile] = File(None),
    current_user: models.User = Depends(get_current_active_verified_user)
)
```

**Flow:**

1. **Authentication** - Validates JWT token, gets current user
2. **Generate analysis_id** - UUID for this analysis
3. **Route to Transformer** - Based on tool_id:
   - `profile-my-data` → `profile_my_data_transformer`
   - `clean-my-data` → `clean_my_data_transformer`
   - `master-my-data` → `master_my_data_transformer`
4. **Return Results** - JSON response with all results

### Problem Areas

| Issue                       | Impact                              |
| --------------------------- | ----------------------------------- |
| **Synchronous processing**  | User waits 10-60+ seconds           |
| **In-memory file handling** | Memory pressure for large files     |
| **No persistence**          | Results lost if user disconnects    |
| **No retry capability**     | Failed analysis must restart        |
| **Single response**         | All or nothing - no partial results |

---

## Transformers System

### Purpose

Transformers orchestrate agent execution and consolidate outputs into unified responses.

### Profile My Data Transformer

**Location:** `transformers/profile_my_data_transformer.py`

**Agents Executed:**

- `unified-profiler` - Comprehensive data profiling
- `drift-detector` - Baseline comparison (optional)
- `score-risk` - PII and risk assessment
- `governance-checker` - Compliance validation
- `test-coverage-agent` - Test coverage validation
- `readiness-rater` - Readiness scoring

**Flow:**

```python
async def run_profile_my_data_analysis(...):
    # 1. Validate tool definition
    # 2. Get required files for agents
    # 3. Validate uploaded files
    # 4. Read files into memory
    # 5. Convert to CSV if needed (xlsx, json → csv)
    # 6. Parse parameters JSON

    # 7. Execute agents with billing
    with BillingContext(current_user) as billing:
        for agent_id in agents_to_run:
            # Debit credits BEFORE execution
            billing_error = billing.consume_credits_for_agent(...)
            if billing_error:
                return billing_error

            # Build agent input
            agent_input = _build_agent_input(agent_id, files_map, parameters)

            # Execute agent (synchronous)
            result = _execute_agent(agent_id, agent_input)
            agent_results[agent_id] = result

    # 8. Transform results into unified response
    return transform_profile_my_data_response(agent_results, ...)
```

### Clean My Data Transformer

**Key Difference:** Agent chaining - each agent passes cleaned file to next agent.

```python
def _update_files_from_result(files_map, result):
    """Update files map with cleaned file from agent result."""
    if result.get("status") == "success" and "cleaned_file" in result:
        new_content = base64.b64decode(cleaned_file["content"])
        files_map["primary"] = (new_content, new_filename)
```

**Agents Executed:**

- `quarantine-agent`
- `null-handler`
- `outlier-remover`
- `type-fixer`
- `duplicate-resolver`
- `field-standardization`
- `cleanse-writeback`
- `cleanse-previewer`

### Master My Data Transformer

Similar to clean-my-data with agent chaining for mastered files.

**Agents Executed:**

- `key-identifier`
- `contract-enforcer`
- `semantic-mapper`
- `lineage-tracer`
- `golden-record-builder`
- `survivorship-resolver`
- `master-writeback-agent`
- `stewardship-flagger`

---

## Agent System

### Agent Input/Output Contract

**Input:**

```python
{
    "agent_id": str,
    "files": {
        "primary": (bytes, filename),
        "baseline": (bytes, filename)  # optional
    },
    "parameters": dict  # agent-specific config
}
```

**Output:**

```python
{
    "status": "success" | "error",
    "agent_id": str,
    "execution_time_ms": int,

    # Standard outputs
    "alerts": List[Alert],
    "issues": List[Issue],
    "recommendations": List[Recommendation],
    "row_level_issues": List[RowIssue],
    "executive_summary": List[SummaryItem],
    "ai_analysis_text": str,

    # Agent-specific data
    "field_profiles": List[FieldProfile],  # unified-profiler
    "drift_analysis": DriftResult,          # drift-detector
    "cleaned_file": CleanedFile,            # cleaning agents
    ...
}
```

### Agent Processing Pattern

```python
def profile_data(file_contents: bytes, filename: str, parameters: dict) -> dict:
    start_time = time.time()

    try:
        # 1. Parse file with Polars
        df = pl.read_csv(io.BytesIO(file_contents))

        # 2. Process data (field profiles, statistics, etc.)
        ...

        # 3. Generate alerts, issues, recommendations
        ...

        # 4. Return standardized output
        return {
            "status": "success",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            ...
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }
```

---

## Database Models

### Current Models (db/models.py)

```python
# User Management
class User(Base):
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True)
    hashed_password = Column(String(255))
    full_name = Column(String(100))
    stripe_customer_id = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    otp_code = Column(String(6))
    otp_expires_at = Column(DateTime)
    otp_type = Column(String(50))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

# Billing System
class CreditWallet(Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    balance_credits = Column(Integer, default=0)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class CreditTransaction(Base):
    id = Column(String(26), primary_key=True)  # ULID
    user_id = Column(Integer, ForeignKey("users.id"))
    delta_credits = Column(Integer)
    type = Column(String(50))  # PURCHASE, CONSUME, REFUND, ADJUSTMENT, GRANT
    reason = Column(String(500))
    agent_id = Column(String(100))
    tool_id = Column(String(100))
    analysis_id = Column(String(100))
    stripe_checkout_session_id = Column(String(255))
    stripe_payment_intent_id = Column(String(255))
    created_at = Column(DateTime)

class AgentCost(Base):
    agent_id = Column(String(100), primary_key=True)
    cost = Column(Integer)
    description = Column(String(255))
```

### Missing: Task Model

**Currently there is NO Task model** - analysis is stateless and ephemeral.

---

## File Handling

### Current Flow (transformers_utils.py)

```python
# 1. Read uploaded files into memory
async def read_uploaded_files(uploaded_files: Dict[str, UploadFile]) -> Dict[str, tuple]:
    files_map = {}
    for file_key, file_obj in uploaded_files.items():
        if file_obj:
            file_contents = await file_obj.read()  # ENTIRE FILE IN MEMORY
            files_map[file_key] = (file_contents, file_obj.filename)
    return files_map

# 2. Convert to CSV if needed
def convert_files_to_csv(files_map: Dict[str, tuple]) -> Dict[str, tuple]:
    for file_key, (content, filename) in files_map.items():
        if filename.endswith('.xlsx'):
            df = pd.read_excel(io.BytesIO(content))
            csv_content = df.to_csv(index=False).encode('utf-8')
            files_map[file_key] = (csv_content, filename.replace('.xlsx', '.csv'))
    return files_map
```

### Commented Out Persistence

```python
# NOTE: Currently commented out in routes.py
# _ = await persist_analysis_inputs(
#     user_id=current_user.id,
#     analysis_id=analysis_id,
#     primary=primary,
#     baseline=baseline,
#     parameters_json=parameters_json,
# )
```

The system **has infrastructure** for file persistence but it's not active.

---

## Downloads System

### Purpose

Generate downloadable reports (Excel, JSON) from analysis results.

### Output Format

```python
{
    "download_id": "profile_excel_report",
    "file_name": "data_profile_report_20241219_103000.xlsx",
    "type": "report",
    "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "content_base64": "UEsDBBQAAAAIAAAh..."  # Base64 encoded file
}
```

### Problem: Base64 in Response

- Large reports become **huge JSON responses**
- 100MB Excel file = 133MB base64 = massive response payload
- Network timeout risks
- Frontend memory pressure

---

## Billing Integration

### Credit Consumption Flow

```python
class BillingContext:
    def consume_credits_for_agent(self, agent_id, tool_id, analysis_id, start_time):
        try:
            self.wallet_service.consume_for_agent(
                user_id=self.current_user.id,
                agent_id=agent_id,
                tool_id=tool_id,
                analysis_id=analysis_id
            )
            return None  # Success
        except InsufficientCreditsError as e:
            return {
                "status": "error",
                "error_code": "BILLING_INSUFFICIENT_CREDITS",
                "error": e.detail,
                ...
            }
```

### Key Points

- Credits are **debited BEFORE** agent execution
- Partial execution possible (some agents run before credit exhaustion)
- `CreditTransaction` records `agent_id`, `tool_id`, `analysis_id`

---

## Current Pain Points

### 1. Scalability Issues

```
Problem: Synchronous Processing
─────────────────────────────────
User A uploads → Backend busy → User B waits
User B uploads → Backend busy → User C waits
...
Result: Sequential processing, poor UX at scale
```

### 2. Memory Pressure

```
Problem: In-Memory File Processing
──────────────────────────────────
100MB CSV uploaded
  → 100MB in memory (raw bytes)
  → 300MB in memory (DataFrame)
  → 100MB for cleaned copy
  → 500+ MB total per request!

10 concurrent users = 5GB RAM needed
```

### 3. No Persistence

```
Problem: Ephemeral Processing
─────────────────────────────
- User disconnects → Results lost
- Browser closes → Results lost
- Network timeout → Results lost
- No history of past analyses
- No resume capability
```

### 4. Large Response Payloads

```
Problem: Base64 Downloads in Response
─────────────────────────────────────
Analysis produces:
  - 50MB Excel report
  - 30MB JSON report
  - 20MB cleaned CSV

Base64 overhead: 33%
Total response: ~130MB JSON!
```

### 5. No Status Tracking

```
Problem: All or Nothing
───────────────────────
- No progress indication
- No partial results on failure
- No way to check status
- User must wait for entire pipeline
```

---

## What Needs to Change

### Migration Requirements

| Current                   | V2.1 Target                             |
| ------------------------- | --------------------------------------- |
| Files uploaded to backend | Files uploaded directly to Backblaze B2 |
| Parameters in database    | Parameters uploaded to B2               |
| In-memory processing      | Streamed processing from S3             |
| Synchronous execution     | Async task queue (future)               |
| No persistence            | Full task persistence                   |
| Base64 downloads          | Presigned download URLs                 |
| No status tracking        | Complete status lifecycle               |
| Single response           | Polling for status/results              |

### New Components Needed

1. **Task Model** - Simplified track analysis lifecycle
2. **S3 Service** - Backblaze B2 integration
3. **Upload Flow** - Presigned URLs for files AND parameters
4. **Status API** - Polling endpoint
5. **Download API** - Presigned download URLs

### Files to Modify

| File                          | Changes                             |
| ----------------------------- | ----------------------------------- |
| `db/models.py`                | Add simplified Task model           |
| `api/routes.py`               | New task endpoints, modify /analyze |
| `transformers/*.py`           | Read files & parameters from S3     |
| `downloads/*.py`              | Write to S3, return URLs not base64 |
| New: `services/s3_service.py` | Backblaze B2 client                 |

---

## Next Steps

See the following documents:

1. [02_V2_ARCHITECTURE_PLAN.md](02_V2_ARCHITECTURE_PLAN.md) - New architecture design
2. [03_TASK_LIFECYCLE.md](03_TASK_LIFECYCLE.md) - Task status system
3. [04_V2_API_SPECIFICATION.md](04_V2_API_SPECIFICATION.md) - New API endpoints
4. [05_DATABASE_SCHEMA_V2.md](05_DATABASE_SCHEMA_V2.md) - Schema changes

---

**Document Status:** Complete  
**Last Updated:** December 19, 2025  
**Version:** 2.1
