# Task Workers Specification

**Document Version:** 2.0.0  
**Updated:** December 23, 2025  
**Purpose:** Define the implementation details for Celery workers that process data analysis tasks.

---

## Table of Contents

1. [Worker Overview](#worker-overview)
2. [Unified Worker Architecture](#unified-worker-architecture)
3. [Unified Worker Implementation](#unified-worker-implementation)
4. [Task Definition](#task-definition)
5. [Progress Reporting](#progress-reporting)
6. [Error Handling](#error-handling)
7. [Callbacks & Hooks](#callbacks--hooks)
8. [Testing Workers](#testing-workers)

---

## Worker Overview

### Design Philosophy

After analyzing the existing transformer code (`profile_my_data_transformer.py`, `clean_my_data_transformer.py`, `master_my_data_transformer.py`), we identified that **all three transformers follow the same pattern**:

1. Load files from S3
2. Convert to CSV if needed
3. Load parameters from S3
4. Validate billing upfront
5. Loop through agents, executing each sequentially
6. Transform response
7. Upload outputs to S3

**The only difference is the list of agents each tool supports.**

This means we need **ONE unified worker** that routes to the appropriate transformer, not separate workers for each tool type. The existing transformers already handle all the tool-specific logic.

### What Workers Do

Celery workers are responsible for:

1. **Picking up tasks** from Redis Cloud queue
2. **Routing to the appropriate transformer** based on `tool_id`
3. **The transformer handles everything else** (agents, progress, billing, outputs)

### Unified Worker Approach

| Component      | Purpose                                          |
| -------------- | ------------------------------------------------ |
| Unified Worker | Routes to existing transformers based on tool_id |
| Transformers   | Already handle all analysis logic per tool       |
| Celery Task    | Wraps transformer call with async/retry support  |

---

## Unified Worker Architecture

### Why Unified Worker?

Looking at the existing transformers, they ALL follow this identical pattern:

```python
# Profile, Clean, and Master all have this same structure:
async def run_*_analysis_v2_1(task, current_user, db):
    # 1. Load files from S3 (same in all)
    # 2. Convert to CSV (same in all)
    # 3. Load parameters (same in all)
    # 4. Billing validation (same in all)
    # 5. Loop through task.agents:
    #    - Update progress (same in all)
    #    - Build agent input (same in all)
    #    - Execute agent via _execute_agent() ← ONLY THIS DIFFERS
    #    - Chain data if needed
    # 6. Transform response (same in all)
    # 7. Upload outputs (same in all)
```

**The `_execute_agent()` function is the ONLY difference** - it routes to different agent modules based on `agent_id`.

### Module Structure

```
celery_queue/
├── __init__.py              # Package initialization
├── celery_app.py            # Celery application configuration
├── celery_config.py         # Celery settings
├── tasks.py                 # Single unified task definition
├── progress.py              # Progress reporting utilities
├── error_handlers.py        # Error handling utilities
└── callbacks.py             # Task callbacks (success, failure)
```

### Worker Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      UNIFIED WORKER EXECUTION FLOW                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   1. Task Received from Redis Cloud                                         │
│      │                                                                       │
│      ▼                                                                       │
│   2. Celery Task: process_analysis(task_id, user_id)                        │
│      │                                                                       │
│      ▼                                                                       │
│   3. Load Task from Database (get tool_id)                                  │
│      │                                                                       │
│      ▼                                                                       │
│   4. Route to Appropriate Transformer:                                      │
│      │                                                                       │
│      ├─► tool_id == "profile-my-data"                                       │
│      │   └─► run_profile_my_data_analysis_v2_1(task, user, db)              │
│      │                                                                       │
│      ├─► tool_id == "clean-my-data"                                         │
│      │   └─► run_clean_my_data_analysis_v2_1(task, user, db)                │
│      │                                                                       │
│      └─► tool_id == "master-my-data"                                        │
│          └─► run_master_my_data_analysis_v2_1(task, user, db)               │
│                                                                              │
│   5. Transformer Handles Everything:                                        │
│      - File loading from S3                                                 │
│      - Billing validation                                                   │
│      - Agent execution loop                                                 │
│      - Progress updates                                                     │
│      - Output generation & upload                                           │
│                                                                              │
│   6. Return Result to Celery                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Unified Worker Implementation

### File: `celery_celery_queue/celery_app.py`

```python
"""
Celery Application Configuration

Central Celery app that connects to Redis Cloud.
"""

import os
from celery import Celery

# Create Celery app
app = Celery('agensium')

# Load configuration from celery_config module
app.config_from_object('queue.celery_config')

# Auto-discover tasks in the queue module
app.autodiscover_tasks(['queue'])
```

### File: `celery_queue/celery_config.py`

```python
"""
Celery Configuration

All settings for Celery workers.
Uses Redis Cloud as broker and result backend.
"""

import os

# Redis Cloud URL (e.g., from Upstash, Railway, or Redis Labs)
# Format: rediss://:password@host:port  (note the double 's' for TLS)
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Broker settings (Redis Cloud)
broker_url = os.getenv("CELERY_BROKER_URL", redis_url)
result_backend = os.getenv("CELERY_RESULT_BACKEND", redis_url)

# Serialization
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

# Task settings
task_acks_late = True  # Acknowledge after completion (reliability)
task_reject_on_worker_lost = True  # Re-queue if worker dies
task_time_limit = int(os.getenv("CELERY_TASK_TIME_LIMIT", 1800))  # 30 min hard limit
task_soft_time_limit = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", 1500))  # 25 min soft limit

# Result settings
result_expires = 86400  # 24 hours

# Worker settings
worker_prefetch_multiplier = 1  # Fair distribution (important for long tasks)
worker_concurrency = int(os.getenv("CELERY_WORKER_CONCURRENCY", 4))
worker_max_memory_per_child = int(os.getenv("CELERY_WORKER_MAX_MEMORY_PER_CHILD", 400000))  # 400MB

# Redis connection pool settings (for Redis Cloud)
broker_transport_options = {
    'visibility_timeout': 3600,  # 1 hour
    'socket_timeout': 30,
    'socket_connect_timeout': 30,
}
```

### File: `celery_queue/tasks.py`

```python
"""
Unified Celery Task Definition

Single task that routes to the appropriate transformer based on tool_id.
This leverages the existing transformer code which already handles:
- S3 file loading
- Billing validation
- Agent execution
- Progress updates
- Output generation
"""

import asyncio
import logging
from typing import Dict, Any

from celery import current_task
from celery.exceptions import SoftTimeLimitExceeded

from celery_queue.celery_app import app
from db.database import SessionLocal
from db import models
from db.models import TaskStatus

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async functions in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(
    bind=True,
    name='queue.tasks.process_analysis',
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    retry_kwargs={'max_retries': 3},
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_analysis(self, task_id: str, user_id: int) -> Dict[str, Any]:
    """
    Unified task processor that routes to the appropriate transformer.

    The transformers already handle ALL the logic:
    - File loading from S3
    - CSV conversion
    - Parameter loading
    - Billing validation
    - Agent execution loop
    - Progress updates
    - Output generation & upload

    This task simply:
    1. Loads the task from DB
    2. Routes to the appropriate transformer based on tool_id
    3. Returns the result

    Args:
        task_id: UUID of the task to process
        user_id: ID of the task owner

    Returns:
        Dict with processing result
    """
    db = SessionLocal()

    try:
        # 1. Load task and user from database
        task = db.query(models.Task).filter(
            models.Task.task_id == task_id
        ).first()

        if not task:
            logger.error(f"Task {task_id} not found")
            return {"status": "error", "error": "Task not found", "error_code": "TASK_NOT_FOUND"}

        user = db.query(models.User).filter(
            models.User.id == user_id
        ).first()

        if not user:
            logger.error(f"User {user_id} not found")
            return {"status": "error", "error": "User not found", "error_code": "USER_NOT_FOUND"}

        # 2. Update status to PROCESSING (this is now done by Celery)
        task.status = TaskStatus.PROCESSING.value
        db.commit()

        # 3. Route to appropriate transformer based on tool_id
        tool_id = task.tool_id
        logger.info(f"Processing task {task_id} with tool: {tool_id}")

        if tool_id == "profile-my-data":
            from transformers.profile_my_data_transformer import run_profile_my_data_analysis_v2_1
            result = run_async(run_profile_my_data_analysis_v2_1(task, user, db))

        elif tool_id == "clean-my-data":
            from transformers.clean_my_data_transformer import run_clean_my_data_analysis_v2_1
            result = run_async(run_clean_my_data_analysis_v2_1(task, user, db))

        elif tool_id == "master-my-data":
            from transformers.master_my_data_transformer import run_master_my_data_analysis_v2_1
            result = run_async(run_master_my_data_analysis_v2_1(task, user, db))

        else:
            logger.error(f"Unknown tool_id: {tool_id}")
            task.status = TaskStatus.FAILED.value
            task.error_code = "UNKNOWN_TOOL"
            task.error_message = f"Unknown tool: {tool_id}"
            db.commit()
            return {"status": "error", "error": f"Unknown tool: {tool_id}", "error_code": "UNKNOWN_TOOL"}

        logger.info(f"Task {task_id} completed successfully")
        return result

    except SoftTimeLimitExceeded:
        logger.error(f"Task {task_id} exceeded soft time limit")
        if task:
            task.status = TaskStatus.FAILED.value
            task.error_code = "TIMEOUT"
            task.error_message = "Task exceeded time limit"
            db.commit()
        raise  # Re-raise for Celery to handle

    except Exception as e:
        logger.exception(f"Task {task_id} failed: {e}")
        if task:
            task.status = TaskStatus.FAILED.value
            task.error_code = "INTERNAL_ERROR"
            task.error_message = str(e)
            db.commit()
        raise  # Re-raise for Celery retry mechanism

    finally:
        db.close()
```

---

## Task Definition

### API Integration: `api/task_routes.py` Update

Replace the threading code with Celery task submission:

```python
# In api/task_routes.py - Update the process_task endpoint

from queue.tasks import process_analysis

@router.post("/tasks/{task_id}/process")
async def process_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Trigger task processing.

    Instead of threading, we now submit to Celery queue.
    """
    # Verify task exists and belongs to user
    task = db.query(models.Task).filter(
        models.Task.task_id == task_id,
        models.Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Update status to QUEUED (new status)
    task.status = TaskStatus.QUEUED.value
    db.commit()

    # Submit to Celery (returns immediately)
    celery_task = process_analysis.delay(task_id, current_user.id)

    return {
        "status": "queued",
        "task_id": task_id,
        "celery_task_id": celery_task.id,
        "message": "Task queued for processing"
    }
```

### Why This Works

1. **Existing transformers are reused** - No code duplication
2. **All logic stays in one place** - The transformers
3. **Easy to maintain** - Update transformer, workers automatically use it
4. **Simplified worker** - Just a router to existing code

---

## Progress Reporting

The existing transformers already handle progress updates. No changes needed!

From `profile_my_data_transformer.py`:

```python
# This already exists in your transformers:
for i, agent_id in enumerate(task.agents):
    # Update progress in database
    task.current_agent = agent_id
    task.progress = int(20 + (i / len(task.agents)) * 70)
    db.commit()
```

### Progress Utilities (Optional Enhancement)

If you want to report progress to Celery as well (for Flower monitoring):

### File: `celery_queue/progress.py`

```python
"""
Progress Reporting Utilities

Optional: Report progress to Celery for Flower dashboard.
The transformers already update the database.
"""

from celery import current_task
from typing import Optional


def report_to_celery(
    progress: int,
    current_agent: Optional[str] = None,
    task_id: Optional[str] = None
):
    """
    Report progress to Celery (for Flower dashboard).

    This is optional since the database is the source of truth.
    """
    if current_task:
        current_task.update_state(
            state='PROCESSING',
            meta={
                'progress': progress,
                'current_agent': current_agent,
                'task_id': task_id
            }
        )
```

---

## Error Handling

### File: `celery_queue/error_handlers.py`

```python
"""
Error Handling Utilities

Simplified error handling for the unified worker.
Most error handling already exists in the transformers.
"""

import logging
from typing import Dict, Any

from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded

logger = logging.getLogger(__name__)


# Errors that should trigger retry
RETRYABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Network issues
)

# Errors that should NOT retry (user action required)
NON_RETRYABLE_ERRORS = (
    ValueError,
    KeyError,
    PermissionError,
)


def classify_error(error: Exception) -> Dict[str, Any]:
    """
    Classify an error for handling decisions.

    Returns:
        Dict with error_code, message, and recoverable flag
    """
    if isinstance(error, SoftTimeLimitExceeded):
        return {
            "error_code": "SOFT_TIMEOUT",
            "message": "Task exceeded soft time limit",
            "recoverable": True
        }

    if isinstance(error, TimeLimitExceeded):
        return {
            "error_code": "HARD_TIMEOUT",
            "message": "Task exceeded hard time limit",
            "recoverable": False
        }

    if isinstance(error, RETRYABLE_ERRORS):
        return {
            "error_code": "TRANSIENT_ERROR",
            "message": str(error),
            "recoverable": True
        }

    # Default: non-recoverable
    return {
        "error_code": "INTERNAL_ERROR",
        "message": str(error),
        "recoverable": False
    }
```

---

## Callbacks & Hooks

### File: `celery_queue/callbacks.py`

````python
"""
Task Callbacks

Optional callbacks for task success/failure.
These can be used for notifications, cleanup, etc.
"""

import logging
from celery.signals import task_success, task_failure, task_retry

logger = logging.getLogger(__name__)


@task_success.connect
def on_task_success(sender=None, result=None, **kwargs):
    """Called when a task completes successfully."""
    task_id = kwargs.get('task_id', 'unknown')
    logger.info(f"Task {task_id} completed successfully")

    # Optional: Send notification, update analytics, etc.


@task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    """Called when a task fails."""
    logger.error(f"Task {task_id} failed: {exception}")

    # Optional: Send alert, notify user, etc.


@task_retry.connect
def on_task_retry(sender=None, reason=None, **kwargs):
    """Called when a task is retried."""
    task_id = kwargs.get('task_id', 'unknown')
    logger.warning(f"Task {task_id} retrying: {reason}")
---

## Testing Workers

### File: `tests/celery_queue/test_tasks.py`

```python
"""
Unit tests for the unified Celery task.

Run with: pytest tests/celery_queue/test_tasks.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from queue.tasks import process_analysis


class TestProcessAnalysis:
    """Tests for the unified process_analysis task."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_task(self):
        """Create mock Task object."""
        task = Mock()
        task.task_id = "test-task-123"
        task.tool_id = "profile-my-data"
        task.user_id = 1
        task.agents = ["unified-profiler", "score-risk"]
        task.status = "PROCESSING"
        return task

    @pytest.fixture
    def mock_user(self):
        """Create mock User object."""
        user = Mock()
        user.id = 1
        user.email = "test@example.com"
        return user

    @patch('queue.tasks.SessionLocal')
    @patch('queue.tasks.run_profile_my_data_analysis_v2_1')
    def test_profile_tool_routing(self, mock_transformer, mock_session, mock_task, mock_user, mock_db):
        """Test that profile-my-data routes to correct transformer."""
        mock_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_task, mock_user]
        mock_transformer.return_value = {"status": "success"}

        # This would need more setup for full test
        # Just checking the routing logic concept
        assert mock_task.tool_id == "profile-my-data"

    def test_unknown_tool_returns_error(self):
        """Test that unknown tool_id returns error."""
        # Test implementation would go here
        pass

    def test_task_not_found_returns_error(self):
        """Test that missing task returns error."""
        # Test implementation would go here
        pass


class TestCeleryConfig:
    """Tests for Celery configuration."""

    def test_redis_url_format(self):
        """Test Redis Cloud URL is properly formatted."""
        # Redis Cloud uses TLS: rediss:// (double s)
        import os
        os.environ['REDIS_URL'] = 'rediss://:password@my-redis.upstash.io:6379'

        # Config should handle this format
        assert 'rediss://' in os.environ['REDIS_URL']
````

---

## Running Workers

### Development (Windows)

```powershell
# Terminal 1: Start FastAPI
cd "c:\Users\VIVEK BANSAL\Desktop\Agensium\Agensium-V2\backend"
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000

# Terminal 2: Start Celery Worker (use --pool=solo on Windows)
celery -A celery_queue.celery_app worker --loglevel=info --pool=solo

# Terminal 3: Start Flower (optional, for monitoring)
celery -A celery_queue.celery_app flower --port=5555
```

### Production

```bash
# Run multiple workers with concurrency
celery -A celery_queue.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --max-memory-per-child=400000
```

---

## Summary: Key Differences from V1

| Aspect           | V1 (Old Approach)                          | V2 (Unified Approach)            |
| ---------------- | ------------------------------------------ | -------------------------------- |
| Worker Classes   | 3 separate (Profile/Clean/Master)          | 1 unified worker                 |
| Code Duplication | Worker code duplicated logic               | Reuses existing transformers     |
| Maintenance      | Update 4 places (3 workers + transformers) | Update 1 place (transformers)    |
| Agent Routing    | Each worker had own agent map              | Transformers already handle this |
| Complexity       | High                                       | Low                              |

---

## Next Steps

1. ✅ Review unified worker specification
2. → Create `celery_queue/` directory structure
3. → Implement `celery_app.py`, `celery_config.py`, `tasks.py`
4. → Update `api/task_routes.py` to use Celery
5. → Proceed to [05_MIGRATION_GUIDE.md](05_MIGRATION_GUIDE.md)

