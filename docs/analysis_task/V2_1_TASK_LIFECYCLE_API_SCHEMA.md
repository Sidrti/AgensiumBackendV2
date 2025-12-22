# Agensium V2.1 Task Lifecycle, API, and Schema

**Document Version:** 2.1.1  
**Created:** December 20, 2025  
**Purpose:** Consolidate the task lifecycle definitions, API contracts, error handling, and simplified `Task` data model so every consumer (frontend, backend, QA, docs) understands exactly how V2.1 operates.

> For the architectural motivation, system flow, and implementation roadmap, see the companion overview document **"V2.1 Architecture & Roadmap"**.

---

## Table of Contents

1. [Status Lifecycle](#status-lifecycle)
2. [Transitions & Diagrams](#transitions--diagrams)
3. [Async Processing Model](#async-processing-model)
4. [Error Handling & Progress](#error-handling--progress)
5. [Timeouts, Cleanup & Retention](#timeouts-cleanup--retention)
6. [Frontend Integration](#frontend-integration)
7. [Task API Specification](#task-api-specification)
8. [Request / Response Schemas](#request--response-schemas)
9. [Errors & Migration](#errors--migration)
10. [Database Schema V2.1](#database-schema-v21)
11. [Data Retention & Storage Savings](#data-retention--storage-savings)

---

## Status Lifecycle

### All Task Statuses

```python
class TaskStatus(str, Enum):
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

### Categorized States

| Category | Statuses                                      | User Action                                        |
| -------- | --------------------------------------------- | -------------------------------------------------- |
| Pending  | `CREATED`, `UPLOADING`                        | Request upload URLs and PUT files/parameters to B2 |
| Ready    | `QUEUED`                                      | Trigger processing                                 |
| Active   | `PROCESSING`                                  | Poll status, optionally cancel                     |
| Terminal | `COMPLETED`, `FAILED`, `CANCELLED`, `EXPIRED` | View/download results or retry                     |

## Status Definitions

Each status supports specific transitions, timestamps, and user-visible cues.

### `CREATED`

- Task record added with `tool_id`, optional `agents`, `status = CREATED`, `created_at`.
- Parameters are never stored in DB; they go to `users/{user_id}/tasks/{task_id}/inputs/parameters.json` in B2.
- Timeout: 15 minutes → `EXPIRED`.

### `UPLOADING`

- Triggered when `POST /tasks/{id}/upload-urls` is called.
- Upload URLs issued for required files (e.g., primary, baseline) and optional `parameters.json`.
- Fields updated: `status = UPLOADING`, `upload_started_at`.
- Timeout: 15 minutes for files to land in B2 → `EXPIRED` if missing.

### `UPLOAD_FAILED`

- Occurs when `POST /tasks/{id}/process` detects missing files.
- Field: `error_message = "Required files not found in storage"`.
- Allows retry by re-requesting upload URLs (back to `UPLOADING`).

### `QUEUED`

- Files verified, before the synchronous processing block begins.
- Immediately transitions to `PROCESSING` in the current implementation but represents the future queue slot.

### `PROCESSING`

- Agents execute sequentially.
- Fields tracked: `processing_started_at`, `progress` (0–100), `current_agent`.
- On completion: go to `COMPLETED`; on errors: `FAILED`; on user cancellation: `CANCELLED`.

### `COMPLETED`

- Outputs uploaded to `users/{user_id}/tasks/{task_id}/outputs/`.
- Downloads obtained from `GET /tasks/{id}/downloads` (returns presigned URLs, no base64).

### `FAILED`

- Capture `error_code` (`AGENT_ERROR`, `BILLING_INSUFFICIENT_CREDITS`, etc.) and `error_message`.
- Billing is verified before processing; insufficient credits fail before agents run.

### `CANCELLED`

- User can cancel while `PROCESSING`; credits consumed earlier are not refunded.

### `EXPIRED`

- Triggered by URL expiry (15 minutes) or timeouts (1 hour idle).
- Cleanup jobs delete partial uploads.

## Transitions & Diagrams

```
CREATED ──► UPLOADING ──► QUEUED ──► PROCESSING ──► COMPLETED
            │             │                   │
            ├────────► UPLOAD_FAILED ──► UPLOADING│
            │                                     ▼
            └─────────────────────────────────► FAILED/CANCELLED/EXPIRED
```

### Matrix (excerpt)

| From / To    | UPLOADING | PROCESSING | COMPLETED | FAILED | EXPIRED |
| ------------ | --------- | ---------- | --------- | ------ | ------- |
| `CREATED`    | ✅        | -          | -         | -      | ✅      |
| `UPLOADING`  | -         | ✅         | -         | -      | ✅      |
| `PROCESSING` | -         | -          | ✅        | ✅     | -       |

## Async Processing Model

- `POST /tasks/{id}/process` now verifies uploads, flips status to `PROCESSING`, and immediately responds. Real work runs in a background thread.

```python
@router.post("/{task_id}/process")
async def trigger_processing(...):
    # 1. Verify required files via s3_service
    # 2. Update task to PROCESSING
    threading.Thread(target=_run_background_task, args=(task_id,), daemon=True).start()
    return TaskResponse(status="PROCESSING", message="Processing started...")
```

Frontend then navigates to the Tasks List page and polls `GET /tasks/{id}` only for progress updates (not during creation).

### Frontend flow snippet

```typescript
const result = await executeTaskFlowAsync(
  { toolId, agents, files, parameters },
  token
);
await fetch(`/tasks/${result.task_id}/process`, { method: "POST" });
setTimeout(() => navigate("/tasks"), 3000);
```

## Error Handling & Progress

### Recoverable Errors

| Status           | Error                | Recovery                |
| ---------------- | -------------------- | ----------------------- |
| UPLOAD_FAILED    | Missing files        | Request new upload URLs |
| EXPIRED          | URLs timed out       | Create new task         |
| FAILED (billing) | Insufficient credits | Add credits & retry     |

### Non-Recoverable

| Status          | Error            | Action                       |
| --------------- | ---------------- | ---------------------------- |
| FAILED (agent)  | Processing error | Review data, create new task |
| FAILED (format) | Invalid file     | Fix format, rerun            |

### Progress Tracking

- `calculate_progress` maps statuses to percentages (0 at `CREATED`, 100 at `COMPLETED`).
- Agent execution fills the 20–95% window; `current_agent` is updated in DB for UI glimpses.

Detailed mapping:

| Progress | Event                                  |
| -------- | -------------------------------------- |
| 0%       | Task created                           |
| 10%      | Upload URLs generated                  |
| 15%      | Inputs verified                        |
| 20–95%   | Agent execution (per-agent increments) |
| 100%     | Task completed                         |

`progress_detail` payload example:

```json
{
  "current_stage": "agent_execution",
  "current_agent": "score-risk",
  "agents_total": 6,
  "agents_completed": 3
}
```

## Timeouts, Cleanup & Retention

### Timeout Rules

| Status     | Timeout    | Result                     |
| ---------- | ---------- | -------------------------- |
| CREATED    | 15 minutes | Become `EXPIRED`           |
| UPLOADING  | 15 minutes | Become `EXPIRED`           |
| PROCESSING | 30 minutes | Mark as `FAILED` (timeout) |

### Cleanup Job (runs every 15 minutes)

```python
async def cleanup_expired_tasks():
    await db.execute("""
        UPDATE tasks SET status='EXPIRED', expired_at=NOW()
        WHERE status IN ('CREATED', 'UPLOADING')
        AND created_at < NOW() - INTERVAL 15 MINUTE
    """)
    rows = await db.fetch_all(...)
    for task in rows:
        s3_service.delete_folder(f"users/{task.user_id}/tasks/{task.task_id}/")
        await db.execute("UPDATE tasks SET s3_cleaned = TRUE WHERE task_id = :task_id", {"task_id": task.task_id})
```

### S3 Retention

| Content                | Retention                | Action             |
| ---------------------- | ------------------------ | ------------------ |
| Input files            | 7 days after completion  | Delete             |
| Output files           | 30 days after completion | Delete             |
| Failed/expired uploads | 7 days                   | Delete immediately |

`delete_folder` removes the entire `tasks/{task_id}/` tree when flagged.

## Frontend Integration

- TaskProcessing page now:
  1. Creates task (no files).
  2. Gets upload URLs.
  3. Uploads files/parameters directly to B2.
  4. Calls `POST /tasks/{id}/process`, receives immediate `PROCESSING` response.
  5. Redirects user to Tasks List (no remaining polling).

`Tasks List` shows per-task statuses based on the mapping below:

| Status        | Label         | Color  | Icon    | Message               |
| ------------- | ------------- | ------ | ------- | --------------------- |
| CREATED       | Initializing  | gray   | clock   | Preparing analysis... |
| UPLOADING     | Uploading     | blue   | upload  | Upload files & params |
| UPLOAD_FAILED | Upload Failed | red    | error   | Retry upload          |
| QUEUED        | Ready         | yellow | queue   | Files received        |
| PROCESSING    | Processing    | blue   | spinner | Analysis running      |
| COMPLETED     | Complete      | green  | check   | View downloads        |
| FAILED        | Failed        | red    | error   | See details           |
| CANCELLED     | Cancelled     | gray   | cancel  | Task cancelled        |
| EXPIRED       | Expired       | gray   | clock   | Create new task       |

## Task API Specification

| Endpoint                       | Method | Purpose                                           |
| ------------------------------ | ------ | ------------------------------------------------- |
| `/tasks`                       | POST   | Create task (tool_id + optional agents).          |
| `/tasks`                       | GET    | List user’s tasks (`limit`, `status`, `tool_id`). |
| `/tasks/{task_id}`             | GET    | Fetch status, timestamps, progress.               |
| `/tasks/{task_id}/upload-urls` | POST   | Generate presigned URLs for files + parameters.   |
| `/tasks/{task_id}/process`     | POST   | Verify uploads + trigger processing (background). |
| `/tasks/{task_id}/downloads`   | GET    | Retrieve presigned download URLs.                 |
| `/tasks/{task_id}/report`      | GET    | Download full report JSON.                        |
| `/tasks/{task_id}/cancel`      | POST   | Cancel a non-terminal task.                       |
| `/tasks/{task_id}`             | DELETE | Delete task and associated files from S3.         |

### `/tasks` (Create)

- Body: `{ "tool_id": "profile-my-data", "agents": ["unified-profiler"] }`
- Response: `task_id`, `status = CREATED`, `created_at`, message.

### `/tasks/{task_id}/upload-urls`

- Body: `files` map (primary/baseline metadata), `has_parameters` flag.
- Response: status `UPLOADING`, map of upload infos `{ url, key, method, headers, expires_at }`, `expires_in_seconds = 900`.

### `/tasks/{task_id}/process`

- No body. Immediately returns `status = PROCESSING`, `progress = 15`, `processing_started_at`.
- On missing files: 400 with `status = UPLOAD_FAILED` and `error_code = FILES_NOT_FOUND`.

### `/tasks/{task_id}`

- Returns `status`, timestamps (`created_at`, `processing_started_at`, etc.), `progress`, `progress_detail`, `downloads_available` boolean.

### `/tasks/{task_id}/downloads`

- Requires `COMPLETED` status.
- Returns list of downloads: each entry includes `download_id`, `filename`, `type`, `mime_type`, `size_bytes`, `url`, `expires_at`.

### `/tasks/{task_id}/report`

- Returns aggregated report JSON with `executiveSummary`, `issueSummary`, `agentResults`, and referenced downloads.

### `/tasks` (List)

- Query filters: `status`, `tool_id`, `limit`, `offset`, `sort`.
- Response: paginated list of tasks.

### `/tasks/{task_id}/cancel` and `DELETE /tasks/{task_id}`

- Cancel: transitions to `CANCELLED`, returns timestamp.
- Delete: removes DB record and S3 files (`files_deleted` count).

## Request / Response Schemas

### `TaskCreateRequest`

- `tool_id`: str (validated against available tools).
- `agents`: optional list of agent IDs.

### `UploadUrlsRequest`

- `files`: dict of `{key: FileMetadata}` where `FileMetadata` includes `filename` and optional `content_type`.
- `has_parameters`: bool.

### `TaskResponse`

- Fields: `task_id`, `status`, `tool_id`, `agents`, `progress`, `progress_detail`, timestamps, `downloads_available`, optional error fields.

### `UploadUrlsResponse`, `DownloadInfo`, `DownloadsResponse`, `TaskListResponse`

- Provide typed payloads for upload URLs, downloads, and paginated lists.

**All schemas are defined in `db/schemas.py`; see code excerpt**.

## Errors & Migration

### Standard Error Format

```json
{
  "detail": "Human-readable message",
  "error_code": "SPECIFIC_CODE",
  "context": { "field": "contextual info" }
}
```

### Common `error_code`s

| Code                           | HTTP Status | Trigger                       |
| ------------------------------ | ----------- | ----------------------------- |
| `TASK_NOT_FOUND`               | 404         | Invalid task ID               |
| `TASK_UNAUTHORIZED`            | 403         | Accessing another user’s task |
| `INVALID_TOOL_ID`              | 400         | Unsupported tool              |
| `FILES_NOT_FOUND`              | 400         | Missing input files           |
| `UPLOAD_URLS_EXPIRED`          | 400         | Upload URLs expired           |
| `TASK_ALREADY_PROCESSING`      | 400         | Duplicate process requests    |
| `TASK_NOT_CANCELLABLE`         | 400         | Terminal task cancellation    |
| `BILLING_INSUFFICIENT_CREDITS` | 402         | Wallet shortfall              |
| `INTERNAL_ERROR`               | 500         | Unexpected server failure     |

### Migration from V1

1. V1 `/analyze` remains temporarily but is deprecated (phase: warning → header → removal).
2. V2.1 flow: `POST /tasks` → upload URLs → PUT files/parameters to B2 → `POST /tasks/{id}/process` → poll `/tasks` or wait for downloads.
3. Emphasize: parameters now live in B2; `Task` records do not store full results.

## Database Schema V2.1

### `tasks` Table (simplified)

```sql
CREATE TABLE tasks (
    task_id VARCHAR(36) PRIMARY KEY,
    user_id INTEGER NOT NULL,
    tool_id VARCHAR(50) NOT NULL,
    agents JSON NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'CREATED',
    progress INTEGER NOT NULL DEFAULT 0,
    current_agent VARCHAR(100),
    error_code VARCHAR(50),
    error_message TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    upload_started_at DATETIME,
    processing_started_at DATETIME,
    completed_at DATETIME,
    failed_at DATETIME,
    cancelled_at DATETIME,
    expired_at DATETIME,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    s3_cleaned BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_task_user FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Indexes & Access Patterns

| Index                   | Purpose                         |
| ----------------------- | ------------------------------- |
| `idx_tasks_user_id`     | List a user’s tasks             |
| `idx_tasks_status`      | Cleanup jobs and status filters |
| `idx_tasks_user_status` | Combined filters                |
| `idx_tasks_created_at`  | Sorting and expiry              |
| `idx_tasks_tool_id`     | Tool-level analytics            |

Queries rely on these indexes (e.g., paginated listings, active tasks, cleaning expired entries).

### `Task` SQLAlchemy Model Highlights

- Includes helper methods `is_terminal()`, `can_process()`, `get_input_prefix()` for S3 key derivation.
- Relationship: `User.tasks = relationship("Task", back_populates="user")` aids ownership checks.

### Pydantic Notes

- `TaskStatusEnum` mirrors the SQL state values.
- `UploadUrlInfo` provides `headers` and `expires_at` for UI.
- `DownloadInfo` enumerates file metadata plus presigned URL.

## Data Retention & Storage Savings

### Retention Policy

| Artifact             | Retention               | Action            |
| -------------------- | ----------------------- | ----------------- |
| Task metadata        | 1 year                  | Soft delete       |
| Inputs               | 7 days post-completion  | Delete from B2    |
| Outputs              | 30 days post-completion | Delete from B2    |
| Expired/Failed tasks | 7 days                  | Immediate cleanup |

### Storage Efficiency

- V2 stored ~30 DB fields plus results, often 15–100 KB per task.
- V2.1 stores 18 fields (~720 bytes) with only minimal JSON for agents.
- Result/parameter payloads live in B2; database size shrinks ~95%.

## References & Next Steps

- Use the companion **Architecture & Roadmap** document for system context, timeline, testing checklists, and Backblaze/S3 service design.
- Implement cleanup jobs to honor retention policies and delete `users/{user_id}/tasks/{task_id}/` prefixes when `s3_cleaned` toggles to `TRUE`.
- Monitor `tasks` lifecycle transitions to ensure new error and retry states behave as expected.
