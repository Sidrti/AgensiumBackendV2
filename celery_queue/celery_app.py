"""
Celery Application

Central Celery instance for the Agensium backend.

Usage:
    # Start worker (Windows - use solo pool)
    celery -A celery_queue.celery_app worker --loglevel=info --pool=solo

    # Start worker (Linux/Mac)
    celery -A celery_queue.celery_app worker --loglevel=info --concurrency=4

    # Start Flower monitoring
    celery -A celery_queue.celery_app flower --port=5555
"""

import os
import sys
from pathlib import Path

# =============================================================================
# PATH SETUP - MUST BE FIRST
# =============================================================================
# Add the backend directory to Python path to ensure local modules are found
# This is critical because Celery may import modules before the worker starts
# and the local 'transformers' folder must be found before any HuggingFace package
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def create_celery_app() -> Celery:
    """
    Create and configure the Celery application.
    
    Returns:
        Configured Celery app instance
    """
    # Create Celery app
    app = Celery("agensium")
    
    # Load configuration from celery_config module
    app.config_from_object("celery_queue.celery_config")
    
    # Auto-discover tasks in the celery_queue module
    app.autodiscover_tasks(["celery_queue"])
    
    return app


# Create the global Celery app instance
celery_app = create_celery_app()


# =============================================================================
# CELERY SIGNALS (Optional - for logging/monitoring)
# =============================================================================

from celery.signals import (
    task_prerun,
    task_postrun,
    task_failure,
    worker_ready,
    worker_shutting_down,
)


@worker_ready.connect
def worker_ready_handler(sender, **kwargs):
    """
    Ensure backend directory is in sys.path when worker starts.
    This is critical for the worker subprocess to find local modules.
    """
    # Add backend directory to worker process's Python path
    backend_dir = Path(__file__).resolve().parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    
    print(f"[Celery] Worker ready: {sender}")
    print(f"[Celery] Python path includes: {backend_dir}")


@worker_shutting_down.connect
def worker_shutdown_handler(sender, **kwargs):
    """Log when worker is shutting down."""
    print(f"[Celery] Worker shutting down: {sender}")


@task_prerun.connect
def task_prerun_handler(sender, task_id, task, args, kwargs, **other):
    """Log when task starts execution."""
    print(f"[Celery] Task starting: {task.name}[{task_id}]")


@task_postrun.connect
def task_postrun_handler(sender, task_id, task, args, kwargs, retval, state, **other):
    """Log when task completes."""
    print(f"[Celery] Task completed: {task.name}[{task_id}] state={state}")


@task_failure.connect
def task_failure_handler(sender, task_id, exception, args, kwargs, traceback, **other):
    """Log when task fails."""
    print(f"[Celery] Task failed: {sender.name}[{task_id}] error={exception}")


# =============================================================================
# HEALTH CHECK
# =============================================================================

@celery_app.task(bind=True, name="celery_queue.tasks.health_check")
def health_check(self):
    """
    Simple health check task for testing connectivity.
    
    Returns:
        dict: Health check status
    """
    return {
        "status": "healthy",
        "worker_id": self.request.hostname,
        "task_id": self.request.id,
    }
