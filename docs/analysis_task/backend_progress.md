# Task-Based Architecture - Implementation Progress & Technical Documentation

**Started:** December 19, 2025  
**Last Updated:** December 20, 2025  
**Status:** ✅ Core Implementation Complete (V2.1.1 Async Processing)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [V2.1.1 Async Processing](#v211-async-processing)
4. [Implementation Phases](#implementation-phases)
5. [Files Created](#files-created)
6. [Files Modified](#files-modified)
7. [Database Changes](#database-changes)
8. [API Endpoints](#api-endpoints)
9. [S3 File Structure](#s3-file-structure)
10. [Code Documentation](#code-documentation)
11. [Testing Checklist](#testing-checklist)
12. [Change Log](#change-log)

---

## Overview

### What is the Task-Based Architecture?

The task-based architecture decouples file uploads from processing, enabling:

- **Resumable uploads**: Files are uploaded directly to Backblaze B2
- **Persistent storage**: Files survive server restarts
- **Task tracking**: Real-time progress monitoring
- **Scalable downloads**: Presigned URLs instead of base64 in responses
- **Async processing**: Backend returns immediately, processes in background (V2.1.1)

### Key Design Decisions

| Decision             | Choice             | Rationale                                           |
| -------------------- | ------------------ | --------------------------------------------------- |
| Queue System         | **SKIPPED**        | Simplicity first - processing happens via threading |
| Processing Model     | **Async (Thread)** | Prevents HTTP timeouts, immediate response          |
| Task Model Fields    | **18 fields**      | Simplified model for core functionality             |
| Parameters Storage   | **S3 only**        | No database storage, uploaded as `parameters.json`  |
| Results Storage      | **S3 only**        | Outputs stored in S3, returned as presigned URLs    |
| Upload URLs Expiry   | **15 minutes**     | Reasonable time for large file uploads              |
| Download URLs Expiry | **1 hour**         | Enough time to download all files                   |

### Status Flow

```
┌─────────┐    ┌───────────┐    ┌────────────┐    ┌───────────┐
│ CREATED │ => │ UPLOADING │ => │ PROCESSING │ => │ COMPLETED │
└─────────┘    └─────┬─────┘    └─────┬──────┘    └───────────┘
                     │                │
                     v                v
              ┌──────────────┐  ┌──────────┐
              │ UPLOAD_FAILED│  │  FAILED  │
              └──────────────┘  └──────────┘
```

**Note:** QUEUED status is available but skipped in current implementation. After triggering processing, we go directly to PROCESSING. The processing happens in a background thread (V2.1.1).

---

## Architecture

### Flow (V2.1.1 - Async Model)

```
Frontend → POST /tasks (create task)
        → POST /tasks/{id}/upload-urls (get presigned URLs)
        → PUT files directly to Backblaze B2
        → POST /tasks/{id}/process (trigger - returns IMMEDIATELY!)
        → Navigate to /tasks page
        → Poll GET /tasks from Tasks List page
        → GET /tasks/{id}/downloads (when COMPLETED)
        → Download files from presigned URLs
```

### Benefits

1. **No request timeout issues** - Trigger returns immediately, processing in background
2. **Resumable** - If upload fails, can retry with new URLs
3. **Progress tracking** - Real-time updates during processing (from Tasks List)
4. **Scalable** - Files stored in object storage, not memory
5. **Cost efficient** - Results stored once, downloaded on-demand
6. **Better UX** - User isn't blocked waiting for processing

---

## V2.1.1 Async Processing

### Overview

In V2.1.1, the `POST /tasks/{task_id}/process` endpoint returns **immediately** after starting background processing. This eliminates HTTP timeout issues and provides better user experience.

### Implementation Details

**File:** `api/task_routes.py`

```python
import threading
import asyncio
from sqlalchemy.orm import sessionmaker

def _execute_task_background(task_id: str, user_id: int):
    """Execute task in background thread with its own DB session."""
    # Create new DB session for this thread
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # Run the async execution in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Execute the task
        result = loop.run_until_complete(_execute_task(task_id, user_id, db))

    finally:
        db.close()
        loop.close()

@router.post("/{task_id}/process")
async def trigger_processing(task_id: str, ...):
    # ... validation ...

    # Start background processing
    thread = threading.Thread(
        target=_execute_task_background,
        args=(task_id, current_user.id),
        daemon=True
    )
    thread.start()

    # Return immediately
    return schemas.TaskResponse(
        task_id=task.task_id,
        status=task.status,
        message="Processing started. Track progress from the Tasks page.",
        # ...
    )
```

### Key Points

1. **Background Thread**: Uses `threading.Thread` with `daemon=True`
2. **Separate DB Session**: Each thread gets its own `SessionLocal()` instance
3. **Own Event Loop**: Background thread creates new `asyncio` event loop
4. **Immediate Response**: Frontend receives response while processing continues
5. **Thread Safety**: No shared state between request thread and background thread

### Response Format

```json
{
  "task_id": "550e8400-...",
  "status": "PROCESSING",
  "message": "Processing started. Track progress from the Tasks page.",
  "tool_id": "profile-my-data",
  "agents": ["unified-profiler", "score-risk"],
  "progress": 0,
  "created_at": "2025-12-20T10:00:00Z",
  "processing_started_at": "2025-12-20T10:01:00Z"
}
```

---

## Implementation Phases

### Phase 1: Infrastructure ✅ COMPLETED

| Task                        | File                     | Status     |
| --------------------------- | ------------------------ | ---------- |
| Create services directory   | `services/`              | ✅ Created |
| Create services init        | `services/__init__.py`   | ✅ Created |
| Create S3 service           | `services/s3_service.py` | ✅ Created |
| Add TaskStatus enum         | `db/models.py`           | ✅ Added   |
| Add Task model              | `db/models.py`           | ✅ Added   |
| Add User.tasks relationship | `db/models.py`           | ✅ Added   |

### Phase 2: Task API ✅ COMPLETED

| Task                         | Endpoint             | Status     |
| ---------------------------- | -------------------- | ---------- |
| Create task routes file      | `api/task_routes.py` | ✅ Created |
| POST /tasks                  | Create task          | ✅ Done    |
| POST /tasks/{id}/upload-urls | Get presigned URLs   | ✅ Done    |
| POST /tasks/{id}/process     | Trigger processing   | ✅ Done    |
| GET /tasks/{id}              | Get task status      | ✅ Done    |
| GET /tasks/{id}/downloads    | Get download URLs    | ✅ Done    |
| GET /tasks/{id}/report       | Get complete report  | ✅ Done    |
| GET /tasks                   | List tasks           | ✅ Done    |
| POST /tasks/{id}/cancel      | Cancel task          | ✅ Done    |
| DELETE /tasks/{id}           | Delete task          | ✅ Done    |
| Register routes              | `main.py`            | ✅ Done    |

### Phase 3: Task Schemas ✅ COMPLETED

| Schema               | Purpose              | Status   |
| -------------------- | -------------------- | -------- |
| `TaskStatusEnum`     | Status enumeration   | ✅ Added |
| `TaskCreateRequest`  | Task creation input  | ✅ Added |
| `TaskCreateResponse` | Task creation output | ✅ Added |
| `FileMetadata`       | File upload metadata | ✅ Added |
| `UploadUrlsRequest`  | Upload URLs input    | ✅ Added |
| `UploadUrlInfo`      | Single upload URL    | ✅ Added |
| `UploadUrlsResponse` | Upload URLs output   | ✅ Added |
| `TaskResponse`       | Task status response | ✅ Added |
| `DownloadInfo`       | Download file info   | ✅ Added |
| `DownloadsResponse`  | Downloads output     | ✅ Added |
| `TaskListItem`       | Task in list         | ✅ Added |
| `PaginationInfo`     | Pagination metadata  | ✅ Added |
| `TaskListResponse`   | List tasks output    | ✅ Added |
| `TaskCancelResponse` | Cancel output        | ✅ Added |
| `TaskDeleteResponse` | Delete output        | ✅ Added |
| `TaskReportResponse` | Report output        | ✅ Added |

### Phase 4: Transformer Updates ✅ COMPLETED

| Transformer | Function Added                   | Status  |
| ----------- | -------------------------------- | ------- |
| Profile     | `run_profile_my_data_analysis()` | ✅ Done |
| Clean       | `run_clean_my_data_analysis()`   | ✅ Done |
| Master      | `run_master_my_data_analysis()`  | ✅ Done |
| All         | `_determine_file_key()`          | ✅ Done |
| All         | `_upload_outputs_to_s3()`        | ✅ Done |

### Phase 5: Database Migration ✅ COMPLETED

| Task                    | Status                                   |
| ----------------------- | ---------------------------------------- |
| Create migration script | ✅ `db/migrations/create_tasks_table.py` |
| Execute migration       | ✅ Tasks table created                   |
| Create indexes          | ✅ 5 indexes + PRIMARY                   |
| Verify structure        | ✅ 18 columns confirmed                  |

### Phase 6: Testing ⏳ PENDING

| Test                  | Status     |
| --------------------- | ---------- |
| Task creation         | ⏳ Pending |
| Upload URL generation | ⏳ Pending |
| File upload to B2     | ⏳ Pending |
| Processing trigger    | ⏳ Pending |
| Status polling        | ⏳ Pending |
| Downloads             | ⏳ Pending |
| End-to-end flow       | ⏳ Pending |

---

## Files Created

### `services/__init__.py`

**Purpose:** Module initialization for services package.

```python
from .s3_service import s3_service, S3Service

__all__ = ["s3_service", "S3Service"]
```

---

### `services/s3_service.py`

**Purpose:** Backblaze B2 S3-compatible storage client.

**Key Features:**

- Singleton pattern for connection reuse
- Presigned URL generation (upload & download)
- File operations (upload, download, delete, list)
- Parameter storage and retrieval
- Task file verification

**Class:** `S3Service`

| Method                            | Purpose                        | Parameters                                                     | Returns                                         |
| --------------------------------- | ------------------------------ | -------------------------------------------------------------- | ----------------------------------------------- |
| `generate_upload_url()`           | Create presigned upload URL    | `user_id`, `task_id`, `filename`, `content_type`, `expires_in` | `Dict[url, key, method, headers, expires_at]`   |
| `generate_parameter_upload_url()` | Create URL for parameters.json | `user_id`, `task_id`, `expires_in`                             | `Dict[url, key, method, headers, expires_at]`   |
| `generate_download_url()`         | Create presigned download URL  | `key`, `expires_in`                                            | `str` (URL)                                     |
| `file_exists()`                   | Check if file exists           | `key`                                                          | `bool`                                          |
| `get_file_info()`                 | Get file metadata              | `key`                                                          | `Dict[size_bytes, content_type, last_modified]` |
| `get_file_bytes()`                | Download file content          | `key`                                                          | `bytes`                                         |
| `get_parameters()`                | Get task parameters            | `user_id`, `task_id`                                           | `Dict` or `None`                                |
| `upload_file()`                   | Upload file content            | `key`, `content`, `content_type`                               | `Dict[key, size_bytes]`                         |
| `upload_json()`                   | Upload JSON data               | `key`, `data`                                                  | `Dict[key, size_bytes]`                         |
| `list_files()`                    | List files with prefix         | `prefix`                                                       | `List[Dict]`                                    |
| `list_input_files()`              | List task inputs               | `user_id`, `task_id`                                           | `List[Dict]`                                    |
| `list_output_files()`             | List task outputs              | `user_id`, `task_id`                                           | `List[Dict]`                                    |
| `delete_file()`                   | Delete single file             | `key`                                                          | `bool`                                          |
| `delete_folder()`                 | Delete files by prefix         | `prefix`                                                       | `int` (count)                                   |
| `delete_task_files()`             | Delete all task files          | `user_id`, `task_id`                                           | `int` (count)                                   |
| `verify_input_files()`            | Verify required files exist    | `user_id`, `task_id`, `required_files`                         | `Dict[verified, found, missing, files]`         |

**Environment Variables Required:**

```
AWS_ENDPOINT_URL=https://s3.us-east-005.backblazeb2.com
AWS_ACCESS_KEY_ID=your_key_id
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-005
S3_BUCKET=agensium-files
```

---

### `api/task_routes.py`

**Purpose:** REST API endpoints for task management.

**Router:** `APIRouter(prefix="/tasks", tags=["tasks"])`

**Endpoints:**

#### `POST /tasks` - Create Task

```python
@router.post("", response_model=schemas.TaskCreateResponse, status_code=201)
async def create_task(request: schemas.TaskCreateRequest, ...)
```

- Creates new task with CREATED status
- Validates tool_id and agents
- Does NOT include parameters or files

#### `POST /tasks/{task_id}/upload-urls` - Get Upload URLs

```python
@router.post("/{task_id}/upload-urls", response_model=schemas.UploadUrlsResponse)
async def get_upload_urls(task_id: str, request: schemas.UploadUrlsRequest, ...)
```

- Generates presigned PUT URLs for file uploads
- Sets task status to UPLOADING
- URLs expire in 15 minutes

#### `POST /tasks/{task_id}/process` - Trigger Processing

```python
@router.post("/{task_id}/process", response_model=schemas.TaskResponse)
async def trigger_processing(task_id: str, ...)
```

- Verifies required files exist in S3
- Sets status to PROCESSING
- Executes analysis synchronously
- Returns COMPLETED or FAILED status

#### `GET /tasks/{task_id}` - Get Task Status

```python
@router.get("/{task_id}", response_model=schemas.TaskResponse)
async def get_task(task_id: str, ...)
```

- Returns current task status and metadata
- Includes progress percentage (0-100)
- Does NOT include full results

#### `GET /tasks/{task_id}/downloads` - Get Download URLs

```python
@router.get("/{task_id}/downloads", response_model=schemas.DownloadsResponse)
async def get_downloads(task_id: str, ...)
```

- Only available for COMPLETED tasks
- Lists output files from S3
- Generates presigned download URLs (1 hour expiry)

#### `GET /tasks` - List Tasks

```python
@router.get("", response_model=schemas.TaskListResponse)
async def list_tasks(status: Optional[str], tool_id: Optional[str], limit: int, offset: int, ...)
```

- Lists user's tasks with pagination
- Optional filtering by status and tool_id

#### `POST /tasks/{task_id}/cancel` - Cancel Task

```python
@router.post("/{task_id}/cancel", response_model=schemas.TaskCancelResponse)
async def cancel_task(task_id: str, ...)
```

- Cancels PROCESSING or QUEUED tasks
- Credits already consumed are NOT refunded

#### `DELETE /tasks/{task_id}` - Delete Task

```python
@router.delete("/{task_id}", response_model=schemas.TaskDeleteResponse)
async def delete_task(task_id: str, ...)
```

- Deletes task and all S3 files
- Returns count of files deleted

---

### `db/migrations/create_tasks_table.py`

**Purpose:** Database migration to create tasks table.

**Run Command:**

```bash
python -m db.migrations.create_tasks_table
```

**Verify Only:**

```bash
python -m db.migrations.create_tasks_table --verify
```

---

## Files Modified

### `db/models.py`

#### Added: `TaskStatus` Enum

```python
class TaskStatus(str, enum.Enum):
    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
```

#### Added: `Task` Model

```python
class Task(Base):
    __tablename__ = "tasks"

    # Primary Key
    task_id = Column(String(36), primary_key=True, index=True)

    # Foreign Key
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Configuration
    tool_id = Column(String(50), nullable=False, index=True)
    agents = Column(JSON, nullable=False)

    # Status
    status = Column(String(20), nullable=False, default=TaskStatus.CREATED.value, index=True)
    progress = Column(Integer, nullable=False, default=0)
    current_agent = Column(String(100), nullable=True)

    # Errors
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    upload_started_at = Column(DateTime, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    expired_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Cleanup
    s3_cleaned = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="tasks")

    # Helper Methods
    def is_terminal(self) -> bool
    def can_process(self) -> bool
    def can_cancel(self) -> bool
    def can_generate_upload_urls(self) -> bool
    def get_s3_prefix(self) -> str
    def get_input_prefix(self) -> str
    def get_output_prefix(self) -> str
```

#### Modified: `User` Model

```python
# Added relationship
tasks = relationship("Task", back_populates="user", lazy="dynamic")
```

---

### `db/schemas.py`

#### Added Schemas (15 total)

| Schema               | Type     | Fields                                                                            |
| -------------------- | -------- | --------------------------------------------------------------------------------- |
| `TaskStatusEnum`     | Enum     | 9 status values                                                                   |
| `TaskCreateRequest`  | Request  | `tool_id`, `agents?`                                                              |
| `FileMetadata`       | Request  | `filename`, `content_type`                                                        |
| `UploadUrlsRequest`  | Request  | `files`, `has_parameters`                                                         |
| `UploadUrlInfo`      | Response | `url`, `key`, `method`, `headers`, `expires_at`                                   |
| `UploadUrlsResponse` | Response | `task_id`, `status`, `uploads`, `expires_in_seconds`, `message`                   |
| `TaskResponse`       | Response | Full task status with timestamps and error info                                   |
| `TaskCreateResponse` | Response | `task_id`, `status`, `tool_id`, `agents`, `created_at`, `message`                 |
| `DownloadInfo`       | Response | `download_id`, `filename`, `type`, `mime_type`, `size_bytes`, `url`, `expires_at` |
| `DownloadsResponse`  | Response | `task_id`, `downloads`, `expires_in_seconds`                                      |
| `TaskListItem`       | Response | `task_id`, `status`, `tool_id`, `progress`, `created_at`, `completed_at`          |
| `PaginationInfo`     | Response | `total`, `limit`, `offset`, `has_more`                                            |
| `TaskListResponse`   | Response | `tasks`, `pagination`                                                             |
| `TaskCancelResponse` | Response | `task_id`, `status`, `message`, `cancelled_at`                                    |
| `TaskDeleteResponse` | Response | `task_id`, `message`, `files_deleted`                                             |

---

### `main.py`

#### Added Import

```python
from api.task_routes import router as task_router
```

#### Added Route Registration

```python
app.include_router(task_router)
```

---

### `transformers/profile_my_data_transformer.py`

#### Added Import

```python
from typing import TYPE_CHECKING
from services.s3_service import s3_service

if TYPE_CHECKING:
    from db import models
```

#### Added Functions

**`run_profile_my_data_analysis(task, current_user, db)`**

- Main entry point for profile analysis
- Reads input files from S3
- Reads parameters from S3
- Executes agents with billing
- Uploads outputs to S3
- Returns `{status: "success"}` or `{status: "error", error: "...", error_code: "..."}`

**`_determine_file_key(filename)`**

- Maps filename to file key (`primary` or `baseline`)
- Based on filename containing "baseline"

**`_upload_outputs_to_s3(task, downloads)`**

- Uploads output files to S3
- Handles XLSX, JSON, CSV content types
- Returns count of uploaded files

---

### `transformers/clean_my_data_transformer.py`

#### Added Import

```python
from typing import TYPE_CHECKING
from services.s3_service import s3_service

if TYPE_CHECKING:
    from db import models
```

#### Added Functions

**`run_clean_my_data_analysis(task, current_user, db)`**

- Main entry point for clean analysis
- **Supports agent chaining** - output of one agent feeds into next
- Calls `_update_files_from_result(files_map, result)` after each agent

**`_determine_file_key(filename)`** - Same as profile

**`_upload_outputs_to_s3(task, downloads)`** - Same as profile

---

### `transformers/master_my_data_transformer.py`

#### Added Import

```python
from typing import TYPE_CHECKING
from services.s3_service import s3_service

if TYPE_CHECKING:
    from db import models
```

#### Added Functions

**`run_master_my_data_analysis(task, current_user, db)`**

- Main entry point for master analysis
- **Supports agent chaining** - output of one agent feeds into next

**`_determine_file_key(filename)`** - Same as profile

**`_upload_outputs_to_s3(task, downloads)`** - Same as profile

---

## Database Changes

### New Table: `tasks`

```sql
CREATE TABLE tasks (
    task_id VARCHAR(36) PRIMARY KEY COMMENT 'UUID task identifier',
    user_id INTEGER NOT NULL COMMENT 'Foreign key to users table',
    tool_id VARCHAR(50) NOT NULL COMMENT 'Tool identifier',
    agents JSON NOT NULL COMMENT 'Array of agent IDs to execute',
    status VARCHAR(20) NOT NULL DEFAULT 'CREATED' COMMENT 'Task status',
    progress INTEGER NOT NULL DEFAULT 0 COMMENT 'Progress percentage 0-100',
    current_agent VARCHAR(100) NULL COMMENT 'Currently executing agent',
    error_code VARCHAR(50) NULL COMMENT 'Error code if failed',
    error_message TEXT NULL COMMENT 'Error message if failed',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    upload_started_at DATETIME NULL,
    processing_started_at DATETIME NULL,
    completed_at DATETIME NULL,
    failed_at DATETIME NULL,
    cancelled_at DATETIME NULL,
    expired_at DATETIME NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    s3_cleaned BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_task_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### Indexes Created

| Index Name              | Columns             | Purpose          |
| ----------------------- | ------------------- | ---------------- |
| PRIMARY                 | `task_id`           | Primary key      |
| `idx_tasks_user_id`     | `user_id`           | Filter by user   |
| `idx_tasks_status`      | `status`            | Filter by status |
| `idx_tasks_user_status` | `user_id`, `status` | Composite filter |
| `idx_tasks_created_at`  | `created_at`        | Sort by date     |
| `idx_tasks_tool_id`     | `tool_id`           | Filter by tool   |

---

## API Endpoints

### Complete Endpoint Reference

| Method | Endpoint                       | Auth        | Purpose                   |
| ------ | ------------------------------ | ----------- | ------------------------- |
| POST   | `/tasks`                       | ✅ Required | Create new task           |
| POST   | `/tasks/{task_id}/upload-urls` | ✅ Required | Get presigned upload URLs |
| POST   | `/tasks/{task_id}/process`     | ✅ Required | Trigger processing        |
| GET    | `/tasks/{task_id}`             | ✅ Required | Get task status           |
| GET    | `/tasks/{task_id}/downloads`   | ✅ Required | Get download URLs         |
| GET    | `/tasks`                       | ✅ Required | List user's tasks         |
| POST   | `/tasks/{task_id}/cancel`      | ✅ Required | Cancel task               |
| DELETE | `/tasks/{task_id}`             | ✅ Required | Delete task               |

### Request/Response Examples

See [frontend_guide.md](frontend_guide.md) for complete API documentation with examples.

---

## S3 File Structure

```
s3://agensium-files/
└── users/
    └── {user_id}/
        └── tasks/
            └── {task_id}/
                ├── inputs/
                │   ├── primary.csv         # Required: Main data file
                │   ├── baseline.csv        # Optional: Comparison file
                │   └── parameters.json     # Optional: Agent parameters
                └── outputs/
                    ├── data_profile_report.xlsx
                    ├── data_profile_report.json
                    ├── cleaned_data.csv
                    └── ... (tool-specific outputs)
```

---

## Code Documentation

### Transformer Function Pattern

All transformers follow this pattern:

```python
async def run_{tool}_analysis(
    task: "models.Task",
    current_user: Any,
    db: Any
) -> Dict[str, Any]:
    """
    Execute {tool} analysis using S3 files.

    1. Read input files from S3
    2. Read parameters from S3 (optional)
    3. Execute agents with billing
    4. Upload outputs to S3
    5. Return status
    """
    # ... implementation
```

### Return Values

**Success:**

```python
{"status": "success"}
```

**Error:**

```python
{
    "status": "error",
    "error": "Human-readable error message",
    "error_code": "ERROR_CODE"
}
```

**Billing Error:**

```python
{
    "status": "error",
    "error": "Insufficient credits",
    "error_code": "BILLING_INSUFFICIENT_CREDITS",
    "context": {"available": 50, "required": 150, "shortfall": 100}
}
```

---

## Billing System

### Upfront Credit Validation

The billing system validates and consumes ALL credits **before** any agent execution begins. This ensures:

1. **No partial results** - Either all agents run or none run
2. **Predictable behavior** - User knows upfront if they have enough credits
3. **Simpler error handling** - No need to handle partial failure scenarios

### Billing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  BEFORE Agent Loop                                               │
├─────────────────────────────────────────────────────────────────┤
│  1. Calculate total cost for ALL agents                          │
│  2. Check if user can afford (WalletService.can_afford_agents)   │
│  3. If NO: Return BILLING_INSUFFICIENT_CREDITS error immediately │
│  4. If YES: Consume credits for ALL agents upfront               │
├─────────────────────────────────────────────────────────────────┤
│  DURING Agent Loop                                               │
├─────────────────────────────────────────────────────────────────┤
│  5. Execute agents one by one (billing already done)             │
│  6. No billing checks per agent                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component                    | Location                     | Purpose                              |
| ---------------------------- | ---------------------------- | ------------------------------------ |
| `BillingContext`             | `billing/billing_context.py` | Context manager for billing          |
| `validate_and_consume_all()` | `BillingContext`             | Upfront validation + consumption     |
| `can_afford_agents()`        | `WalletService`              | Check affordability for all agents   |
| `consume_for_agent()`        | `WalletService`              | Atomic credit deduction              |
| `InsufficientCreditsError`   | `billing/exceptions.py`      | Raised when credits are insufficient |

### Error Codes

| Error Code                     | HTTP | Description                       |
| ------------------------------ | ---- | --------------------------------- |
| `BILLING_INSUFFICIENT_CREDITS` | 402  | Not enough credits for all agents |
| `BILLING_WALLET_NOT_FOUND`     | 404  | User doesn't have a wallet        |
| `BILLING_AGENT_COST_MISSING`   | 500  | Agent cost not configured         |

### Usage in Transformers

```python
from billing import BillingContext, InsufficientCreditsError

# ========== UPFRONT BILLING ==========
with BillingContext(current_user) as billing:
    try:
        billing.validate_and_consume_all(
            agents=task.agents,
            tool_id=task.tool_id,
            task_id=task.task_id
        )
    except InsufficientCreditsError as e:
        return billing.get_billing_error_response(...)
# ========== END UPFRONT BILLING ==========

# Execute agents (billing already handled)
for agent_id in task.agents:
    result = execute_agent(agent_id)
```

---

## Testing Checklist

### Unit Tests

- [ ] `S3Service.generate_upload_url()`
- [ ] `S3Service.generate_download_url()`
- [ ] `S3Service.verify_input_files()`
- [ ] `Task.can_process()`
- [ ] `Task.can_cancel()`

### Integration Tests

- [ ] POST /tasks - Create task
- [ ] POST /tasks/{id}/upload-urls - Get URLs
- [ ] File upload to B2
- [ ] POST /tasks/{id}/process - Trigger
- [ ] GET /tasks/{id} - Status polling
- [ ] GET /tasks/{id}/downloads - Get downloads

### End-to-End Tests

- [ ] Complete profile-my-data flow
- [ ] Complete clean-my-data flow
- [ ] Complete master-my-data flow
- [ ] Error handling (missing files)
- [ ] Error handling (insufficient credits)
- [ ] Task cancellation
- [ ] Task deletion with S3 cleanup

---

## Change Log

### December 20, 2025 - V2.1.1 Async Processing

**Async Processing Implementation**

- Modified `POST /tasks/{task_id}/process` to return immediately
- Added `_execute_task_background()` function for background processing
- Implemented `threading.Thread` with `daemon=True` pattern
- Each background thread creates its own DB session for thread safety
- Background thread creates new asyncio event loop
- Updated response message to indicate task tracking from Tasks page

**Files Modified:**

- `api/task_routes.py` - Added async processing with background threads

### December 19, 2025 - Initial Implementation

**Phase 1: Infrastructure**

- Created `services/` directory
- Created `services/__init__.py`
- Created `services/s3_service.py` with full B2 integration
- Added `TaskStatus` enum to `db/models.py`
- Added `Task` model to `db/models.py`
- Added `User.tasks` relationship

**Phase 2: Task API**

- Created `api/task_routes.py` with 8 endpoints
- Updated `main.py` to register routes

**Phase 3: Task Schemas**

- Added 15 Pydantic schemas to `db/schemas.py`

**Phase 4: Transformer Updates**

- Added `run_profile_my_data_analysis()` to profile transformer
- Added `run_clean_my_data_analysis()` to clean transformer
- Added `run_master_my_data_analysis()` to master transformer
- Added helper functions to all transformers

**Phase 5: Database Migration**

- Created `db/migrations/create_tasks_table.py`
- Executed migration successfully
- Created 5 indexes + PRIMARY key
- Verified 18 columns

---

## Quick Reference

### Environment Variables

```bash
# Backblaze B2 (Required)
AWS_ENDPOINT_URL=https://s3.us-east-005.backblazeb2.com
AWS_ACCESS_KEY_ID=your_key_id
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-005
S3_BUCKET=agensium-files

# Database (Required)
DATABASE_URL=mysql+pymysql://user:pass@host:port/db
```

### Run Migration

```bash
python -m db.migrations.create_tasks_table
```

### Test Server Imports

```bash
python -c "from main import app; print('OK')"
```
