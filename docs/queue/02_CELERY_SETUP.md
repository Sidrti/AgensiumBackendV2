# Celery Setup Guide

**Document Version:** 1.0.0  
**Created:** December 23, 2025  
**Purpose:** Step-by-step guide for setting up Celery in the Agensium backend.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration Files](#configuration-files)
4. [Celery App Setup](#celery-app-setup)
5. [Task Definitions](#task-definitions)
6. [Running Workers](#running-workers)
7. [Testing the Setup](#testing-the-setup)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before setting up Celery, ensure you have:

- ✅ Python 3.10+ installed
- ✅ Virtual environment activated (`.venv`)
- ✅ Redis installed and running (see [03_REDIS_SETUP.md](03_REDIS_SETUP.md))
- ✅ Backend project running successfully

---

## Installation

### Step 1: Add Dependencies to requirements.txt

Add the following packages to `requirements.txt`:

```txt
# Task Queue - Celery
celery[redis]>=5.3.0
flower>=2.0.0
redis>=5.0.0
```

### Step 2: Install Dependencies

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install new dependencies
pip install celery[redis] flower redis
```

### Step 3: Verify Installation

```powershell
# Check Celery version
celery --version
# Expected: celery 5.x.x

# Check Redis client
python -c "import redis; print(redis.__version__)"
# Expected: 5.x.x
```

---

## Configuration Files

### File: `celery_config.py`

Create this file in the backend root directory:

```python
"""
Celery Configuration for Agensium Backend

This configuration is optimized for data processing tasks with the following
characteristics:
- Long-running tasks (up to 30 minutes)
- Memory-intensive operations (data analysis)
- Need for reliable execution with retries
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# BROKER & BACKEND CONFIGURATION
# =============================================================================

# Redis as message broker
broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

# Redis as result backend
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# =============================================================================
# SERIALIZATION
# =============================================================================

# Use JSON for human-readable messages
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

# Ensure timezone consistency
timezone = "UTC"
enable_utc = True

# =============================================================================
# TASK EXECUTION SETTINGS
# =============================================================================

# Acknowledge task only after completion (for reliability)
task_acks_late = True

# Re-queue task if worker is killed mid-execution
task_reject_on_worker_lost = True

# Hard time limit (kills task after this)
task_time_limit = 1800  # 30 minutes

# Soft time limit (raises SoftTimeLimitExceeded exception)
task_soft_time_limit = 1500  # 25 minutes

# Track task state changes
task_track_started = True

# Ignore result by default (enable per-task if needed)
task_ignore_result = False

# =============================================================================
# RESULT SETTINGS
# =============================================================================

# Results expire after 24 hours
result_expires = 86400

# Store extended task metadata
result_extended = True

# =============================================================================
# WORKER SETTINGS
# =============================================================================

# Number of concurrent workers per process
# For CPU-bound tasks (data analysis), set to number of cores
worker_concurrency = int(os.getenv("CELERY_CONCURRENCY", 4))

# Prefetch only 1 task at a time (fair distribution)
worker_prefetch_multiplier = 1

# Maximum tasks per worker before restart (prevent memory leaks)
worker_max_tasks_per_child = 50

# Log level
worker_log_format = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
worker_task_log_format = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s"

# =============================================================================
# QUEUE CONFIGURATION
# =============================================================================

# Define task queues
task_queues = {
    "default": {
        "exchange": "default",
        "routing_key": "default",
    },
    "high_priority": {
        "exchange": "high_priority",
        "routing_key": "high_priority",
    },
    "low_priority": {
        "exchange": "low_priority",
        "routing_key": "low_priority",
    },
}

# Default queue
task_default_queue = "default"
task_default_exchange = "default"
task_default_routing_key = "default"

# =============================================================================
# RETRY SETTINGS
# =============================================================================

# Default retry delay (can be overridden per task)
task_default_retry_delay = 60  # 1 minute

# Enable retry backoff
task_retry_backoff = True
task_retry_backoff_max = 600  # Max 10 minutes between retries
task_retry_jitter = True  # Add randomness to prevent thundering herd

# =============================================================================
# BEAT SCHEDULER (for periodic tasks)
# =============================================================================

# Beat schedule - add periodic tasks here
beat_schedule = {
    "cleanup-expired-tasks": {
        "task": "queue.tasks.cleanup_expired_tasks",
        "schedule": 900.0,  # Every 15 minutes
    },
    "health-check": {
        "task": "queue.tasks.health_check",
        "schedule": 60.0,  # Every minute
    },
}

# =============================================================================
# SECURITY SETTINGS (for production)
# =============================================================================

# Enable SSL for Redis in production
# broker_use_ssl = {
#     'ssl_cert_reqs': ssl.CERT_REQUIRED,
#     'ssl_ca_certs': '/path/to/ca.pem',
# }

# =============================================================================
# MONITORING
# =============================================================================

# Enable sending task-sent events for Flower
worker_send_task_events = True
task_send_sent_event = True
```

---

## Celery App Setup

### File: `celery_app.py`

Create this file in the backend root directory:

```python
"""
Celery Application for Agensium Backend

This module initializes the Celery application and configures it to
auto-discover tasks from the queue module.

Usage:
    # Start worker
    celery -A celery_app worker --loglevel=info

    # Start beat scheduler
    celery -A celery_app beat --loglevel=info

    # Start Flower monitoring
    celery -A celery_app flower --port=5555
"""

import os
import sys
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Create Celery app
app = Celery("agensium")

# Load configuration from celery_config.py
app.config_from_object("celery_config")

# Auto-discover tasks in these modules
app.autodiscover_tasks([
    "queue",        # Main task module
    "queue.tasks",  # Task definitions
])


# =============================================================================
# OPTIONAL: Configure task error handling
# =============================================================================

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery connectivity."""
    print(f"Request: {self.request!r}")
    return {"status": "ok", "task_id": self.request.id}


# =============================================================================
# STARTUP HOOKS
# =============================================================================

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Set up periodic tasks after configuration."""
    print("✓ Celery periodic tasks configured")


@app.on_after_finalize.connect
def setup_direct_queue(sender, **kwargs):
    """Set up direct queue after finalization."""
    print("✓ Celery queues finalized")


if __name__ == "__main__":
    app.start()
```

---

## Task Definitions

### File: `queue/__init__.py`

```python
"""
Queue module for Celery tasks.

This module contains all task definitions for the Agensium backend.
Tasks are automatically discovered by Celery.
"""

from .tasks import process_analysis, cleanup_expired_tasks, health_check

__all__ = [
    "process_analysis",
    "cleanup_expired_tasks",
    "health_check",
]
```

### File: `queue/tasks.py`

```python
"""
Celery Task Definitions for Agensium Backend

This module defines all Celery tasks for data processing.
Each task is designed to be:
- Idempotent (safe to retry)
- Self-contained (no shared state)
- Observable (proper logging)
"""

import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session

# Import after Celery app is created
from celery_app import app
from db.database import SessionLocal, engine
from db import models
from db.models import TaskStatus

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN PROCESSING TASK
# =============================================================================

@app.task(
    bind=True,
    name="queue.tasks.process_analysis",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
    track_started=True,
)
def process_analysis(
    self,
    task_id: str,
    user_id: int,
    tool_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main task for processing data analysis.

    This task:
    1. Updates task status to PROCESSING
    2. Executes the appropriate transformer based on tool_id
    3. Updates task status to COMPLETED or FAILED
    4. Reports progress throughout execution

    Args:
        task_id: UUID of the Agensium task
        user_id: Owner user ID
        tool_id: Optional tool ID (read from task if not provided)

    Returns:
        Dict with status and execution details

    Raises:
        SoftTimeLimitExceeded: If task exceeds 25 minutes
        Various exceptions that trigger retry
    """
    start_time = time.time()
    db = SessionLocal()

    try:
        logger.info(f"Starting task {task_id} for user {user_id}")

        # Get task from database
        task = db.query(models.Task).filter(
            models.Task.task_id == task_id
        ).first()

        if not task:
            logger.error(f"Task {task_id} not found")
            return {"status": "error", "error": "Task not found"}

        # Get user
        user = db.query(models.User).filter(
            models.User.id == user_id
        ).first()

        if not user:
            logger.error(f"User {user_id} not found")
            task.status = TaskStatus.FAILED.value
            task.error_code = "USER_NOT_FOUND"
            task.error_message = "User not found"
            task.failed_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "error", "error": "User not found"}

        # Update status to PROCESSING
        task.status = TaskStatus.PROCESSING.value
        task.processing_started_at = datetime.now(timezone.utc)
        task.progress = 20
        db.commit()

        # Report progress to Celery
        self.update_state(
            state="PROCESSING",
            meta={
                "progress": 20,
                "current_agent": None,
                "task_id": task_id
            }
        )

        # Execute based on tool
        result = None
        actual_tool_id = tool_id or task.tool_id

        try:
            if actual_tool_id == "profile-my-data":
                from transformers import profile_my_data_transformer
                result = _run_sync(
                    profile_my_data_transformer.run_profile_my_data_analysis_v2_1,
                    task=task,
                    current_user=user,
                    db=db
                )
            elif actual_tool_id == "clean-my-data":
                from transformers import clean_my_data_transformer
                result = _run_sync(
                    clean_my_data_transformer.run_clean_my_data_analysis_v2_1,
                    task=task,
                    current_user=user,
                    db=db
                )
            elif actual_tool_id == "master-my-data":
                from transformers import master_my_data_transformer
                result = _run_sync(
                    master_my_data_transformer.run_master_my_data_analysis_v2_1,
                    task=task,
                    current_user=user,
                    db=db
                )
            else:
                result = {
                    "status": "error",
                    "error": f"Unknown tool: {actual_tool_id}",
                    "error_code": "UNKNOWN_TOOL"
                }

        except SoftTimeLimitExceeded:
            logger.warning(f"Task {task_id} exceeded soft time limit")
            result = {
                "status": "error",
                "error": "Task exceeded time limit",
                "error_code": "TIMEOUT"
            }
        except Exception as e:
            logger.exception(f"Task {task_id} failed with error: {e}")
            result = {
                "status": "error",
                "error": str(e),
                "error_code": "INTERNAL_ERROR"
            }

        execution_time_ms = int((time.time() - start_time) * 1000)

        # Refresh task to get latest state
        db.refresh(task)

        # Update task based on result
        if result and result.get("status") == "success":
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = datetime.now(timezone.utc)
            task.progress = 100
            task.current_agent = None
            logger.info(f"Task {task_id} completed in {execution_time_ms}ms")
        else:
            task.status = TaskStatus.FAILED.value
            task.failed_at = datetime.now(timezone.utc)
            task.error_code = result.get("error_code", "PROCESSING_ERROR") if result else "PROCESSING_ERROR"
            task.error_message = result.get("error") if result else "Unknown error"
            logger.error(f"Task {task_id} failed: {task.error_message}")

        db.commit()

        return {
            "status": result.get("status") if result else "error",
            "task_id": task_id,
            "execution_time_ms": execution_time_ms
        }

    except Exception as e:
        logger.exception(f"Unexpected error in task {task_id}: {e}")

        # Try to update task status
        try:
            task = db.query(models.Task).filter(
                models.Task.task_id == task_id
            ).first()
            if task:
                task.status = TaskStatus.FAILED.value
                task.error_code = "INTERNAL_ERROR"
                task.error_message = str(e)
                task.failed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass

        raise  # Re-raise to trigger retry if applicable

    finally:
        db.close()


def _run_sync(async_func, **kwargs):
    """Run an async function synchronously in Celery worker."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_func(**kwargs))
    finally:
        loop.close()


# =============================================================================
# MAINTENANCE TASKS
# =============================================================================

@app.task(
    name="queue.tasks.cleanup_expired_tasks",
    ignore_result=True,
)
def cleanup_expired_tasks():
    """
    Periodic task to clean up expired tasks.

    Runs every 15 minutes and:
    1. Marks stale CREATED/UPLOADING tasks as EXPIRED
    2. Cleans up S3 files for expired tasks
    """
    from datetime import timedelta
    from services.s3_service import s3_service

    db = SessionLocal()

    try:
        expiry_threshold = datetime.now(timezone.utc) - timedelta(minutes=15)

        # Find expired tasks
        expired_tasks = db.query(models.Task).filter(
            models.Task.status.in_([
                TaskStatus.CREATED.value,
                TaskStatus.UPLOADING.value
            ]),
            models.Task.created_at < expiry_threshold
        ).all()

        count = 0
        for task in expired_tasks:
            task.status = TaskStatus.EXPIRED.value
            task.expired_at = datetime.now(timezone.utc)

            # Clean up S3 files
            try:
                s3_service.delete_task_files(task.user_id, task.task_id)
                task.s3_cleaned = True
            except Exception as e:
                logger.warning(f"Failed to clean S3 for task {task.task_id}: {e}")

            count += 1

        db.commit()
        logger.info(f"Cleaned up {count} expired tasks")

        return {"cleaned": count}

    finally:
        db.close()


@app.task(
    name="queue.tasks.health_check",
    ignore_result=True,
)
def health_check():
    """
    Periodic health check task.

    Runs every minute to:
    1. Verify database connectivity
    2. Verify S3 connectivity
    3. Log worker status
    """
    db = SessionLocal()

    try:
        # Check database
        db.execute("SELECT 1")
        db_ok = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_ok = False
    finally:
        db.close()

    # Check S3
    try:
        from services.s3_service import s3_service
        s3_service.list_files("health-check-probe/")
        s3_ok = True
    except Exception as e:
        logger.warning(f"S3 health check failed (may be normal): {e}")
        s3_ok = True  # S3 errors are less critical

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "ok" if db_ok else "error",
        "s3": "ok" if s3_ok else "error"
    }
```

---

## Running Workers

### Development Mode (Single Worker)

```powershell
# Navigate to backend directory
cd "c:\Users\VIVEK BANSAL\Desktop\Agensium\Agensium-V2\backend"

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Start single worker
celery -A celery_app worker --loglevel=info --pool=solo
```

**Note:** Use `--pool=solo` on Windows for development.

### Production Mode (Multiple Workers)

```powershell
# Start multiple workers with prefork pool
celery -A celery_app worker --loglevel=info --concurrency=4

# Or with gevent for I/O bound tasks
celery -A celery_app worker --loglevel=info --pool=gevent --concurrency=100
```

### Start Beat Scheduler (for periodic tasks)

```powershell
celery -A celery_app beat --loglevel=info
```

### Start Flower Monitoring

```powershell
celery -A celery_app flower --port=5555
```

Then open: http://localhost:5555

---

## Testing the Setup

### Test 1: Verify Celery Starts

```powershell
celery -A celery_app worker --loglevel=info --pool=solo
```

Expected output:

```
 -------------- celery@HOSTNAME v5.3.x
---- **** -----
--- * ***  * -- Windows-10...
-- * - **** ---
- ** ---------- [config]
- ** ---------- .> app:         agensium:0x...
- ** ---------- .> transport:   redis://localhost:6379/0
- ** ---------- .> results:     redis://localhost:6379/1
- *** --- * --- .> concurrency: 4 (solo)
-- ******* ---- .> task events: ON
--- ***** -----
 -------------- [queues]
                .> default          exchange=default(direct) key=default

[tasks]
  . queue.tasks.cleanup_expired_tasks
  . queue.tasks.health_check
  . queue.tasks.process_analysis

[2025-12-23 10:00:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2025-12-23 10:00:00,000: INFO/MainProcess] celery@HOSTNAME ready.
```

### Test 2: Send Test Task

In a Python shell:

```python
from celery_app import app, debug_task

# Send test task
result = debug_task.delay()
print(f"Task ID: {result.id}")

# Wait for result
print(f"Result: {result.get(timeout=10)}")
```

### Test 3: Check Flower Dashboard

1. Start Flower: `celery -A celery_app flower --port=5555`
2. Open: http://localhost:5555
3. Verify workers appear in dashboard

---

## Troubleshooting

### Error: "No module named 'celery_app'"

**Solution:** Ensure you're running from the backend directory:

```powershell
cd "c:\Users\VIVEK BANSAL\Desktop\Agensium\Agensium-V2\backend"
celery -A celery_app worker --loglevel=info
```

### Error: "Connection refused" (Redis)

**Solution:** Start Redis first (see [03_REDIS_SETUP.md](03_REDIS_SETUP.md))

### Error: "Pool not found" on Windows

**Solution:** Use `--pool=solo` for Windows development:

```powershell
celery -A celery_app worker --loglevel=info --pool=solo
```

### Error: Tasks stuck in PENDING

**Possible causes:**

1. Worker not running
2. Wrong queue configuration
3. Task name mismatch

**Debug steps:**

```powershell
# List registered tasks
celery -A celery_app inspect registered

# List active tasks
celery -A celery_app inspect active

# Check queue
celery -A celery_app inspect reserved
```

### Error: Memory leaks after many tasks

**Solution:** Configure worker recycling:

```python
# In celery_config.py
worker_max_tasks_per_child = 50  # Restart worker after 50 tasks
```

---

## Next Steps

1. ✅ Complete Celery setup
2. → Proceed to [03_REDIS_SETUP.md](03_REDIS_SETUP.md) for Redis installation
3. → Proceed to [05_MIGRATION_GUIDE.md](05_MIGRATION_GUIDE.md) for code migration
