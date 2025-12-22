# Task Lifecycle - Status Tracking System

**Document Version:** 2.1.1  
**Created:** December 19, 2025  
**Updated:** December 20, 2025  
**Purpose:** Define the complete task lifecycle from creation to completion/failure

---

## Table of Contents

1. [Status Overview](#status-overview)
2. [Status Definitions](#status-definitions)
3. [State Transitions](#state-transitions)
4. [Status Flow Diagrams](#status-flow-diagrams)
5. [Async Processing](#async-processing)
6. [Error Handling](#error-handling)
7. [Progress Tracking](#progress-tracking)
8. [Timeout & Cleanup](#timeout--cleanup)
9. [Frontend Integration](#frontend-integration)

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
- `status = CREATED`
- `created_at`

**Note:** Parameters are NOT stored in database - they will be uploaded to B2

**Timeout:** 15 minutes → EXPIRED

---

### UPLOADING

**Description:** Upload URLs generated for files AND parameters, waiting for uploads.

**Entry:** `POST /tasks/{id}/upload-urls` called  
**Exit:**

- `POST /tasks/{id}/process` called & files verified → QUEUED
- Upload URLs expire → EXPIRED
- Files not found on verify → UPLOAD_FAILED

**Fields Set:**

- `status = UPLOADING`
- `upload_started_at`

**Files to Upload:**

- Primary file (required)
- Baseline file (optional)
- parameters.json (optional, but URL provided if needed)

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
- `updated_at`

**Note:** In synchronous V2.1, QUEUED transitions immediately to PROCESSING.  
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
- `updated_at`

**Progress Updates:**

```python
# During processing, update progress
task.progress = (agents_completed / total_agents) * 100
task.current_agent = "unified-profiler"
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

**Result Access:**

- Output files available in S3 outputs folder
- Download URLs via `GET /tasks/{id}/downloads`
- NO results stored in database

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
                          Frontend uploads:
                          - files to B2
                          - parameters.json to B2
                                    │
                    POST /tasks/:id/process
                    (Returns immediately)
                                    │
                                    ▼
                            ┌────────────┐
                            │ PROCESSING │ ◄── Backend executes in background
                            └──────┬─────┘
                                   │
                          Frontend navigates to
                          Tasks List page to track
                                   │
                          (Backend continues...)
                                   │
                          All agents complete
                          Outputs uploaded to B2
                                   │
                                   ▼
                            ┌───────────┐
                            │ COMPLETED │
                            └───────────┘
```

### Async Processing Flow (V2.1.1)

```
Frontend                          Backend
   │                                 │
   │  POST /tasks/:id/process        │
   │─────────────────────────────────►│
   │                                 │ Verify files ✓
   │                                 │ Set status = PROCESSING
   │  200 OK (status: PROCESSING)    │ Start background thread
   │◄─────────────────────────────────│
   │                                 │
   │  Navigate to Tasks List         │ ┌─────────────────────┐
   │                                 │ │ Background Thread   │
   │                                 │ │ - Execute agents    │
   │                                 │ │ - Upload outputs    │
   │                                 │ │ - Update status     │
   │                                 │ └─────────────────────┘
   │                                 │
   │  GET /tasks (from Tasks List)   │
   │─────────────────────────────────►│
   │  Task list with statuses        │
   │◄─────────────────────────────────│
   │                                 │
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

## Async Processing

### V2.1.1 Async Model

In V2.1.1, task processing is **asynchronous**:

1. **Immediate Response**: `POST /tasks/{id}/process` returns immediately with status `PROCESSING`
2. **Background Execution**: Agent execution happens in a background thread on the backend
3. **Frontend Redirect**: Frontend navigates user to Tasks List page after triggering
4. **Progress Tracking**: User tracks task progress from the Tasks List page

### Why Async Processing?

| Benefit               | Description                                                   |
| --------------------- | ------------------------------------------------------------- |
| **No Timeout Issues** | Long-running tasks don't cause HTTP timeouts                  |
| **Better UX**         | User isn't stuck waiting on a loading screen                  |
| **Resumable**         | User can close browser, task continues                        |
| **Scalable**          | Backend can process multiple tasks concurrently               |
| **Visibility**        | Tasks List page shows all tasks with real-time status updates |

### Backend Implementation

```python
@router.post("/{task_id}/process")
async def trigger_processing(task_id: str, background_tasks: BackgroundTasks, ...):
    # 1. Verify files exist
    # 2. Set status to PROCESSING
    # 3. Start background thread for execution
    thread = threading.Thread(target=run_background_task, daemon=True)
    thread.start()

    # 4. Return immediately
    return TaskResponse(status="PROCESSING", message="Processing started...")
```

### Frontend Flow

```typescript
// Simplified TaskProcessing page
const result = await executeTaskFlowAsync(
  {
    toolId,
    agents,
    files,
    parameters,
  },
  token,
  {
    onStep: (step) => updateUI(step),
    onUploadProgress: (key, percent) => updateProgress(percent),
  }
);

// After triggering, show success message
showSuccessMessage("Analysis started! Redirecting to Tasks page...");

// Auto-redirect to Tasks List
setTimeout(() => navigate("/tasks"), 5000);
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
        completed = task.agents_completed_count or 0
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
        "agents_completed": 3
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
            expired_at = NOW()
        WHERE status = 'CREATED'
        AND created_at < NOW() - INTERVAL 15 MINUTE
    """)

    # 2. Expire UPLOADING tasks older than 15 minutes
    await db.execute("""
        UPDATE tasks
        SET status = 'EXPIRED',
            expired_at = NOW()
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
        # Delete entire task folder (inputs + outputs)
        prefix = f"users/{task.user_id}/tasks/{task.task_id}/"
        s3_service.delete_folder(prefix)

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

### Simplified Task Processing Flow (V2.1.1)

The TaskProcessing page now follows a simplified flow:

```typescript
// TaskProcessing.jsx - Simplified Flow
// 1. Create task
// 2. Get upload URLs
// 3. Upload files to S3
// 4. Trigger processing (returns immediately)
// 5. Show success message
// 6. Auto-redirect to Tasks List page

const executeTask = async () => {
  const result = await executeTaskFlowAsync(
    { toolId, agents, files, parameters },
    token,
    {
      onStep: (step, data) => {
        if (step === "created") setTaskId(data.task_id);
        if (step === "triggered") setIsComplete(true);
      },
      onUploadProgress: (key, percent) => setUploadProgress(percent),
    }
  );

  // Success! Navigate to Tasks page
  navigate("/tasks");
};
```

### No Polling Required

Unlike the previous synchronous approach, the frontend does NOT need to poll for status during task creation:

| Previous (V2.1)                        | Current (V2.1.1)                     |
| -------------------------------------- | ------------------------------------ |
| Wait on TaskProcessing page            | Redirect to Tasks List immediately   |
| Poll `GET /tasks/{id}` every 3 seconds | No polling during creation           |
| Show downloads on completion           | View downloads from TaskDetails page |
| User stuck on loading screen           | User can browse, start other tasks   |

### Task Status Tracking

Users track task status from the **Tasks List** page:

```typescript
// TasksList.jsx
const { data: tasks } = useListTasks({ limit: 20 });

// Shows all tasks with real-time status
// PROCESSING tasks can be clicked to view details
// COMPLETED tasks show download button
```

### Complete Upload Flow (Frontend)

```typescript
// 1. Create task
const createResponse = await fetch("/tasks", {
  method: "POST",
  body: JSON.stringify({
    tool_id: "profile-my-data",
    agents: ["unified-profiler", "score-risk"],
  }),
});
const { task_id } = await createResponse.json();

// 2. Get upload URLs
const urlsResponse = await fetch(`/tasks/${task_id}/upload-urls`, {
  method: "POST",
  body: JSON.stringify({
    files: {
      primary: { filename: "data.csv", content_type: "text/csv" },
    },
    has_parameters: true,
  }),
});
const { uploads } = await urlsResponse.json();

// 3. Upload files to B2
await fetch(uploads.primary.url, {
  method: "PUT",
  headers: { "Content-Type": "text/csv" },
  body: primaryFile,
});

// 4. Upload parameters to B2
if (parameters && uploads.parameters) {
  await fetch(uploads.parameters.url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(parameters),
  });
}

// 5. Trigger processing (returns immediately!)
const processResponse = await fetch(`/tasks/${task_id}/process`, {
  method: "POST",
});
// processResponse.status === "PROCESSING"

// 6. Navigate to Tasks List
navigate("/tasks");

// User can later check task status and download results from Tasks List
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
    message: "Please upload your files and parameters",
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
4. **Parameters in S3** - Not stored in database, uploaded like files
5. **Automatic expiry** - Prevent orphaned tasks
6. **Simplified tracking** - Removed redundant metadata
7. **Async processing (V2.1.1)** - Backend processes in background, immediate response to frontend

### Implementation Priority

1. ✅ Basic statuses: CREATED → UPLOADING → QUEUED → PROCESSING → COMPLETED/FAILED
2. ✅ Async processing: Immediate response, background execution
3. ⬜ Progress tracking during PROCESSING
4. ⬜ Timeout & cleanup jobs
5. ⬜ CANCELLED support

---

**Document Status:** Complete  
**Last Updated:** December 20, 2025  
**Version:** 2.1.1
