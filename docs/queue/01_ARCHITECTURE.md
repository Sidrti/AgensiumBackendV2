# Queue System Architecture

**Document Version:** 2.0.0  
**Created:** December 23, 2025  
**Updated:** December 23, 2025  
**Purpose:** Define the complete architecture for migrating from threading to a proper queue-based processing system using Celery and Redis Cloud.

---

## Executive Summary

The current Agensium V2.1 architecture uses Python's `threading.Thread` for background task processing. While functional, this approach has limitations around scalability, reliability, and observability. This document outlines the migration to a production-grade queue system using **Celery** as the task queue and **Redis Cloud** (Upstash or Railway) as the message broker.

### Key Design Decisions

1. **Unified Worker** - Single worker processes all tool types (profile, clean, master)
2. **Redis Cloud** - No self-hosted Redis; use managed service (Upstash recommended)
3. **Reuse Existing Code** - Workers call existing transformers directly, no code duplication
4. **No Docker Required** - Simple deployment without containerization complexity

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Target Architecture](#target-architecture)
3. [Component Design](#component-design)
4. [Data Flow](#data-flow)
5. [Task Lifecycle](#task-lifecycle)
6. [Scalability Model](#scalability-model)
7. [Error Handling Strategy](#error-handling-strategy)
8. [Security Considerations](#security-considerations)

---

## Current State Analysis

### How It Works Now

The current implementation in `api/task_routes.py`:

```python
# Current approach - Background threading
def run_background_task():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_execute_task_background(task_id, user_id))
    finally:
        loop.close()

thread = threading.Thread(target=run_background_task, daemon=True)
thread.start()
```

### Current Limitations

| Issue                     | Impact                               | Severity  |
| ------------------------- | ------------------------------------ | --------- |
| **No Persistence**        | Tasks lost on server restart         | 🔴 High   |
| **No Horizontal Scaling** | All tasks run on single server       | 🔴 High   |
| **Limited Retry**         | Manual retry logic required          | 🟡 Medium |
| **No Task Monitoring**    | Can't see queue depth, worker status | 🟡 Medium |
| **Memory Isolation**      | Bad task can crash entire server     | 🔴 High   |
| **Thread Limits**         | Python GIL limits true parallelism   | 🟡 Medium |
| **No Rate Limiting**      | Can overwhelm system with tasks      | 🟡 Medium |
| **No Priority Queues**    | All tasks treated equally            | 🟢 Low    |

### Current Task Status Flow

```
CREATED → UPLOADING → PROCESSING → COMPLETED/FAILED
                         ↑
                   (Background Thread)
```

**Note:** The `QUEUED` status exists in the model but is skipped in current implementation.

---

## Target Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AGENSIUM QUEUE ARCHITECTURE (V2)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                         FRONTEND LAYER                             │     │
│   │                                                                    │     │
│   │   React App ──► POST /tasks ──► POST /tasks/{id}/process          │     │
│   │                                          │                         │     │
│   │   GET /tasks/{id} ◄─── Poll for status ◄─┘                        │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                      │                                       │
│                                      ▼                                       │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                          API LAYER                                 │     │
│   │                                                                    │     │
│   │   FastAPI ────► Celery.send_task() ────► Redis Cloud (Enqueue)    │     │
│   │      │                                                             │     │
│   │      └── Update Task: status = QUEUED                             │     │
│   │                                                                    │     │
│   │   Database (MySQL) ◄─── Task status queries                       │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                      │                                       │
│                                      ▼                                       │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                  MESSAGE BROKER (REDIS CLOUD)                      │     │
│   │                                                                    │     │
│   │              Upstash / Railway Managed Redis                       │     │
│   │                                                                    │     │
│   │   ┌───────────────────────────────────────────────────────────┐   │     │
│   │   │                    Default Queue                           │   │     │
│   │   │   All tasks: profile, clean, master analysis              │   │     │
│   │   └───────────────────────────────────────────────────────────┘   │     │
│   │                                                                    │     │
│   │   Result Backend: Stores task results (TTL: 24h)                  │     │
│   │   Connection: rediss:// (TLS encrypted)                          │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                      │                                       │
│                                      ▼                                       │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                       WORKER LAYER (CELERY)                        │     │
│   │                                                                    │     │
│   │   ┌───────────────────────────────────────────────────────────┐   │     │
│   │   │                   UNIFIED WORKER                           │   │     │
│   │   │                                                            │   │     │
│   │   │   process_analysis(task_id, user_id)                      │   │     │
│   │   │           │                                                │   │     │
│   │   │           ▼                                                │   │     │
│   │   │   ┌───────────────────────────────────────────────────┐   │   │     │
│   │   │   │  Route by tool_id:                                │   │   │     │
│   │   │   │                                                    │   │   │     │
│   │   │   │  profile-my-data → profile_transformer            │   │   │     │
│   │   │   │  clean-my-data   → clean_transformer              │   │   │     │
│   │   │   │  master-my-data  → master_transformer             │   │   │     │
│   │   │   └───────────────────────────────────────────────────┘   │   │     │
│   │   │                                                            │   │     │
│   │   │   Workers can be scaled horizontally (1, 2, 4, etc.)      │   │     │
│   │   └───────────────────────────────────────────────────────────┘   │     │
│   │                                                                    │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                      │                                       │
│                                      ▼                                       │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                       STORAGE LAYER                                │     │
│   │                                                                    │     │
│   │   ┌─────────────────┐      ┌─────────────────────────────────┐   │     │
│   │   │    MySQL        │      │       Backblaze B2 (S3)          │   │     │
│   │   │  (PlanetScale   │      │                                  │   │     │
│   │   │   or Railway)   │      │ - Input files                   │   │     │
│   │   │                 │      │ - Parameters.json               │   │     │
│   │   │ - Task records  │      │ - Output files                  │   │     │
│   │   │ - User data     │      │ - Reports (.xlsx, .json)        │   │     │
│   │   │ - Billing       │      │                                  │   │     │
│   │   └─────────────────┘      └─────────────────────────────────┘   │     │
│   │                                                                    │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                       MONITORING (OPTIONAL)                        │     │
│   │                                                                    │     │
│   │   Flower Dashboard ─── Task status, queue depth, worker health    │     │
│   │                                                                    │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why Unified Worker?

The existing transformers already have identical patterns:

```python
# All three transformers follow the same structure:
def run_*_analysis_v2_1(input_file, selected_agents, ...):
    # 1. Check billing balance
    # 2. Loop through selected agents
    # 3. Execute each agent via _execute_agent()
    # 4. Aggregate results
    # 5. Generate outputs
```

**The only difference is which agents are available in `_execute_agent()`.**

So instead of creating separate worker classes, the unified worker:

1. Reads the task's `tool_id` from the database
2. Routes to the appropriate existing transformer
3. Done!

---

## Component Design

### 1. Celery Application (`celery_celery_queue/celery_app.py`)

Central configuration for Celery workers:

```python
import os
from celery import Celery

# Redis Cloud URL (Upstash or Railway)
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery('agensium')

app.conf.update(
    broker_url=redis_url,
    result_backend=redis_url,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=1800,  # 30 minutes
    task_soft_time_limit=1500,  # 25 minutes
    result_expires=86400,  # 24 hours
    worker_prefetch_multiplier=1,
)

# Auto-discover tasks
app.autodiscover_tasks(['queue'])
```

### 2. Task Definition (`celery_queue/tasks.py`)

Single unified task that routes to existing transformers:

```python
from celery_queue.celery_app import app
from db.database import get_db
from db.models import Task
from transformers.profile_my_data_transformer import run_profile_analysis_v2_1
from transformers.clean_my_data_transformer import run_clean_analysis_v2_1
from transformers.master_my_data_transformer import run_master_analysis_v2_1

TRANSFORMERS = {
    "profile-my-data": run_profile_analysis_v2_1,
    "clean-my-data": run_clean_analysis_v2_1,
    "master-my-data": run_master_analysis_v2_1,
}

@app.task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    name='queue.tasks.process_analysis'
)
def process_analysis(self, task_id: str, user_id: int):
    """
    Unified task for all analysis types.
    Routes to the appropriate transformer based on tool_id.
    """
    db = next(get_db())
    try:
        # Get task and determine which transformer to use
        task = db.query(Task).filter(Task.id == task_id).first()
        tool_id = task.tool_id

        # Update status
        task.status = "PROCESSING"
        db.commit()

        # Route to appropriate transformer
        transformer = TRANSFORMERS.get(tool_id)
        if not transformer:
            raise ValueError(f"Unknown tool_id: {tool_id}")

        # Execute! (transformers handle everything else)
        result = transformer(
            input_file=task.input_s3_key,
            selected_agents=task.selected_agents,
            user_id=user_id,
            task_id=task_id,
        )

        # Update task on success
        task.status = "COMPLETED"
        task.result = result
        db.commit()

    except Exception as e:
        task.status = "FAILED"
        task.error = str(e)
        db.commit()
        raise
    finally:
        db.close()
```

### 3. Queue Module Structure (Simplified)

```
celery_queue/
├── __init__.py           # Module initialization
├── celery_app.py         # Celery application config
├── celery_config.py      # Settings (optional, can be in celery_app)
└── tasks.py              # Single unified task definition
```

**That's it!** No separate worker classes needed because the transformers already contain all the logic.

---

## Data Flow

### Task Submission Flow

```
1. User triggers processing
   │
   ▼
2. POST /tasks/{id}/process
   │
   ├─► Verify files exist in S3
   │
   ├─► Update task status: QUEUED
   │
   ├─► Celery send_task('process_analysis', args=[task_id, user_id])
   │
   └─► Return immediately: {"status": "QUEUED", "message": "..."}

3. Redis receives task message
   │
   └─► Task added to queue with metadata

4. Celery worker picks up task
   │
   ├─► Update task status: PROCESSING
   │
   ├─► Execute agent chain
   │   ├─► Read inputs from S3
   │   ├─► Run profile/clean/master analysis
   │   ├─► Upload outputs to S3
   │   └─► Record progress updates
   │
   ├─► On success: Update task status: COMPLETED
   │
   └─► On failure: Update task status: FAILED

5. Frontend polls GET /tasks/{id}
   │
   └─► Returns current status and progress
```

### Message Structure

```json
{
  "id": "celery-task-uuid",
  "task": "queue.tasks.process_analysis",
  "args": ["550e8400-e29b-41d4-a716-446655440000", 123],
  "kwargs": {},
  "retries": 0,
  "eta": null,
  "expires": null
}
```

---

## Task Lifecycle

### Updated Status Flow

```
┌─────────┐     ┌───────────┐     ┌────────┐     ┌────────────┐     ┌───────────┐
│ CREATED │ ──► │ UPLOADING │ ──► │ QUEUED │ ──► │ PROCESSING │ ──► │ COMPLETED │
└─────────┘     └───────────┘     └────────┘     └────────────┘     └───────────┘
                      │                │                │
                      ▼                │                ▼
               ┌──────────────┐        │         ┌──────────┐
               │ UPLOAD_FAILED│ ◄──────┘         │  FAILED  │
               └──────────────┘                  └──────────┘
                                                       │
                                                       ▼
                                                ┌──────────────┐
                                                │  CANCELLED   │
                                                └──────────────┘
```

### Status Transitions with Queue

| Current Status | Action               | New Status | Actor  |
| -------------- | -------------------- | ---------- | ------ |
| UPLOADING      | POST /process        | QUEUED     | API    |
| QUEUED         | Worker picks up task | PROCESSING | Worker |
| PROCESSING     | Analysis completes   | COMPLETED  | Worker |
| PROCESSING     | Analysis fails       | FAILED     | Worker |
| PROCESSING     | User cancels         | CANCELLED  | API    |
| QUEUED         | Task expires (24h)   | EXPIRED    | Worker |

---

## Scalability Model

### Horizontal Scaling

```
                    Load Balancer
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ API 1   │    │ API 2   │    │ API 3   │
    └────┬────┘    └────┬────┘    └────┬────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │   Redis Cloud    │ (Upstash / Railway)
              │   (Managed)      │
              └────────┬─────────┘
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
     ▼                 ▼                 ▼
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Unified  │    │ Unified  │    │ Unified  │
│ Worker 1 │    │ Worker 2 │    │ Worker N │
│          │    │          │    │          │
│ Handles  │    │ Handles  │    │ Handles  │
│ all tools│    │ all tools│    │ all tools│
└──────────┘    └──────────┘    └──────────┘
```

### Scaling Guidelines

| Metric        | Threshold   | Action                   |
| ------------- | ----------- | ------------------------ |
| Queue depth   | > 50 tasks  | Add workers              |
| Avg wait time | > 5 minutes | Add workers              |
| Worker CPU    | > 80%       | Add workers or upgrade   |
| Worker memory | > 70%       | Investigate memory leaks |

### Worker Scaling Formula

```
Recommended Workers = (Peak Tasks/Hour × Avg Task Duration in Hours) × 1.5
```

Example:

- Peak: 100 tasks/hour
- Avg duration: 2 minutes (0.033 hours)
- Workers = (100 × 0.033) × 1.5 = 5 workers

### Scaling in Practice

```powershell
# Start with 1 worker
celery -A celery_queue.celery_app worker --loglevel=info --concurrency=4

# Add more workers as needed (run in separate terminals/services)
celery -A celery_queue.celery_app worker --loglevel=info --concurrency=4
celery -A celery_queue.celery_app worker --loglevel=info --concurrency=4
```

On Railway/Render, just add more worker service instances.

---

## Error Handling Strategy

### Retry Configuration

```python
@app.task(
    autoretry_for=(
        ConnectionError,    # Network issues
        TimeoutError,       # S3/DB timeouts
        TransientError,     # Temporary failures
    ),
    retry_backoff=True,
    retry_backoff_max=600,  # Max 10 minutes between retries
    retry_jitter=True,      # Add randomness to prevent thundering herd
    retry_kwargs={'max_retries': 3},
)
def process_analysis(self, task_id, user_id):
    ...
```

### Error Categories

| Error Type        | Retry | Action                           |
| ----------------- | ----- | -------------------------------- |
| S3 Connection     | Yes   | Exponential backoff              |
| DB Connection     | Yes   | Exponential backoff              |
| Billing Error     | No    | Mark failed, notify user         |
| Data Format Error | No    | Mark failed, store error details |
| Agent Error       | No    | Mark failed, store agent output  |
| Timeout (Soft)    | Yes   | Re-queue with higher priority    |
| Timeout (Hard)    | No    | Mark failed, alert ops           |
| Worker Killed     | Yes   | Auto-requeue by Celery           |

### Dead Letter Queue (DLQ)

Failed tasks after all retries go to DLQ:

```python
task_routes = {
    'queue.tasks.process_analysis': {
        'queue': 'default',
        'dead_letter_queue': 'dlq',
    },
}
```

---

## Security Considerations

### Redis Cloud Security

Redis Cloud providers (Upstash, Railway) handle security:

1. **Authentication**: Password included in connection URL
2. **TLS Encryption**: Always use `rediss://` (with double 's')
3. **Network Isolation**: Managed by provider
4. **No Maintenance**: Provider handles updates and patches

### Connection URL Format

```env
# TLS-encrypted connection (note the 'rediss://' with double 's')
REDIS_URL=rediss://default:PASSWORD@host.upstash.io:6379
```

### Task Data Security

1. **Minimize Sensitive Data**:

   - Only pass task_id and user_id
   - Never pass credentials or file contents

2. **Audit Logging**:

   ```python
   @app.task
   def process_analysis(self, task_id, user_id):
       logger.info(f"Starting task {task_id} for user {user_id}")
       # ... processing
       logger.info(f"Completed task {task_id}")
   ```

---

## Benefits of New Architecture

| Aspect             | Current (Threading)   | New (Celery + Redis Cloud)    |
| ------------------ | --------------------- | ----------------------------- |
| **Reliability**    | Tasks lost on restart | Tasks persist in Redis        |
| **Scalability**    | Single server         | N workers across N servers    |
| **Monitoring**     | None                  | Flower dashboard              |
| **Error Recovery** | Manual                | Automatic retries             |
| **Isolation**      | Shared memory         | Process isolation             |
| **Maintenance**    | Self-managed Redis    | Zero - managed by Upstash     |
| **Setup Time**     | Complex               | 5 minutes with Redis Cloud    |
| **Cost**           | Server + Redis        | Pay-per-use (free tier avail) |

---

## Next Steps

1. **Review this architecture** with team
2. **Proceed to** [02_CELERY_SETUP.md](02_CELERY_SETUP.md) for Celery installation
3. **Proceed to** [03_REDIS_SETUP.md](03_REDIS_SETUP.md) for Redis Cloud setup
4. **Implement** following [05_MIGRATION_GUIDE.md](05_MIGRATION_GUIDE.md)

---

## References

- [Celery Documentation](https://docs.celeryq.dev/)
- [Upstash Redis](https://upstash.com/)
- [Railway](https://railway.app/)
- [V2_USER_JOURNEY.md](../V2_USER_JOURNEY.md) - Original vision document

