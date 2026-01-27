"""
Celery Tasks - Unified Worker

Single task that processes all analysis types by routing to the appropriate
transformer based on tool_id. This avoids code duplication since all
transformers follow the same pattern.

Architecture:
    process_analysis(task_id, user_id)
        → Load task from DB
        → Route to transformer based on tool_id:
            - profile-my-data → profile_my_data_transformer
            - clean-my-data   → clean_my_data_transformer
            - master-my-data  → master_my_data_transformer
            - analyze-my-data → analyze_my_data_transformer
        → Update task status on completion/failure
"""

import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

# Add the backend directory to Python path to ensure local modules are found
# This is needed because Celery may run from a different working directory
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from celery_queue.celery_app import celery_app
from db.database import SessionLocal
from db import models
from db.models import TaskStatus
from transformers.transformers_utils import get_transformer


# =============================================================================
# BASE TASK CLASS
# =============================================================================

class AnalysisTask(Task):
    """
    Base task class with common error handling and database management.
    """
    
    # Task settings
    autoretry_for = (ConnectionError, TimeoutError)
    retry_backoff = True
    retry_backoff_max = 600  # Max 10 minutes between retries
    retry_jitter = True
    max_retries = 3
    
    # Don't retry on these errors
    dont_autoretry_for = (
        ValueError,
        SoftTimeLimitExceeded,
    )
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Handle task failure - update task status in database.
        """
        print(f"[Celery] Task {task_id} failed: {exc}")
        
        # Extract task_id from args (first argument)
        if args:
            analysis_task_id = args[0]
            self._update_task_status_on_failure(analysis_task_id, str(exc))
    
    def on_success(self, retval, task_id, args, kwargs):
        """
        Handle task success - logging.
        """
        print(f"[Celery] Task {task_id} completed successfully")
    
    def _update_task_status_on_failure(self, task_id: str, error_message: str):
        """
        Update task status to FAILED in database.
        """
        db = SessionLocal()
        try:
            task = db.query(models.Task).filter(models.Task.task_id == task_id).first()
            if task and task.status == TaskStatus.PROCESSING.value:
                task.status = TaskStatus.FAILED.value
                task.error_code = "CELERY_TASK_FAILURE"
                task.error_message = error_message[:1000]  # Limit error message length
                task.failed_at = datetime.now(timezone.utc)
                db.commit()
                print(f"[Celery] Updated task {task_id} status to FAILED")
        except Exception as e:
            print(f"[Celery] Failed to update task status: {e}")
        finally:
            db.close()


# =============================================================================
# MAIN TASK
# =============================================================================

@celery_app.task(
    bind=True,
    base=AnalysisTask,
    name="celery_queue.tasks.process_analysis",
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_analysis(self, task_id: str, user_id: int) -> Dict[str, Any]:
    """
    Unified task for processing all analysis types.
    
    Routes to the appropriate transformer based on the task's tool_id.
    This is the main entry point for all Celery-based analysis processing.
    
    Args:
        task_id: UUID of the task to process
        user_id: ID of the user who owns the task
        
    Returns:
        dict: Result with status and optional error info
    """
    print(f"[Celery] Processing task {task_id} for user {user_id}")
    start_time = time.time()
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Load task from database
        task = db.query(models.Task).filter(models.Task.task_id == task_id).first()
        if not task:
            print(f"[Celery] Task {task_id} not found")
            return {
                "status": "error",
                "error": f"Task {task_id} not found",
                "error_code": "TASK_NOT_FOUND"
            }
        
        # Check if task is in valid state
        if task.status not in [TaskStatus.QUEUED.value, TaskStatus.PROCESSING.value]:
            print(f"[Celery] Task {task_id} in invalid state: {task.status}")
            return {
                "status": "error",
                "error": f"Task in invalid state: {task.status}",
                "error_code": "INVALID_TASK_STATE"
            }
        
        # Load user
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            print(f"[Celery] User {user_id} not found")
            task.status = TaskStatus.FAILED.value
            task.error_code = "USER_NOT_FOUND"
            task.error_message = f"User {user_id} not found"
            task.failed_at = datetime.now(timezone.utc)
            db.commit()
            return {
                "status": "error",
                "error": "User not found",
                "error_code": "USER_NOT_FOUND"
            }
        
        # Update task status to PROCESSING
        task.status = TaskStatus.PROCESSING.value
        task.processing_started_at = datetime.now(timezone.utc)
        db.commit()
        
        # Get the appropriate transformer
        try:
            transformer = get_transformer(task.tool_id)
        except ValueError as e:
            task.status = TaskStatus.FAILED.value
            task.error_code = "UNKNOWN_TOOL"
            task.error_message = str(e)
            task.failed_at = datetime.now(timezone.utc)
            db.commit()
            return {
                "status": "error",
                "error": str(e),
                "error_code": "UNKNOWN_TOOL"
            }
        
        # Execute transformer (run async function in sync context)
        print(f"[Celery] Executing {task.tool_id} transformer for task {task_id}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                transformer(
                    task=task,
                    current_user=user,
                    db=db
                )
            )
        finally:
            loop.close()
        
        # Process result
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Refresh task to get latest state (transformer may have updated it)
        db.refresh(task)
        
        if result and result.get("status") == "success":
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = datetime.now(timezone.utc)
            task.progress = 100
            task.current_agent = None
            db.commit()
            
            print(f"[Celery] Task {task_id} completed successfully in {execution_time_ms}ms")
            return {
                "status": "success",
                "task_id": task_id,
                "execution_time_ms": execution_time_ms
            }
        else:
            task.status = TaskStatus.FAILED.value
            task.failed_at = datetime.now(timezone.utc)
            task.error_code = result.get("error_code", "PROCESSING_ERROR") if result else "PROCESSING_ERROR"
            task.error_message = result.get("error_message") or result.get("error") or "Unknown error" if result else "Unknown error"
            db.commit()
            
            print(f"[Celery] Task {task_id} failed: {task.error_message}")
            return {
                "status": "error",
                "task_id": task_id,
                "error": task.error_message,
                "error_code": task.error_code,
                "execution_time_ms": execution_time_ms
            }
    
    except SoftTimeLimitExceeded:
        print(f"[Celery] Task {task_id} exceeded soft time limit")
        try:
            task = db.query(models.Task).filter(models.Task.task_id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED.value
                task.error_code = "TIMEOUT"
                task.error_message = "Task exceeded time limit"
                task.failed_at = datetime.now(timezone.utc)
                db.commit()
        except:
            pass
        raise  # Re-raise to let Celery handle it
    
    except Exception as e:
        print(f"[Celery] Task {task_id} failed with exception: {e}")
        try:
            task = db.query(models.Task).filter(models.Task.task_id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED.value
                task.error_code = "INTERNAL_ERROR"
                task.error_message = str(e)[:1000]
                task.failed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as db_error:
            print(f"[Celery] Failed to update task status: {db_error}")
        
        return {
            "status": "error",
            "task_id": task_id,
            "error": str(e),
            "error_code": "INTERNAL_ERROR"
        }
    
    finally:
        db.close()


# =============================================================================
# UTILITY TASKS
# =============================================================================

@celery_app.task(name="celery_queue.tasks.cleanup_stale_tasks")
def cleanup_stale_tasks(hours: int = 24) -> Dict[str, Any]:
    """
    Cleanup tasks that have been stuck in PROCESSING state for too long.
    
    This is a maintenance task that should be run periodically.
    
    Args:
        hours: Number of hours after which a PROCESSING task is considered stale
        
    Returns:
        dict: Cleanup results
    """
    from datetime import timedelta
    
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        stale_tasks = db.query(models.Task).filter(
            models.Task.status == TaskStatus.PROCESSING.value,
            models.Task.processing_started_at < cutoff
        ).all()
        
        updated_count = 0
        for task in stale_tasks:
            task.status = TaskStatus.FAILED.value
            task.error_code = "STALE_TASK"
            task.error_message = f"Task was stuck in PROCESSING for more than {hours} hours"
            task.failed_at = datetime.now(timezone.utc)
            updated_count += 1
        
        db.commit()
        
        print(f"[Celery] Cleaned up {updated_count} stale tasks")
        return {
            "status": "success",
            "cleaned_up": updated_count
        }
    
    except Exception as e:
        print(f"[Celery] Cleanup failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        db.close()
