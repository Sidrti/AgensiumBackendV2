# V2.1 API Specification

**Document Version:** 2.1.1  
**Created:** December 19, 2025  
**Updated:** December 20, 2025  
**Purpose:** Complete API specification for V2.1 task-based endpoints with simplified model

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Task Endpoints](#task-endpoints)
4. [Request/Response Schemas](#requestresponse-schemas)
5. [Error Responses](#error-responses)
6. [Migration from V1](#migration-from-v1)

---

## Overview

### Base URL

```
Production: https://api.agensium.com
Development: http://localhost:8000
```

### API Versioning

V2.1 endpoints use the `/tasks` prefix:

```
/tasks           # New task endpoints
/analyze         # Legacy endpoint (deprecated)
```

### New Endpoints Summary

| Method | Endpoint                       | Purpose                             |
| ------ | ------------------------------ | ----------------------------------- |
| POST   | `/tasks`                       | Create new task                     |
| GET    | `/tasks`                       | List user's tasks                   |
| GET    | `/tasks/{task_id}`             | Get task status/results             |
| POST   | `/tasks/{task_id}/upload-urls` | Get presigned URLs (files + params) |
| POST   | `/tasks/{task_id}/process`     | Trigger processing                  |
| GET    | `/tasks/{task_id}/downloads`   | Get download URLs                   |
| GET    | `/tasks/{task_id}/report`      | Get complete analysis report        |
| POST   | `/tasks/{task_id}/cancel`      | Cancel task                         |
| DELETE | `/tasks/{task_id}`             | Delete task                         |

---

## Authentication

All endpoints require JWT authentication:

```http
Authorization: Bearer <jwt_token>
```

Uses existing auth system from `auth/dependencies.py`:

```python
current_user: models.User = Depends(get_current_active_verified_user)
```

---

## Task Endpoints

### 1. Create Task

**POST /tasks**

Creates a new task and returns task ID. Parameters are NOT included in this request.

#### Request

```http
POST /tasks
Content-Type: application/json
Authorization: Bearer <token>

{
    "tool_id": "profile-my-data",
    "agents": ["unified-profiler", "drift-detector", "score-risk"]
}
```

#### Request Fields

| Field     | Type     | Required | Description                                                           |
| --------- | -------- | -------- | --------------------------------------------------------------------- |
| `tool_id` | string   | Yes      | Tool identifier: `profile-my-data`, `clean-my-data`, `master-my-data` |
| `agents`  | string[] | No       | Agent IDs to run (defaults to tool's available_agents)                |

**Note:** Parameters are NOT sent in this request. They will be uploaded to B2 separately.

#### Response

```http
HTTP/1.1 201 Created
Content-Type: application/json

{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "CREATED",
    "tool_id": "profile-my-data",
    "agents": ["unified-profiler", "drift-detector", "score-risk"],
    "created_at": "2024-12-19T10:30:00Z",
    "message": "Task created. Request upload URLs to proceed."
}
```

---

### 2. Get Upload URLs

**POST /tasks/{task_id}/upload-urls**

Generates presigned URLs for direct upload to Backblaze B2, including files AND parameters.json.

#### Request

```http
POST /tasks/550e8400-e29b-41d4-a716-446655440000/upload-urls
Content-Type: application/json
Authorization: Bearer <token>

{
    "files": {
        "primary": {
            "filename": "sales_data.csv",
            "content_type": "text/csv"
        },
        "baseline": {
            "filename": "baseline_data.csv",
            "content_type": "text/csv"
        }
    },
    "has_parameters": true
}
```

#### Request Fields

| Field                      | Type    | Required | Description                        |
| -------------------------- | ------- | -------- | ---------------------------------- |
| `files`                    | object  | Yes      | File metadata for expected uploads |
| `files.{key}.filename`     | string  | Yes      | Original filename                  |
| `files.{key}.content_type` | string  | No       | MIME type (default: text/csv)      |
| `has_parameters`           | boolean | No       | Whether to generate parameters URL |

#### Response

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "UPLOADING",
    "uploads": {
        "primary": {
            "url": "https://s3.us-east-005.backblazeb2.com/agensium-files/users/123/tasks/550e8400.../inputs/sales_data.csv?X-Amz-Algorithm=...",
            "key": "users/123/tasks/550e8400-e29b-41d4-a716-446655440000/inputs/sales_data.csv",
            "method": "PUT",
            "headers": {
                "Content-Type": "text/csv"
            },
            "expires_at": "2024-12-19T10:45:00Z"
        },
        "baseline": {
            "url": "https://s3.us-east-005.backblazeb2.com/agensium-files/users/123/tasks/550e8400.../inputs/baseline_data.csv?X-Amz-Algorithm=...",
            "key": "users/123/tasks/550e8400-e29b-41d4-a716-446655440000/inputs/baseline_data.csv",
            "method": "PUT",
            "headers": {
                "Content-Type": "text/csv"
            },
            "expires_at": "2024-12-19T10:45:00Z"
        },
        "parameters": {
            "url": "https://s3.us-east-005.backblazeb2.com/agensium-files/users/123/tasks/550e8400.../inputs/parameters.json?X-Amz-Algorithm=...",
            "key": "users/123/tasks/550e8400-e29b-41d4-a716-446655440000/inputs/parameters.json",
            "method": "PUT",
            "headers": {
                "Content-Type": "application/json"
            },
            "expires_at": "2024-12-19T10:45:00Z"
        }
    },
    "expires_in_seconds": 900,
    "message": "Upload files directly to the provided URLs using PUT method."
}
```

#### Frontend Upload Example

```typescript
// Upload each file directly to B2
async function uploadFile(uploadInfo: UploadInfo, file: File): Promise<void> {
  const response = await fetch(uploadInfo.url, {
    method: "PUT",
    headers: uploadInfo.headers,
    body: file,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.status}`);
  }
}

// Upload parameters as JSON
async function uploadParameters(
  uploadInfo: UploadInfo,
  params: object
): Promise<void> {
  const response = await fetch(uploadInfo.url, {
    method: "PUT",
    headers: uploadInfo.headers,
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    throw new Error(`Parameter upload failed: ${response.status}`);
  }
}

// Upload all
await uploadFile(uploads.primary, primaryFile);
if (baselineFile) await uploadFile(uploads.baseline, baselineFile);
if (parameters && uploads.parameters) {
  await uploadParameters(uploads.parameters, parameters);
}
```

---

### 3. Trigger Processing

**POST /tasks/{task_id}/process**

Verifies files are uploaded and starts processing **in the background**.

**V2.1.1 Change:** This endpoint now returns **immediately** after triggering. Processing continues in a background thread on the server. Frontend should navigate user to Tasks List page to track progress.

#### Request

```http
POST /tasks/550e8400-e29b-41d4-a716-446655440000/process
Authorization: Bearer <token>
```

No body required.

#### Response (Immediate - Processing Started)

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "PROCESSING",
    "tool_id": "profile-my-data",
    "agents": ["unified-profiler", "score-risk"],
    "progress": 15,
    "created_at": "2024-12-19T10:30:00Z",
    "processing_started_at": "2024-12-19T10:32:00Z",
    "downloads_available": false,
    "message": "Processing started. Track progress from the Tasks page."
}
```

**Note:** Unlike the previous synchronous model, this response is returned **immediately**. The actual processing happens in the background. Use `GET /tasks/{id}` to check status, or navigate to the Tasks List page.

#### Response (Files Missing)

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "UPLOAD_FAILED",
    "error_code": "FILES_NOT_FOUND",
    "error": "Required files not found in storage",
    "missing_files": ["primary"],
    "message": "Please request new upload URLs and try again."
}
```

#### Backend Processing Flow

```
1. Verify required files exist in S3
2. Set task status to PROCESSING
3. Start background thread for agent execution
4. Return immediately (status: PROCESSING)

Background thread:
5. Execute agents sequentially
6. Upload outputs to S3
7. Update task status to COMPLETED or FAILED
```

---

### 4. Get Task Status

**GET /tasks/{task_id}**

Returns current task status, progress, and results (if complete).

#### Request

```http
GET /tasks/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer <token>
```

#### Response (Processing)

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "PROCESSING",
    "tool_id": "profile-my-data",
    "progress": 55,
    "progress_detail": {
        "current_agent": "score-risk",
        "agents_total": 6,
        "agents_completed": 3
    },
    "created_at": "2024-12-19T10:30:00Z",
    "processing_started_at": "2024-12-19T10:32:00Z"
}
```

#### Response (Completed)

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "COMPLETED",
    "tool_id": "profile-my-data",
    "progress": 100,
    "execution_time_ms": 45230,
    "created_at": "2024-12-19T10:30:00Z",
    "completed_at": "2024-12-19T10:30:45Z",
    "downloads_available": true,
    "message": "Analysis completed. Use /downloads endpoint to get file URLs."
}
```

**Note:** Full results are NOT returned in this response. Use `/downloads` endpoint to get output files.

#### Response (Failed)

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "FAILED",
    "tool_id": "profile-my-data",
    "error_code": "BILLING_INSUFFICIENT_CREDITS",
    "error_message": "Insufficient credits for agent execution. Required: 150, Available: 50",
    "context": {
        "available": 50,
        "required": 150,
        "shortfall": 100,
        "breakdown": {
            "unified-profiler": 50,
            "drift-detector": 50,
            "score-risk": 50
        }
    },
    "created_at": "2024-12-19T10:30:00Z",
    "failed_at": "2024-12-19T10:32:15Z"
}
```

**Note:** Billing is checked **upfront** for ALL agents before any execution begins. If the user doesn't have enough credits for all selected agents, the task fails immediately - no partial execution occurs.

---

### 5. Get Download URLs

**GET /tasks/{task_id}/downloads**

Returns presigned download URLs for all output files.

#### Request

```http
GET /tasks/550e8400-e29b-41d4-a716-446655440000/downloads
Authorization: Bearer <token>
```

#### Response

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "downloads": [
        {
            "download_id": "excel_report",
            "filename": "data_profile_report_20241219_103045.xlsx",
            "type": "report",
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "size_bytes": 2048576,
            "url": "https://s3.us-east-005.backblazeb2.com/agensium-files/users/123/tasks/550e8400.../outputs/data_profile_report.xlsx?X-Amz-Algorithm=...",
            "expires_at": "2024-12-19T11:30:00Z"
        },
        {
            "download_id": "json_report",
            "filename": "data_profile_report_20241219_103045.json",
            "type": "report",
            "mime_type": "application/json",
            "size_bytes": 1536000,
            "url": "https://s3.us-east-005.backblazeb2.com/agensium-files/users/123/tasks/550e8400.../outputs/data_profile_report.json?X-Amz-Algorithm=...",
            "expires_at": "2024-12-19T11:30:00Z"
        }
    ],
    "expires_in_seconds": 3600
}
```

**Note:** No base64 content in response - only presigned URLs for direct download.

---

### 9. Get Task Report

**GET /tasks/{task_id}/report**

Returns the complete analysis report for a completed task. This includes all analysis results, recommendations, and visualizations data formatted for the frontend results pages.

#### Request

```http
GET /tasks/550e8400-e29b-41d4-a716-446655440000/report
Authorization: Bearer <token>
```

#### Response

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
    "tool": "profile-my-data",
    "status": "success",
    "timestamp": "2024-12-19T10:30:45Z",
    "execution_time_ms": 45230,
    "report": {
        "executiveSummary": {...},
        "analysisSummary": {...},
        "rowLevelIssues": [...],
        "issueSummary": {...},
        "routingDecisions": [...],
        "downloads": [
            {
                "filename": "profile_report.json",
                "url": "https://...",
                "type": "report"
            }
        ],
        "agentResults": {
            "unified-profiler": {...},
            "score-risk": {...}
        }
    }
}
```

#### Response Fields

| Field               | Type   | Description                                  |
| ------------------- | ------ | -------------------------------------------- |
| `analysis_id`       | string | Same as task_id                              |
| `tool`              | string | Tool identifier                              |
| `status`            | string | "success" or "error"                         |
| `timestamp`         | string | Completion timestamp (ISO 8601)              |
| `execution_time_ms` | number | Total execution time                         |
| `report`            | object | Complete report data for frontend components |

#### Report Object Fields

| Field              | Type   | Description                             |
| ------------------ | ------ | --------------------------------------- |
| `executiveSummary` | object | High-level summary for executives       |
| `analysisSummary`  | object | Detailed analysis summary               |
| `rowLevelIssues`   | array  | Row-level data issues found             |
| `issueSummary`     | object | Aggregated issue statistics             |
| `routingDecisions` | array  | Agent routing decisions made            |
| `downloads`        | array  | Available downloads with presigned URLs |
| `agentResults`     | object | Results from each agent, keyed by ID    |

#### Errors

| Code | Error            | Description                  |
| ---- | ---------------- | ---------------------------- |
| 400  | Not completed    | Task not in COMPLETED status |
| 404  | Not found        | Task doesn't exist           |
| 404  | Report not found | No JSON report in S3         |

---

### 10. List Tasks

**GET /tasks**

Lists user's tasks with pagination and filtering.

#### Request

```http
GET /tasks?status=COMPLETED&tool_id=profile-my-data&limit=20&offset=0
Authorization: Bearer <token>
```

#### Query Parameters

| Parameter | Type   | Default         | Description         |
| --------- | ------ | --------------- | ------------------- |
| `status`  | string | -               | Filter by status    |
| `tool_id` | string | -               | Filter by tool      |
| `limit`   | int    | 20              | Max results (1-100) |
| `offset`  | int    | 0               | Pagination offset   |
| `sort`    | string | created_at:desc | Sort order          |

#### Response

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "tasks": [
        {
            "task_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "COMPLETED",
            "tool_id": "profile-my-data",
            "progress": 100,
            "created_at": "2024-12-19T10:30:00Z",
            "completed_at": "2024-12-19T10:30:45Z"
        },
        {
            "task_id": "660e8400-e29b-41d4-a716-446655440001",
            "status": "PROCESSING",
            "tool_id": "clean-my-data",
            "progress": 45,
            "created_at": "2024-12-19T10:35:00Z"
        }
    ],
    "pagination": {
        "total": 42,
        "limit": 20,
        "offset": 0,
        "has_more": true
    }
}
```

---

### 7. Cancel Task

**POST /tasks/{task_id}/cancel**

Cancels a task in progress.

#### Request

```http
POST /tasks/550e8400-e29b-41d4-a716-446655440000/cancel
Authorization: Bearer <token>
```

#### Response

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "CANCELLED",
    "message": "Task cancelled successfully",
    "cancelled_at": "2024-12-19T10:33:00Z"
}
```

---

### 8. Delete Task

**DELETE /tasks/{task_id}**

Deletes a task and its associated files from S3.

#### Request

```http
DELETE /tasks/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer <token>
```

#### Response

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "Task and associated files deleted",
    "files_deleted": 5
}
```

---

## Request/Response Schemas

### Task Creation Request

```python
# Pydantic schema
class TaskCreateRequest(BaseModel):
    tool_id: str = Field(..., description="Tool identifier")
    agents: Optional[List[str]] = Field(None, description="Agent IDs to run")

    @validator('tool_id')
    def validate_tool_id(cls, v):
        valid_tools = ['profile-my-data', 'clean-my-data', 'master-my-data']
        if v not in valid_tools:
            raise ValueError(f"Invalid tool_id. Must be one of: {valid_tools}")
        return v
```

**Note:** Parameters are NOT in this schema - they're uploaded separately to B2.

### Upload URLs Request

```python
class FileMetadata(BaseModel):
    """File metadata for upload URL generation."""
    filename: str
    content_type: str = "text/csv"

class UploadUrlsRequest(BaseModel):
    """Request schema for getting upload URLs."""
    files: Dict[str, FileMetadata] = Field(..., description="Files to upload")
    has_parameters: bool = Field(False, description="Whether to include parameters URL")
```

### Task Response

```python
class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    tool_id: str
    agents: List[str]
    progress: int = 0
    progress_detail: Optional[Dict[str, Any]] = None

    # Timestamps
    created_at: datetime
    upload_started_at: Optional[datetime] = None
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None

    # Results
    downloads_available: bool = False

    # Error info (when failed)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
```

**Note:** No `result_summary` or `result_full` fields - results are in S3 only.

---

## Error Responses

### Standard Error Format

```json
{
  "detail": "Human-readable error message",
  "error_code": "SPECIFIC_ERROR_CODE",
  "context": {
    "field": "additional context"
  }
}
```

### Error Codes

| Code                           | HTTP Status | Description                               |
| ------------------------------ | ----------- | ----------------------------------------- |
| `TASK_NOT_FOUND`               | 404         | Task ID does not exist                    |
| `TASK_UNAUTHORIZED`            | 403         | User does not own this task               |
| `INVALID_TOOL_ID`              | 400         | Tool ID not recognized                    |
| `INVALID_STATUS_TRANSITION`    | 400         | Invalid status transition requested       |
| `FILES_NOT_FOUND`              | 400         | Required files not in S3                  |
| `UPLOAD_URLS_EXPIRED`          | 400         | Upload URLs have expired                  |
| `TASK_ALREADY_PROCESSING`      | 400         | Task is already being processed           |
| `TASK_NOT_CANCELLABLE`         | 400         | Task cannot be cancelled (terminal state) |
| `BILLING_INSUFFICIENT_CREDITS` | 402         | Not enough credits                        |
| `BILLING_WALLET_NOT_FOUND`     | 402         | User wallet not found                     |
| `INTERNAL_ERROR`               | 500         | Internal server error                     |

---

## Migration from V1

### V1 Endpoint (Deprecated)

```http
# Old way - still works but deprecated
POST /analyze
Content-Type: multipart/form-data

tool_id=profile-my-data
agents=unified-profiler,score-risk
parameters_json={"unified-profiler": {...}}
primary=<file>
baseline=<file>

# Returns entire result in single response (can be 100MB+)
```

### V2.1 Migration Path

```http
# Step 1: Create task (NO parameters here)
POST /tasks
{"tool_id": "profile-my-data", "agents": ["unified-profiler"]}
→ {"task_id": "abc123", "status": "CREATED"}

# Step 2: Get upload URLs (including parameters)
POST /tasks/abc123/upload-urls
{"files": {"primary": {...}}, "has_parameters": true}
→ {"uploads": {"primary": {...}, "parameters": {...}}}

# Step 3: Upload files to B2
PUT https://s3.../primary.csv
→ 200 OK

# Step 4: Upload parameters to B2
PUT https://s3.../parameters.json
Body: {"unified-profiler": {...}}
→ 200 OK

# Step 5: Trigger processing (RETURNS IMMEDIATELY in V2.1.1)
POST /tasks/abc123/process
→ {"status": "PROCESSING", "message": "Processing started..."}

# Step 6: Navigate to Tasks List page (no polling required during creation)
# User tracks progress from Tasks List page

# Step 7: Later, check task status or get downloads
GET /tasks/abc123
→ {"status": "COMPLETED", "downloads_available": true}

GET /tasks/abc123/downloads
→ {"downloads": [{"url": "https://..."}]}
```

### Key Differences

| Aspect           | V1                    | V2.1.1                    |
| ---------------- | --------------------- | ------------------------- |
| Parameters       | In request body       | Uploaded to B2 separately |
| File Upload      | To backend            | Direct to B2              |
| Results          | In response (base64)  | Presigned URLs only       |
| Database Storage | Parameters in DB      | Nothing stored in DB      |
| File Metadata    | Stored in task record | Derived from S3 path      |
| Processing       | Synchronous           | Async (background thread) |
| Frontend Waiting | Polls until complete  | Redirects immediately     |

### Deprecation Timeline

| Phase       | Timeline      | Action                        |
| ----------- | ------------- | ----------------------------- |
| **Now**     | December 2024 | V2.1 endpoints available      |
| **Phase 1** | January 2025  | Add deprecation warning to V1 |
| **Phase 2** | March 2025    | V1 returns deprecation header |
| **Phase 3** | June 2025     | V1 disabled                   |

---

**Document Status:** Complete  
**Last Updated:** December 20, 2025  
**Version:** 2.1.1
