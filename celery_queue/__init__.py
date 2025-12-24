"""
Agensium Celery Queue Module

Celery-based task queue for background processing of data analysis tasks.

Components:
- celery_app: Celery application instance
- celery_config: Configuration settings
- tasks: Task definitions (unified worker)

Usage:
    # Start worker
    celery -A celery_queue.celery_app worker --loglevel=info --pool=solo

    # Start Flower (monitoring)
    celery -A celery_queue.celery_app flower --port=5555
"""

import sys
from pathlib import Path

# Ensure backend directory is in Python path before any imports
# This is critical for finding local 'transformers' module
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from .celery_app import celery_app
from .tasks import process_analysis

__all__ = ["celery_app", "process_analysis"]
