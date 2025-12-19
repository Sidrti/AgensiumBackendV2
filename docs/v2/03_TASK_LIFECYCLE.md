# Task Lifecycle - Status Tracking System

**Document Version:** 1.0  
**Created:** December 19, 2025  
**Purpose:** Define the complete task lifecycle from creation to completion/failure

---

## Table of Contents

1. [Status Overview](#status-overview)
2. [Status Definitions](#status-definitions)
3. [State Transitions](#state-transitions)
4. [Status Flow Diagrams](#status-flow-diagrams)
5. [Error Handling](#error-handling)
6. [Progress Tracking](#progress-tracking)
7. [Timeout & Cleanup](#timeout--cleanup)
8. [Frontend Integration](#frontend-integration)

---

## Status Overview

### All Task Statuses

```python
class TaskStatus(str, Enum):
    # Initial States
    CREATED = "CREATED"           # Task created, awaiting upload URLs

    # Upload States
    UPLOADING = "UPLOADING"       # Upload URLs generated, files being uploaded
    UPLOAD_FAILED = "UPLOAD_FAILED"  # Upload verification failed

    # Processing States
    QUEUED = "QUEUED"             # Files uploaded, ready to process
    PROCESSING = "PROCESSING"     # Analysis in progress

    # Terminal States
    COMPLETED = "COMPLETED"       # Successfully completed
    FAILED = "FAILED"             # Processing failed
    CANCELLED = "CANCELLED"       # User cancelled

    # Expiry State
    EXPIRED = "EXPIRED"           # Task expired (upload URLs expired)
```

### Status Categories

| Category     | Statuses                              | User Can...                |
| ------------ | ------------------------------------- | -------------------------- |
| **Pending**  | CREATED, UPLOADING                    | Request URLs, Upload files |
| **Ready**    | QUEUED                                | Trigger processing         |
| **Active**   | PROCESSING                            | Poll status, Cancel        |
| **Terminal** | COMPLETED, FAILED, CANCELLED, EXPIRED | View results, Download     |

---

## Status Definitions

### CREATED

**Description:** Task record created, no upload URLs generated yet.

**Entry:** `POST /tasks` called  
**Exit:** `POST /tasks/{id}/upload-urls` called → UPLOADING

**Fields Set:**

- `task_id` (UUID)
- `user_id`
- `tool_id`
- `agents` (list)
- `parameters` (JSON)
- `status = CREATED`
- `created_at`

**Timeout:** 15 minutes → EXPIRED

---

### UPLOADING

**Description:** Upload URLs generated, waiting for files.

**Entry:** `POST /tasks/{id}/upload-urls` called  
**Exit:**

- `POST /tasks/{id}/process` called & files verified → QUEUED
- Upload URLs expire → EXPIRED
- Files not found on verify → UPLOAD_FAILED

**Fields Set:**

- `status = UPLOADING`
- `upload_urls` (JSON with presigned URLs)
- `upload_started_at`
- `s3_input_keys` (expected file keys)

**Timeout:** 15 minutes after upload URLs generated → EXPIRED

---

### UPLOAD_FAILED

**Description:** Upload verification failed - files not found in S3.

**Entry:** `POST /tasks/{id}/process` called but files missing  
**Exit:**

- `POST /tasks/{id}/upload-urls` called (retry) → UPLOADING

**Fields Set:**

- `status = UPLOAD_FAILED`
- `error_message = "Required files not found in storage"`
- `updated_at`

**Retry:** User can request new upload URLs

---

### QUEUED

**Description:** Files uploaded successfully, ready for processing.

**Entry:** `POST /tasks/{id}/process` called & files verified  
**Exit:**

- Processing starts → PROCESSING

**Fields Set:**

- `status = QUEUED`
- `files_verified_at`
- `updated_at`

**Note:** In synchronous V2, QUEUED transitions immediately to PROCESSING.  
In future queue system, task waits in queue.

---

### PROCESSING

**Description:** Analysis actively running.

**Entry:** Processing begins  
**Exit:**

- Success → COMPLETED
- Error → FAILED
- User cancels → CANCELLED

**Fields Set:**

- `status = PROCESSING`
- `processing_started_at`
- `progress` (0-100)
- `current_agent` (currently executing agent)
- `agents_completed` (list)
- `updated_at`

**Progress Updates:**

```python
# During processing, update progress
task.progress = (agents_completed / total_agents) * 100
task.current_agent = "unified-profiler"
task.agents_completed = ["drift-detector", "score-risk"]
```

---

### COMPLETED

**Description:** Analysis finished successfully.

**Entry:** All agents completed successfully  
**Terminal:** Yes

**Fields Set:**

- `status = COMPLETED`
- `completed_at`
- `progress = 100`
- `result_summary` (JSON summary)
- `s3_output_keys` (list of output file keys)
- `download_urls_expires_at` (for cached URLs)

**Result Access:**

- Full results stored in `task_result` (JSON)
- Files available in S3 outputs folder
- Download URLs via `GET /tasks/{id}/downloads`

---

### FAILED

**Description:** Analysis failed with error.

**Entry:**

- Agent execution error
- System error
- Billing error (insufficient credits)

**Terminal:** Yes (but can retry in some cases)

**Fields Set:**

- `status = FAILED`
- `error_code` (e.g., "AGENT_ERROR", "BILLING_ERROR")
- `error_message` (human readable)
- `failed_at`
- `failed_agent` (which agent failed)
- `partial_results` (if any agents completed)

**Error Codes:**

```python
ERROR_CODES = {
    "AGENT_ERROR": "Agent execution failed",
    "BILLING_INSUFFICIENT_CREDITS": "Insufficient credits",
    "BILLING_WALLET_NOT_FOUND": "Wallet not found",
    "FILE_READ_ERROR": "Could not read input file",
    "FILE_FORMAT_ERROR": "Invalid file format",
    "TIMEOUT_ERROR": "Processing timeout exceeded",
    "INTERNAL_ERROR": "Internal server error"
}
```

---

### CANCELLED

**Description:** User cancelled the task.

**Entry:** `POST /tasks/{id}/cancel` called (while PROCESSING)  
**Terminal:** Yes

**Fields Set:**

- `status = CANCELLED`
- `cancelled_at`
- `cancelled_reason = "User requested cancellation"`

**Note:** Credits already consumed are not refunded (partial work done).

---

### EXPIRED

**Description:** Task expired before processing started.

**Entry:**

- Upload URLs expired (15 min timeout)
- Task idle too long (1 hour timeout)

**Terminal:** Yes

**Fields Set:**

- `status = EXPIRED`
- `expired_at`
- `expiry_reason` (e.g., "Upload URLs expired")

**Cleanup:** Partial uploads deleted from S3.

---

## State Transitions

### Valid Transitions

```
CREATED ─────────────────► UPLOADING
    │                          │
    │                          ├───► UPLOAD_FAILED ───► UPLOADING (retry)
    │                          │
    │                          └───► QUEUED
    │                                   │
    ▼                                   ▼
EXPIRED ◄─────────────────── PROCESSING
                                │  │
                                │  └───► CANCELLED
                                │
                                ├───► COMPLETED
                                │
                                └───► FAILED
```

### Transition Matrix

| From \ To         | CREATED | UPLOADING | UPLOAD_FAILED | QUEUED | PROCESSING | COMPLETED | FAILED | CANCELLED | EXPIRED |
| ----------------- | ------- | --------- | ------------- | ------ | ---------- | --------- | ------ | --------- | ------- |
| **CREATED**       | -       | ✅        | -             | -      | -          | -         | -      | -         | ✅      |
| **UPLOADING**     | -       | -         | ✅            | ✅     | -          | -         | -      | -         | ✅      |
| **UPLOAD_FAILED** | -       | ✅        | -             | -      | -          | -         | -      | -         | -       |
| **QUEUED**        | -       | -         | -             | -      | ✅         | -         | -      | -         | -       |
| **PROCESSING**    | -       | -         | -             | -      | -          | ✅        | ✅     | ✅        | -       |

---

## Status Flow Diagrams

### Happy Path

```
┌─────────┐    POST /tasks     ┌──────────┐
│  START  │───────────────────►│ CREATED  │
└─────────┘                    └────┬─────┘
                                    │
                    POST /tasks/:id/upload-urls
                                    │
                                    ▼
                              ┌───────────┐
                              │ UPLOADING │
                              └─────┬─────┘
                                    │
                          Frontend uploads to B2
                                    │
                    POST /tasks/:id/process
                                    │
                                    ▼
                              ┌─────────┐
                              │ QUEUED  │
                              └────┬────┘
                                   │
                        (In sync V2: immediate)
                                   │
                                   ▼
                            ┌────────────┐
                            │ PROCESSING │
                            └──────┬─────┘
                                   │
                          All agents complete
                                   │
                                   ▼
                            ┌───────────┐
                            │ COMPLETED │
                            └───────────┘
```

### Error Paths

```
UPLOADING
    │
    ├── Files not found ──► UPLOAD_FAILED
    │                            │
    │                       Retry with new URLs
    │                            │
    │                            ▼
    │                       UPLOADING
    │
    └── URLs expired ────► EXPIRED


PROCESSING
    │
    ├── Agent error ─────► FAILED (error_code: AGENT_ERROR)
    │
    ├── Billing error ───► FAILED (error_code: BILLING_INSUFFICIENT_CREDITS)
    │
    └── User cancels ────► CANCELLED
```

---

## Error Handling

### Recoverable Errors

| Status           | Error                | Recovery Action                       |
| ---------------- | -------------------- | ------------------------------------- |
| UPLOAD_FAILED    | Files not in S3      | Request new upload URLs, retry upload |
| EXPIRED          | URLs expired         | Create new task                       |
| FAILED (billing) | Insufficient credits | Add credits, create new task          |

### Non-Recoverable Errors

| Status          | Error            | User Action                             |
| --------------- | ---------------- | --------------------------------------- |
| FAILED (agent)  | Processing error | Review error, fix data, create new task |
| FAILED (format) | Invalid file     | Fix file format, create new task        |

### Partial Results

When failure occurs **after some agents complete**:

```python
# Task with partial results
{
    "task_id": "abc-123",
    "status": "FAILED",
    "error_code": "BILLING_INSUFFICIENT_CREDITS",
    "error_message": "Insufficient credits for agent: score-risk",
    "partial_results": {
        "unified-profiler": { ... },  # Completed
        "drift-detector": { ... }     # Completed
    },
    "agents_completed": ["unified-profiler", "drift-detector"],
    "failed_agent": "score-risk"
}
```

---

## Progress Tracking

### Progress Calculation

```python
def calculate_progress(task: Task) -> int:
    """Calculate task progress percentage."""
    if task.status == TaskStatus.CREATED:
        return 0
    elif task.status == TaskStatus.UPLOADING:
        return 10  # URL generated
    elif task.status == TaskStatus.QUEUED:
        return 15  # Files verified
    elif task.status == TaskStatus.PROCESSING:
        # Calculate based on agents
        total_agents = len(task.agents)
        completed = len(task.agents_completed or [])
        # 15-95% for processing (leave room for finalizing)
        return 15 + int((completed / total_agents) * 80)
    elif task.status == TaskStatus.COMPLETED:
        return 100
    else:
        return task.progress or 0
```

### Progress Events

| Progress | Event                       |
| -------- | --------------------------- |
| 0%       | Task created                |
| 10%      | Upload URLs generated       |
| 15%      | Files uploaded & verified   |
| 20-95%   | Agent processing (N agents) |
| 100%     | Complete                    |

### Agent Progress Detail

```python
# Detailed progress response
{
    "task_id": "abc-123",
    "status": "PROCESSING",
    "progress": 55,
    "progress_detail": {
        "current_stage": "agent_execution",
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
    }
}
```

---

## Timeout & Cleanup

### Timeout Rules

| Status     | Timeout    | Action             |
| ---------- | ---------- | ------------------ |
| CREATED    | 15 minutes | → EXPIRED          |
| UPLOADING  | 15 minutes | → EXPIRED          |
| PROCESSING | 30 minutes | → FAILED (timeout) |

### Cleanup Jobs

```python
# Scheduled cleanup job (runs every 15 minutes)
async def cleanup_expired_tasks():
    """Expire stale tasks and clean up S3."""

    # 1. Expire CREATED tasks older than 15 minutes
    await db.execute("""
        UPDATE tasks
        SET status = 'EXPIRED',
            expired_at = NOW(),
            expiry_reason = 'Task creation timeout'
        WHERE status = 'CREATED'
        AND created_at < NOW() - INTERVAL 15 MINUTE
    """)

    # 2. Expire UPLOADING tasks older than 15 minutes
    await db.execute("""
        UPDATE tasks
        SET status = 'EXPIRED',
            expired_at = NOW(),
            expiry_reason = 'Upload URLs expired'
        WHERE status = 'UPLOADING'
        AND upload_started_at < NOW() - INTERVAL 15 MINUTE
    """)

    # 3. Clean up S3 for expired tasks
    expired_tasks = await db.fetch_all("""
        SELECT task_id, user_id
        FROM tasks
        WHERE status = 'EXPIRED'
        AND s3_cleaned = FALSE
    """)

    for task in expired_tasks:
        await s3_service.delete_task_folder(task.user_id, task.task_id)
        await db.execute("""
            UPDATE tasks SET s3_cleaned = TRUE WHERE task_id = ?
        """, task.task_id)
```

### S3 Retention

| Content Type       | Retention                |
| ------------------ | ------------------------ |
| Input files        | 7 days after completion  |
| Output files       | 30 days after completion |
| Failed task files  | 7 days                   |
| Expired task files | Delete immediately       |

---

## Frontend Integration

### Polling Strategy

```typescript
// Frontend polling for task status
async function pollTaskStatus(taskId: string): Promise<TaskResult> {
  const POLL_INTERVALS = {
    UPLOADING: 2000, // 2 seconds
    QUEUED: 1000, // 1 second
    PROCESSING: 3000, // 3 seconds
  };

  while (true) {
    const response = await fetch(`/tasks/${taskId}`);
    const task = await response.json();

    // Update UI with progress
    updateProgressUI(task.progress, task.status);

    // Check terminal states
    if (["COMPLETED", "FAILED", "CANCELLED", "EXPIRED"].includes(task.status)) {
      return task;
    }

    // Wait before next poll
    const interval = POLL_INTERVALS[task.status] || 3000;
    await sleep(interval);
  }
}
```

### Status Display Mapping

```typescript
const STATUS_DISPLAY = {
  CREATED: {
    label: "Initializing",
    color: "gray",
    icon: "clock",
    message: "Preparing your analysis...",
  },
  UPLOADING: {
    label: "Uploading",
    color: "blue",
    icon: "upload",
    message: "Please upload your files",
  },
  UPLOAD_FAILED: {
    label: "Upload Failed",
    color: "red",
    icon: "error",
    message: "File upload failed. Please try again.",
  },
  QUEUED: {
    label: "Ready",
    color: "yellow",
    icon: "queue",
    message: "Files received, starting analysis...",
  },
  PROCESSING: {
    label: "Processing",
    color: "blue",
    icon: "spinner",
    message: "Analysis in progress...",
  },
  COMPLETED: {
    label: "Complete",
    color: "green",
    icon: "check",
    message: "Analysis completed successfully!",
  },
  FAILED: {
    label: "Failed",
    color: "red",
    icon: "error",
    message: "Analysis failed. See details below.",
  },
  CANCELLED: {
    label: "Cancelled",
    color: "gray",
    icon: "cancel",
    message: "Analysis was cancelled.",
  },
  EXPIRED: {
    label: "Expired",
    color: "gray",
    icon: "clock",
    message: "Task expired. Please create a new analysis.",
  },
};
```

---

## Summary

### Key Design Decisions

1. **Fine-grained statuses** - Clear visibility at each stage
2. **Recoverable states** - UPLOAD_FAILED allows retry
3. **Progress tracking** - Agent-level progress
4. **Partial results** - Failed tasks may have partial data
5. **Automatic expiry** - Prevent orphaned tasks

### Implementation Priority

1. ✅ Basic statuses: CREATED → UPLOADING → QUEUED → PROCESSING → COMPLETED/FAILED
2. ⬜ Progress tracking during PROCESSING
3. ⬜ Timeout & cleanup jobs
4. ⬜ CANCELLED support
5. ⬜ Partial results on failure

---

**Document Status:** Complete  
**Last Updated:** December 19, 2025
