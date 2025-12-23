# Migration Guide: Threading to Celery

**Document Version:** 1.0.0  
**Created:** December 23, 2025  
**Purpose:** Step-by-step migration from current `threading.Thread` approach to Celery + Redis queue system.

---

## Table of Contents

1. [Migration Overview](#migration-overview)
2. [Phase 1: Parallel Infrastructure](#phase-1-parallel-infrastructure)
3. [Phase 2: Task Routes Refactoring](#phase-2-task-routes-refactoring)
4. [Phase 3: Feature Flag Implementation](#phase-3-feature-flag-implementation)
5. [Phase 4: Database Status Updates](#phase-4-database-status-updates)
6. [Phase 5: Testing & Validation](#phase-5-testing--validation)
7. [Phase 6: Gradual Rollout](#phase-6-gradual-rollout)
8. [Rollback Procedures](#rollback-procedures)
9. [Post-Migration Cleanup](#post-migration-cleanup)

---

## Migration Overview

### Current State

**File:** `api/task_routes.py`

```python
# Current: Direct threading approach
def _execute_task_background(task_id: str, user_id: int):
    """Executes the task in a background thread."""
    # ... direct execution ...

# Task trigger
thread = threading.Thread(
    target=_execute_task_background,
    args=(task_id, user.id),
    daemon=True
)
thread.start()
```

### Target State

```python
# Target: Celery task dispatch
from queue.tasks import process_data_task

# Task trigger
result = process_data_task.delay(task_id, user.id)
celery_task_id = result.id
```

### Migration Principles

1. **Zero Downtime** - Keep existing system running during migration
2. **Feature Flag Controlled** - Toggle between threading and Celery
3. **Parallel Operation** - Both systems can run simultaneously
4. **Easy Rollback** - Quick switch back if issues arise
5. **Incremental Validation** - Test each phase before proceeding

---

## Phase 1: Parallel Infrastructure

### Step 1.1: Create Queue Module

```powershell
# Create directory structure
mkdir -p queue/workers
touch queue/__init__.py
touch queue/tasks.py
touch queue/celery_app.py
touch queue/celery_config.py
touch queue/progress.py
touch queue/error_handlers.py
touch queue/workers/__init__.py
touch queue/workers/base_worker.py
touch queue/workers/profile_worker.py
touch queue/workers/clean_worker.py
touch queue/workers/master_worker.py
```

### Step 1.2: Update requirements.txt

```diff
# requirements.txt

 # Existing packages
 fastapi==0.104.1
 uvicorn==0.24.0
 sqlalchemy==2.0.23
 pymysql==1.1.0
 boto3==1.34.0
 pandas==2.1.3
 numpy==1.26.2
 openpyxl==3.1.2
 openai==1.3.7
 stripe==7.7.0
 python-multipart==0.0.6
 python-jose[cryptography]==3.3.0
 passlib[bcrypt]==1.7.4
 aiosmtplib==3.0.1
 Jinja2==3.1.2
+
+# Queue system (Phase 1)
+celery[redis]==5.3.4
+redis==5.0.1
+flower==2.0.1
```

### Step 1.3: Install Dependencies

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install new packages
pip install celery[redis] redis flower

# Verify installation
python -c "import celery; print(f'Celery {celery.__version__}')"
python -c "import redis; print(f'Redis {redis.__version__}')"
```

### Step 1.4: Add Environment Variables

**File:** `.env`

```env
# Queue Configuration (Phase 1)
USE_CELERY=false  # Feature flag - start disabled
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Worker Configuration
CELERY_WORKER_CONCURRENCY=4
CELERY_TASK_TIME_LIMIT=1800
CELERY_TASK_SOFT_TIME_LIMIT=1500
```

### Step 1.5: Create Celery Application

**File:** `queue/celery_app.py`

```python
"""
Celery Application Configuration

This module creates and configures the Celery application
for background task processing.
"""

import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Create Celery app
celery_app = Celery(
    "agensium",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=["queue.tasks"]
)

# Load configuration
celery_app.config_from_object("queue.celery_config")

# Optional: Auto-discover tasks
# celery_app.autodiscover_tasks(['queue'])

if __name__ == "__main__":
    celery_app.start()
```

### Step 1.6: Verify Celery Starts

```powershell
# Start Redis (must be running first)
# See 03_REDIS_SETUP.md for installation

# Test Celery worker starts
celery -A queue.celery_app worker --loglevel=info

# You should see:
# [config]
# .> app:         agensium:...
# .> transport:   redis://localhost:6379/0
# .> results:     redis://localhost:6379/0
# [queues]
# .> profile      exchange=profile(direct) key=profile
# .> clean        exchange=clean(direct) key=clean
# .> master       exchange=master(direct) key=master
# .> default      exchange=default(direct) key=default
```

---

## Phase 2: Task Routes Refactoring

### Step 2.1: Extract Task Execution Logic

Create a new module that encapsulates the current execution logic:

**File:** `queue/execution.py`

```python
"""
Task Execution Logic

Contains the core execution logic extracted from task_routes.py,
usable by both threading and Celery approaches.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from db.database import SessionLocal
from db import models
from db.models import TaskStatus
from services.s3_service import s3_service
from transformers import (
    profile_my_data_transformer,
    clean_my_data_transformer,
    master_my_data_transformer
)

logger = logging.getLogger(__name__)


class TaskExecutor:
    """
    Encapsulates task execution logic.

    Used by both:
    - Threading approach (current)
    - Celery workers (migration target)
    """

    def __init__(
        self,
        task_id: str,
        user_id: int,
        progress_callback: Optional[callable] = None
    ):
        """
        Initialize executor.

        Args:
            task_id: UUID of the task
            user_id: ID of the user
            progress_callback: Optional callback for progress updates
                               Signature: (progress: int, agent: str) -> None
        """
        self.task_id = task_id
        self.user_id = user_id
        self.progress_callback = progress_callback
        self.db: Optional[Session] = None
        self.task: Optional[models.Task] = None
        self.user: Optional[models.User] = None

    def execute(self) -> Dict[str, Any]:
        """
        Execute the task.

        Returns:
            Result dict with status and details
        """
        try:
            self.db = SessionLocal()

            # Load entities
            if not self._load_entities():
                return {"status": "error", "error": "Entity not found"}

            # Update to PROCESSING
            self._update_status(TaskStatus.PROCESSING, progress=15)

            # Execute based on tool
            tool_id = self.task.tool_id

            if tool_id == "profile-my-data":
                result = self._execute_profile()
            elif tool_id == "clean-my-data":
                result = self._execute_clean()
            elif tool_id == "master-my-data":
                result = self._execute_master()
            else:
                result = {"status": "error", "error": f"Unknown tool: {tool_id}"}

            if result.get("status") == "error":
                self._update_status(
                    TaskStatus.FAILED,
                    error_code=result.get("error_code", "PROCESSING_ERROR"),
                    error_message=result.get("error")
                )
            else:
                self._update_status(TaskStatus.COMPLETED, progress=100)

            return result

        except Exception as e:
            logger.exception(f"Task execution error: {e}")
            self._update_status(
                TaskStatus.FAILED,
                error_code="INTERNAL_ERROR",
                error_message=str(e)
            )
            return {"status": "error", "error": str(e)}

        finally:
            if self.db:
                self.db.close()

    def _load_entities(self) -> bool:
        """Load task and user from database."""
        self.task = self.db.query(models.Task).filter(
            models.Task.task_id == self.task_id
        ).first()

        self.user = self.db.query(models.User).filter(
            models.User.id == self.user_id
        ).first()

        return self.task is not None and self.user is not None

    def _update_status(
        self,
        status: TaskStatus,
        progress: Optional[int] = None,
        current_agent: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Update task status."""
        if not self.task:
            return

        self.task.status = status.value

        if progress is not None:
            self.task.progress = progress

        if current_agent is not None:
            self.task.current_agent = current_agent

        if error_code is not None:
            self.task.error_code = error_code

        if error_message is not None:
            self.task.error_message = error_message

        now = datetime.now(timezone.utc)
        if status == TaskStatus.PROCESSING:
            self.task.processing_started_at = now
        elif status == TaskStatus.COMPLETED:
            self.task.completed_at = now
        elif status == TaskStatus.FAILED:
            self.task.failed_at = now

        self.db.commit()

        # Call progress callback if provided
        if self.progress_callback and progress is not None:
            self.progress_callback(progress, current_agent)

    def _execute_profile(self) -> Dict[str, Any]:
        """Execute profile analysis."""
        # Existing logic from _execute_task_background
        # ... (extract from task_routes.py)
        return profile_my_data_transformer.run_analysis_v2_1(
            self.db,
            self.user.id,
            self.task.task_id,
            s3_service,
            lambda p, a: self._update_status(TaskStatus.PROCESSING, p, a)
        )

    def _execute_clean(self) -> Dict[str, Any]:
        """Execute clean analysis."""
        return clean_my_data_transformer.run_analysis_v2_1(
            self.db,
            self.user.id,
            self.task.task_id,
            s3_service,
            lambda p, a: self._update_status(TaskStatus.PROCESSING, p, a)
        )

    def _execute_master(self) -> Dict[str, Any]:
        """Execute master analysis."""
        return master_my_data_transformer.run_analysis_v2_1(
            self.db,
            self.user.id,
            self.task.task_id,
            s3_service,
            lambda p, a: self._update_status(TaskStatus.PROCESSING, p, a)
        )
```

### Step 2.2: Create Celery Tasks

**File:** `queue/tasks.py`

```python
"""
Celery Task Definitions

Defines the Celery tasks that wrap the TaskExecutor.
"""

import logging
from typing import Dict, Any

from celery import Task

from .celery_app import celery_app
from .execution import TaskExecutor

logger = logging.getLogger(__name__)


class BaseTask(Task):
    """Base task with error handling and retries."""

    autoretry_for = (ConnectionError, TimeoutError)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 3

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(f"Task {task_id} retrying: {exc}")


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="process_data_task",
    queue="default",
    time_limit=1800,
    soft_time_limit=1500
)
def process_data_task(
    self,
    task_id: str,
    user_id: int
) -> Dict[str, Any]:
    """
    Process a data analysis task.

    This is the main Celery task that replaces the threading approach.

    Args:
        task_id: UUID of the Agensium task
        user_id: ID of the user

    Returns:
        Result dict with status and details
    """
    def progress_callback(progress: int, agent: str = None):
        """Report progress to Celery."""
        self.update_state(
            state="PROCESSING",
            meta={
                "progress": progress,
                "current_agent": agent,
                "task_id": task_id
            }
        )

    executor = TaskExecutor(
        task_id=task_id,
        user_id=user_id,
        progress_callback=progress_callback
    )

    return executor.execute()


# Tool-specific tasks for dedicated queues
@celery_app.task(
    bind=True,
    base=BaseTask,
    name="process_profile_task",
    queue="profile",
    time_limit=1200,
    soft_time_limit=1000
)
def process_profile_task(self, task_id: str, user_id: int) -> Dict[str, Any]:
    """Process profile-my-data task."""
    return process_data_task(task_id, user_id)


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="process_clean_task",
    queue="clean",
    time_limit=1800,
    soft_time_limit=1500
)
def process_clean_task(self, task_id: str, user_id: int) -> Dict[str, Any]:
    """Process clean-my-data task."""
    return process_data_task(task_id, user_id)


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="process_master_task",
    queue="master",
    time_limit=2400,
    soft_time_limit=2100
)
def process_master_task(self, task_id: str, user_id: int) -> Dict[str, Any]:
    """Process master-my-data task."""
    return process_data_task(task_id, user_id)
```

---

## Phase 3: Feature Flag Implementation

### Step 3.1: Create Configuration Module

**File:** `queue/config.py`

```python
"""
Queue Configuration

Provides feature flags and configuration for queue system.
"""

import os
from typing import Optional
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class QueueConfig:
    """Queue configuration singleton."""

    def __init__(self):
        self._use_celery: Optional[bool] = None

    @property
    def use_celery(self) -> bool:
        """Check if Celery queue should be used."""
        if self._use_celery is None:
            env_value = os.getenv("USE_CELERY", "false").lower()
            self._use_celery = env_value in ("true", "1", "yes")
        return self._use_celery

    def set_use_celery(self, value: bool):
        """Override Celery usage (for testing)."""
        self._use_celery = value

    @property
    def redis_url(self) -> str:
        """Get Redis URL."""
        return os.getenv("REDIS_URL", "redis://localhost:6379/0")

    @property
    def worker_concurrency(self) -> int:
        """Get worker concurrency."""
        return int(os.getenv("CELERY_WORKER_CONCURRENCY", "4"))

    @property
    def task_time_limit(self) -> int:
        """Get task time limit in seconds."""
        return int(os.getenv("CELERY_TASK_TIME_LIMIT", "1800"))


@lru_cache()
def get_queue_config() -> QueueConfig:
    """Get cached queue configuration."""
    return QueueConfig()
```

### Step 3.2: Create Dispatcher

**File:** `queue/dispatcher.py`

```python
"""
Task Dispatcher

Routes tasks to either threading or Celery based on configuration.
"""

import threading
import logging
from typing import Dict, Any

from .config import get_queue_config
from .execution import TaskExecutor
from .tasks import process_data_task, process_profile_task, process_clean_task, process_master_task

logger = logging.getLogger(__name__)


def dispatch_task(
    task_id: str,
    user_id: int,
    tool_id: str = "default"
) -> Dict[str, Any]:
    """
    Dispatch a task to the appropriate execution system.

    Args:
        task_id: UUID of the task
        user_id: ID of the user
        tool_id: Tool ID for queue routing

    Returns:
        Dict with dispatch information
    """
    config = get_queue_config()

    if config.use_celery:
        return _dispatch_celery(task_id, user_id, tool_id)
    else:
        return _dispatch_thread(task_id, user_id)


def _dispatch_celery(
    task_id: str,
    user_id: int,
    tool_id: str
) -> Dict[str, Any]:
    """Dispatch to Celery queue."""
    logger.info(f"Dispatching task {task_id} to Celery queue")

    # Route to tool-specific queue
    task_map = {
        "profile-my-data": process_profile_task,
        "clean-my-data": process_clean_task,
        "master-my-data": process_master_task,
    }

    task_func = task_map.get(tool_id, process_data_task)

    # Dispatch to Celery
    result = task_func.delay(task_id, user_id)

    return {
        "dispatch_method": "celery",
        "celery_task_id": result.id,
        "task_id": task_id,
        "queue": task_func.queue or "default"
    }


def _dispatch_thread(task_id: str, user_id: int) -> Dict[str, Any]:
    """Dispatch to background thread (current approach)."""
    logger.info(f"Dispatching task {task_id} to background thread")

    def execute_in_thread():
        executor = TaskExecutor(task_id, user_id)
        executor.execute()

    thread = threading.Thread(
        target=execute_in_thread,
        daemon=True
    )
    thread.start()

    return {
        "dispatch_method": "thread",
        "task_id": task_id
    }
```

### Step 3.3: Update Task Routes

**File:** `api/task_routes.py` (modifications)

```python
# At the top, add import
from queue.dispatcher import dispatch_task

# In the trigger_processing endpoint, replace threading code:

# BEFORE:
# thread = threading.Thread(
#     target=_execute_task_background,
#     args=(task_id, user.id),
#     daemon=True
# )
# thread.start()

# AFTER:
dispatch_result = dispatch_task(
    task_id=task_id,
    user_id=user.id,
    tool_id=task.tool_id
)
logger.info(f"Task dispatched: {dispatch_result}")
```

### Step 3.4: Feature Flag Toggle

```powershell
# Toggle to Celery
$env:USE_CELERY = "true"

# Toggle back to threading
$env:USE_CELERY = "false"
```

---

## Phase 4: Database Status Updates

### Step 4.1: Enable QUEUED Status

Update task creation to use QUEUED when Celery is enabled:

**File:** `api/task_routes.py`

```python
from queue.config import get_queue_config

async def create_task(request: CreateTaskRequest, ...):
    config = get_queue_config()

    # Set initial status based on dispatch method
    initial_status = (
        TaskStatus.QUEUED if config.use_celery
        else TaskStatus.CREATED
    )

    new_task = models.Task(
        task_id=task_id,
        user_id=user.id,
        tool_id=request.tool_id,
        status=initial_status.value,
        # ... rest of fields
    )
```

### Step 4.2: Add Celery Task ID Storage

**File:** `db/models.py` (migration needed)

```python
class Task(Base):
    # ... existing fields ...

    # Add new field for Celery task ID
    celery_task_id = Column(String(255), nullable=True)
```

**Migration SQL:**

```sql
ALTER TABLE tasks
ADD COLUMN celery_task_id VARCHAR(255) NULL;

CREATE INDEX idx_tasks_celery_task_id ON tasks(celery_task_id);
```

---

## Phase 5: Testing & Validation

### Step 5.1: Unit Tests

**File:** `tests/queue/test_dispatcher.py`

```python
"""Test task dispatcher."""

import pytest
from unittest.mock import patch, Mock

from queue.dispatcher import dispatch_task
from queue.config import get_queue_config


class TestDispatcher:
    """Tests for task dispatcher."""

    @patch('queue.dispatcher.get_queue_config')
    @patch('queue.dispatcher.TaskExecutor')
    def test_dispatch_thread(self, mock_executor, mock_config):
        """Test threading dispatch."""
        config = Mock()
        config.use_celery = False
        mock_config.return_value = config

        result = dispatch_task("task-123", 1, "profile-my-data")

        assert result["dispatch_method"] == "thread"
        assert result["task_id"] == "task-123"

    @patch('queue.dispatcher.get_queue_config')
    @patch('queue.dispatcher.process_profile_task')
    def test_dispatch_celery(self, mock_task, mock_config):
        """Test Celery dispatch."""
        config = Mock()
        config.use_celery = True
        mock_config.return_value = config

        mock_result = Mock()
        mock_result.id = "celery-task-id"
        mock_task.delay.return_value = mock_result
        mock_task.queue = "profile"

        result = dispatch_task("task-123", 1, "profile-my-data")

        assert result["dispatch_method"] == "celery"
        assert result["celery_task_id"] == "celery-task-id"
        assert result["queue"] == "profile"
```

### Step 5.2: Integration Tests

```powershell
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Start Celery worker in test mode
celery -A queue.celery_app worker --loglevel=info --pool=solo

# Run integration tests
pytest tests/queue/test_integration.py -v
```

### Step 5.3: Load Tests

```python
# tests/queue/load_test.py
"""Load test for queue system."""

import asyncio
import httpx
import time

async def create_tasks(n: int):
    """Create n tasks and measure throughput."""
    async with httpx.AsyncClient() as client:
        start = time.time()

        tasks = []
        for i in range(n):
            task = client.post(
                "http://localhost:8000/tasks",
                json={"tool_id": "profile-my-data"},
                headers={"Authorization": "Bearer ..."}
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        end = time.time()

        success = sum(1 for r in responses if r.status_code == 201)
        print(f"Created {success}/{n} tasks in {end-start:.2f}s")
        print(f"Throughput: {success/(end-start):.2f} tasks/sec")

if __name__ == "__main__":
    asyncio.run(create_tasks(100))
```

---

## Phase 6: Gradual Rollout

### Step 6.1: Percentage-Based Rollout

**File:** `queue/config.py` (update)

```python
import random

class QueueConfig:
    # ... existing code ...

    @property
    def celery_rollout_percentage(self) -> int:
        """Get Celery rollout percentage (0-100)."""
        return int(os.getenv("CELERY_ROLLOUT_PERCENTAGE", "0"))

    def should_use_celery(self, task_id: str = None) -> bool:
        """
        Determine if Celery should be used.

        Uses consistent hashing for the same task_id.
        """
        if not self.use_celery:
            return False

        percentage = self.celery_rollout_percentage

        if percentage >= 100:
            return True

        if percentage <= 0:
            return False

        # Consistent routing based on task_id
        if task_id:
            hash_value = hash(task_id) % 100
            return hash_value < percentage

        # Random for new tasks
        return random.randint(1, 100) <= percentage
```

### Step 6.2: Rollout Schedule

| Phase | Percentage | Duration | Criteria to Proceed   |
| ----- | ---------- | -------- | --------------------- |
| 1     | 5%         | 2 days   | No errors, latency OK |
| 2     | 25%        | 3 days   | Error rate < 0.1%     |
| 3     | 50%        | 5 days   | Error rate < 0.1%     |
| 4     | 75%        | 5 days   | Error rate < 0.1%     |
| 5     | 100%       | Final    | All metrics stable    |

### Step 6.3: Monitoring Commands

```powershell
# Watch error rates
$env:CELERY_ROLLOUT_PERCENTAGE = "5"

# Increase to 25%
$env:CELERY_ROLLOUT_PERCENTAGE = "25"

# Full rollout
$env:CELERY_ROLLOUT_PERCENTAGE = "100"
```

---

## Rollback Procedures

### Immediate Rollback

```powershell
# Disable Celery immediately
$env:USE_CELERY = "false"

# Restart FastAPI servers
# Tasks will revert to threading
```

### Celery Queue Drain

```python
# Drain pending tasks before rollback
from queue.celery_app import celery_app

# Purge all pending tasks (destructive!)
celery_app.control.purge()

# Or gracefully drain (wait for completion)
celery_app.control.shutdown()
```

### Partial Rollback

```powershell
# Reduce Celery percentage
$env:CELERY_ROLLOUT_PERCENTAGE = "10"
```

---

## Post-Migration Cleanup

### Step 1: Remove Threading Code

Once Celery is stable at 100%, remove old threading code:

```python
# DELETE from task_routes.py:
# - _execute_task_background function
# - threading imports
# - thread.start() code
```

### Step 2: Remove Feature Flags

```python
# Simplify dispatcher to Celery-only
def dispatch_task(task_id: str, user_id: int, tool_id: str):
    return _dispatch_celery(task_id, user_id, tool_id)
```

### Step 3: Update Documentation

- Remove threading references
- Document Celery-only architecture
- Update deployment guides

### Step 4: Clean Environment

```env
# Remove deprecated flags
# USE_CELERY=true  # No longer needed
# CELERY_ROLLOUT_PERCENTAGE=100  # No longer needed
```

---

## Migration Checklist

### Pre-Migration

- [ ] Redis installed and running
- [ ] Celery installed (requirements.txt)
- [ ] Environment variables configured
- [ ] Celery worker tested locally
- [ ] Flower monitoring set up

### During Migration

- [ ] Feature flag enabled (5%)
- [ ] Monitoring dashboards ready
- [ ] Error alerts configured
- [ ] Rollback procedure documented
- [ ] On-call team notified

### Post-Migration

- [ ] 100% Celery rollout stable
- [ ] Threading code removed
- [ ] Documentation updated
- [ ] Performance metrics baselined
- [ ] Capacity planning completed

---

## Next Steps

1. ✅ Review migration guide
2. → Implement Phase 1 (infrastructure)
3. → Proceed to [06_MONITORING.md](06_MONITORING.md) for observability
