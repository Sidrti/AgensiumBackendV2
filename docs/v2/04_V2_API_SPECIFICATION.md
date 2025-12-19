# V2 API Specification

**Document Version:** 1.0  
**Created:** December 19, 2025  
**Purpose:** Complete API specification for V2 task-based endpoints

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

V2 endpoints are prefixed with `/v2/` (optional during transition):

```
/tasks           # New task endpoints
/v2/tasks        # Explicit v2 prefix (alternative)
/analyze         # Legacy endpoint (deprecated)
```

### New Endpoints Summary

| Method | Endpoint                       | Purpose                   |
| ------ | ------------------------------ | ------------------------- |
| POST   | `/tasks`                       | Create new task           |
| GET    | `/tasks`                       | List user's tasks         |
| GET    | `/tasks/{task_id}`             | Get task status/results   |
| POST   | `/tasks/{task_id}/upload-urls` | Get presigned upload URLs |
| POST   | `/tasks/{task_id}/process`     | Trigger processing        |
| GET    | `/tasks/{task_id}/downloads`   | Get download URLs         |
| POST   | `/tasks/{task_id}/cancel`      | Cancel task               |
| DELETE | `/tasks/{task_id}`             | Delete task               |

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

Creates a new task and returns task ID.

#### Request

```http
POST /tasks
Content-Type: application/json
Authorization: Bearer <token>

{
    "tool_id": "profile-my-data",
    "agents": ["unified-profiler", "drift-detector", "score-risk"],
    "parameters": {
        "unified-profiler": {
            "null_alert_threshold": 50
        },
        "drift-detector": {
            "significance_level": 0.05
        }
    },
    "files": {
        "primary": {
            "filename": "sales_data.csv",
            "content_type": "text/csv",
            "size_bytes": 52428800
        },
        "baseline": {
            "filename": "baseline_data.csv",
            "content_type": "text/csv",
            "size_bytes": 48000000
        }
    }
}
```

#### Request Fields

| Field                      | Type     | Required | Description                                                           |
| -------------------------- | -------- | -------- | --------------------------------------------------------------------- |
| `tool_id`                  | string   | Yes      | Tool identifier: `profile-my-data`, `clean-my-data`, `master-my-data` |
| `agents`                   | string[] | No       | Agent IDs to run (defaults to tool's available_agents)                |
| `parameters`               | object   | No       | Agent-specific parameters (keyed by agent_id)                         |
| `files`                    | object   | Yes      | File metadata for expected uploads                                    |
| `files.{key}.filename`     | string   | Yes      | Original filename                                                     |
| `files.{key}.content_type` | string   | No       | MIME type (default: text/csv)                                         |
| `files.{key}.size_bytes`   | int      | No       | Expected file size                                                    |

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

Generates presigned URLs for direct upload to Backblaze B2.

#### Request

```http
POST /tasks/550e8400-e29b-41d4-a716-446655440000/upload-urls
Authorization: Bearer <token>
```

No body required - uses file info from task creation.

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

// Upload all files
for (const [fileKey, uploadInfo] of Object.entries(uploads)) {
  const file = files[fileKey];
  await uploadFile(uploadInfo, file);
}
```

---

### 3. Trigger Processing

**POST /tasks/{task_id}/process**

Verifies files are uploaded and starts processing.

#### Request

```http
POST /tasks/550e8400-e29b-41d4-a716-446655440000/process
Authorization: Bearer <token>
```

No body required.

#### Response (Success)

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "PROCESSING",
    "message": "Files verified. Analysis started.",
    "files_verified": {
        "primary": {
            "key": "users/123/tasks/550e8400.../inputs/sales_data.csv",
            "size_bytes": 52428800,
            "verified_at": "2024-12-19T10:32:00Z"
        },
        "baseline": {
            "key": "users/123/tasks/550e8400.../inputs/baseline_data.csv",
            "size_bytes": 48000000,
            "verified_at": "2024-12-19T10:32:00Z"
        }
    }
}
```

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
        "agents_completed": 3,
        "agents_status": {
            "unified-profiler": "completed",
            "drift-detector": "completed",
            "score-risk": "running",
            "governance-checker": "pending",
            "test-coverage-agent": "pending",
            "readiness-rater": "pending"
        }
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
    "result_summary": {
        "total_alerts": 12,
        "total_issues": 45,
        "total_recommendations": 8,
        "readiness_score": 78,
        "risk_level": "medium"
    },
    "report": {
        "alerts": [...],
        "issues": [...],
        "recommendations": [...],
        "executiveSummary": [...],
        "analysisSummary": {...},
        "unified-profiler": {...},
        "drift-detector": {...},
        "score-risk": {...},
        // ... all agent results
    },
    "downloads_available": true
}
```

#### Response (Failed)

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "FAILED",
    "tool_id": "profile-my-data",
    "error_code": "BILLING_INSUFFICIENT_CREDITS",
    "error_message": "Insufficient credits for agent: score-risk. Required: 50, Available: 10",
    "failed_agent": "score-risk",
    "created_at": "2024-12-19T10:30:00Z",
    "failed_at": "2024-12-19T10:32:15Z",
    "partial_results": {
        "unified-profiler": {...},
        "drift-detector": {...}
    },
    "agents_completed": ["unified-profiler", "drift-detector"]
}
```

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

---

### 6. List Tasks

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
            "completed_at": "2024-12-19T10:30:45Z",
            "result_summary": {
                "total_alerts": 12,
                "readiness_score": 78
            }
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
    "cancelled_at": "2024-12-19T10:33:00Z",
    "partial_results": {
        "unified-profiler": {...}
    },
    "agents_completed": ["unified-profiler"]
}
```

---

### 8. Delete Task

**DELETE /tasks/{task_id}**

Deletes a task and its associated files.

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
    "files_deleted": [
        "users/123/tasks/550e8400.../inputs/sales_data.csv",
        "users/123/tasks/550e8400.../outputs/data_profile_report.xlsx"
    ]
}
```

---

## Request/Response Schemas

### Task Creation Request

```python
# Pydantic schema
class FileMetadata(BaseModel):
    filename: str
    content_type: str = "text/csv"
    size_bytes: Optional[int] = None

class TaskCreateRequest(BaseModel):
    tool_id: str = Field(..., description="Tool identifier")
    agents: Optional[List[str]] = Field(None, description="Agent IDs to run")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Agent parameters")
    files: Dict[str, FileMetadata] = Field(..., description="Expected file uploads")

    @validator('tool_id')
    def validate_tool_id(cls, v):
        valid_tools = ['profile-my-data', 'clean-my-data', 'master-my-data']
        if v not in valid_tools:
            raise ValueError(f"Invalid tool_id. Must be one of: {valid_tools}")
        return v
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

    # Results (when completed)
    result_summary: Optional[Dict[str, Any]] = None
    report: Optional[Dict[str, Any]] = None
    downloads_available: bool = False

    # Error info (when failed)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    failed_agent: Optional[str] = None
    partial_results: Optional[Dict[str, Any]] = None
```

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

### V2 Migration Path

```http
# Step 1: Create task
POST /tasks
{"tool_id": "profile-my-data", "files": {"primary": {...}}}
→ {"task_id": "abc123", "status": "CREATED"}

# Step 2: Get upload URLs
POST /tasks/abc123/upload-urls
→ {"uploads": {"primary": {"url": "https://..."}}}

# Step 3: Upload to B2
PUT https://s3.us-east-005.backblazeb2.com/...
→ 200 OK

# Step 4: Trigger processing
POST /tasks/abc123/process
→ {"status": "PROCESSING"}

# Step 5: Poll for completion
GET /tasks/abc123
→ {"status": "COMPLETED", "report": {...}}

# Step 6: Get download URLs
GET /tasks/abc123/downloads
→ {"downloads": [{"url": "https://..."}]}
```

### Deprecation Timeline

| Phase       | Timeline      | Action                        |
| ----------- | ------------- | ----------------------------- |
| **Now**     | December 2024 | V2 endpoints available        |
| **Phase 1** | January 2025  | Add deprecation warning to V1 |
| **Phase 2** | March 2025    | V1 returns deprecation header |
| **Phase 3** | June 2025     | V1 disabled                   |

---

**Document Status:** Complete  
**Last Updated:** December 19, 2025
