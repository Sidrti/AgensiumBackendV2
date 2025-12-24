"""
Celery Configuration

Settings for Celery workers and Redis Cloud connection.
All settings can be overridden via environment variables.
"""

import os
from kombu import Queue


# =============================================================================
# BROKER & BACKEND (Redis Cloud)
# =============================================================================

# Redis URL - use rediss:// for TLS (Upstash/Railway)
# Format: rediss://default:PASSWORD@HOST:PORT
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

broker_url = os.getenv("CELERY_BROKER_URL", REDIS_URL)
result_backend = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)


# =============================================================================
# SERIALIZATION
# =============================================================================

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True


# =============================================================================
# TASK SETTINGS
# =============================================================================

# Acknowledge task after completion (ensures task is re-queued if worker dies)
task_acks_late = True

# Reject and requeue task if worker is lost
task_reject_on_worker_lost = True

# Hard time limit - worker process killed after this (seconds)
task_time_limit = 1800  # 30 minutes

# Soft time limit - SoftTimeLimitExceeded raised after this (seconds)
task_soft_time_limit = 1500  # 25 minutes

# Ignore task results we don't need
task_ignore_result = False

# Store task errors
task_store_errors_even_if_ignored = True


# =============================================================================
# RESULT SETTINGS
# =============================================================================

# Result expiration (seconds) - 24 hours
result_expires = 86400

# Enable extended task result attributes
result_extended = True


# =============================================================================
# WORKER SETTINGS
# =============================================================================

# Number of concurrent workers (can be overridden by command line)
worker_concurrency = 1

# Prefetch multiplier - 1 for fair distribution (important for long tasks)
worker_prefetch_multiplier = 1

# Restart worker after processing N tasks (prevents memory leaks)
worker_max_tasks_per_child = int(os.getenv("CELERY_WORKER_MAX_TASKS_PER_CHILD", "100"))

# Max memory per child in KB (400MB default)
worker_max_memory_per_child = int(os.getenv("CELERY_WORKER_MAX_MEMORY_PER_CHILD", "400000"))


# =============================================================================
# QUEUE CONFIGURATION
# =============================================================================

# Default queue
task_default_queue = "default"

# Define queues (single queue for unified worker approach)
task_queues = (
    Queue("default", routing_key="default"),
)

# Route all tasks to default queue
task_routes = {
    "celery_queue.tasks.*": {"queue": "default"},
}


# =============================================================================
# RETRY CONFIGURATION
# =============================================================================

# Default retry delay (seconds)
task_default_retry_delay = 60

# Max retries
task_annotations = {
    "celery_queue.tasks.process_analysis": {
        "rate_limit": "10/m",  # Max 10 tasks per minute per worker
        "max_retries": 3,
    }
}


# =============================================================================
# BROKER SETTINGS (Redis-specific)
# =============================================================================

# Redis connection settings
broker_connection_retry_on_startup = True
broker_connection_max_retries = 10

# SSL/TLS settings for Upstash Redis (required for rediss:// URLs)
import ssl
redis_backend_use_ssl = {
    "ssl_cert_reqs": ssl.CERT_NONE,
}

broker_use_ssl = {
    "ssl_cert_reqs": ssl.CERT_NONE,
}

# Transport options for Redis
broker_transport_options = {
    "visibility_timeout": 3600,  # 1 hour - task must complete within this time
    "socket_timeout": 30,
    "socket_connect_timeout": 30,
}

# Result backend transport options
result_backend_transport_options = {
    "socket_timeout": 30,
    "socket_connect_timeout": 30,
}


# =============================================================================
# LOGGING
# =============================================================================

# Worker hijack root logger
worker_hijack_root_logger = False

# Log format
worker_log_format = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
worker_task_log_format = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s"
