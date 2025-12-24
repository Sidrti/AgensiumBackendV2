# Monitoring & Observability

**Document Version:** 1.0.0  
**Created:** December 23, 2025  
**Purpose:** Set up comprehensive monitoring for Celery + Redis queue system.

---

## Table of Contents

1. [Monitoring Stack Overview](#monitoring-stack-overview)
2. [Flower Setup (Celery UI)](#flower-setup-celery-ui)
3. [Prometheus Integration](#prometheus-integration)
4. [Grafana Dashboards](#grafana-dashboards)
5. [Redis Monitoring](#redis-monitoring)
6. [Application Logging](#application-logging)
7. [Alerting Configuration](#alerting-configuration)
8. [Health Check Endpoints](#health-check-endpoints)
9. [Troubleshooting Guide](#troubleshooting-guide)

---

## Monitoring Stack Overview

### Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MONITORING ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│   │    Flower    │    │  Prometheus  │    │   Grafana    │                 │
│   │  (Celery UI) │    │   (Metrics)  │    │ (Dashboards) │                 │
│   │  :5555       │    │   :9090      │    │   :3000      │                 │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                 │
│          │                   │                   │                          │
│          │                   │                   │                          │
│          ▼                   ▼                   ▼                          │
│   ┌──────────────────────────────────────────────────────┐                 │
│   │              Celery Workers (with Exporters)          │                 │
│   │                                                        │                 │
│   │   ┌────────────┐ ┌────────────┐ ┌────────────┐        │                 │
│   │   │  Profile   │ │   Clean    │ │   Master   │        │                 │
│   │   │  Worker    │ │  Worker    │ │   Worker   │        │                 │
│   │   └─────┬──────┘ └─────┬──────┘ └─────┬──────┘        │                 │
│   │         │              │              │                │                 │
│   │         └──────────────┼──────────────┘                │                 │
│   │                        │                               │                 │
│   │                        ▼                               │                 │
│   │                 ┌────────────┐                         │                 │
│   │                 │   Redis    │                         │                 │
│   │                 │   :6379    │                         │                 │
│   │                 └────────────┘                         │                 │
│   │                        │                               │                 │
│   │                        ▼                               │                 │
│   │                 ┌────────────┐                         │                 │
│   │                 │  Redis     │                         │                 │
│   │                 │  Exporter  │                         │                 │
│   │                 │   :9121    │                         │                 │
│   │                 └────────────┘                         │                 │
│   └────────────────────────────────────────────────────────┘                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Metrics to Monitor

| Category      | Metric            | Target  |
| ------------- | ----------------- | ------- |
| Throughput    | Tasks/second      | > 10/s  |
| Latency       | 95th percentile   | < 2 min |
| Success Rate  | Completed/Total   | > 99%   |
| Queue Depth   | Pending tasks     | < 100   |
| Worker Health | Active workers    | >= 2    |
| Redis         | Memory usage      | < 80%   |
| Redis         | Connected clients | < 100   |

---

## Flower Setup (Celery UI)

### Basic Installation

```powershell
# Already installed via requirements.txt
pip install flower==2.0.1
```

### Starting Flower

```powershell
# Basic startup
celery -A celery_queue.celery_app flower --port=5555

# With authentication
celery -A celery_queue.celery_app flower \
    --port=5555 \
    --basic_auth=admin:password

# With broker URL
celery -A celery_queue.celery_app flower \
    --port=5555 \
    --broker=redis://localhost:6379/0
```

### Environment Configuration

**File:** `.env`

```env
# Flower Configuration
FLOWER_PORT=5555
FLOWER_BASIC_AUTH=admin:your-secure-password
FLOWER_PURGE_OFFLINE_WORKERS=300
FLOWER_BROKER_API=redis://localhost:6379/0
```

### Flower Features

| Feature   | URL                           | Description             |
| --------- | ----------------------------- | ----------------------- |
| Dashboard | http://localhost:5555         | Overview of all workers |
| Tasks     | http://localhost:5555/tasks   | Task history and status |
| Broker    | http://localhost:5555/broker  | Queue statistics        |
| Monitor   | http://localhost:5555/monitor | Real-time charts        |

### Docker Compose with Flower

**File:** `docker-compose.monitoring.yml`

```yaml
version: "3.8"

services:
  flower:
    image: mher/flower:2.0.1
    container_name: agensium-flower
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - FLOWER_BASIC_AUTH=admin:password
      - FLOWER_PURGE_OFFLINE_WORKERS=300
    depends_on:
      - redis
    restart: unless-stopped
    networks:
      - agensium-network

  redis:
    image: redis:7-alpine
    container_name: agensium-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - agensium-network

networks:
  agensium-network:
    driver: bridge

volumes:
  redis_data:
```

---

## Prometheus Integration

### Celery Prometheus Exporter

**Installation:**

```powershell
pip install celery-exporter
```

**File:** `celery_queue/metrics.py`

```python
"""
Prometheus Metrics for Celery Tasks

Exposes metrics for Prometheus scraping.
"""

from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time


# Task counters
TASKS_RECEIVED = Counter(
    'celery_tasks_received_total',
    'Total tasks received',
    ['task_name', 'queue']
)

TASKS_SUCCEEDED = Counter(
    'celery_tasks_succeeded_total',
    'Total tasks completed successfully',
    ['task_name', 'queue']
)

TASKS_FAILED = Counter(
    'celery_tasks_failed_total',
    'Total tasks failed',
    ['task_name', 'queue']
)

TASKS_RETRIED = Counter(
    'celery_tasks_retried_total',
    'Total task retries',
    ['task_name', 'queue']
)


# Task latency histogram
TASK_DURATION = Histogram(
    'celery_task_duration_seconds',
    'Task execution time in seconds',
    ['task_name', 'queue'],
    buckets=(5, 10, 30, 60, 120, 300, 600, 1200, 1800, float('inf'))
)


# Queue gauges
QUEUE_LENGTH = Gauge(
    'celery_queue_length',
    'Number of tasks in queue',
    ['queue']
)

ACTIVE_WORKERS = Gauge(
    'celery_active_workers',
    'Number of active workers',
    ['queue']
)


# Custom task timer context
class TaskTimer:
    """Context manager for timing tasks."""

    def __init__(self, task_name: str, queue: str = 'default'):
        self.task_name = task_name
        self.queue = queue
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        TASKS_RECEIVED.labels(self.task_name, self.queue).inc()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        TASK_DURATION.labels(self.task_name, self.queue).observe(duration)

        if exc_type is None:
            TASKS_SUCCEEDED.labels(self.task_name, self.queue).inc()
        else:
            TASKS_FAILED.labels(self.task_name, self.queue).inc()


def start_metrics_server(port: int = 9999):
    """Start Prometheus metrics HTTP server."""
    start_http_server(port)
    print(f"Prometheus metrics server started on port {port}")
```

### Celery Signals for Metrics

**File:** `celery_queue/signals.py`

```python
"""
Celery Signal Handlers for Metrics

Automatically captures task lifecycle events for Prometheus.
"""

from celery import signals
from .metrics import (
    TASKS_RECEIVED, TASKS_SUCCEEDED, TASKS_FAILED,
    TASKS_RETRIED, TASK_DURATION
)
import time


task_start_times = {}


@signals.task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    """Called before task execution."""
    task_start_times[task_id] = time.time()
    queue = getattr(task, 'queue', 'default') or 'default'
    TASKS_RECEIVED.labels(task.name, queue).inc()


@signals.task_success.connect
def task_success_handler(sender, result, **kwargs):
    """Called on task success."""
    task_id = sender.request.id
    queue = getattr(sender, 'queue', 'default') or 'default'

    TASKS_SUCCEEDED.labels(sender.name, queue).inc()

    if task_id in task_start_times:
        duration = time.time() - task_start_times.pop(task_id)
        TASK_DURATION.labels(sender.name, queue).observe(duration)


@signals.task_failure.connect
def task_failure_handler(sender, task_id, exception, *args, **kwargs):
    """Called on task failure."""
    queue = getattr(sender, 'queue', 'default') or 'default'
    TASKS_FAILED.labels(sender.name, queue).inc()

    if task_id in task_start_times:
        duration = time.time() - task_start_times.pop(task_id)
        TASK_DURATION.labels(sender.name, queue).observe(duration)


@signals.task_retry.connect
def task_retry_handler(sender, reason, *args, **kwargs):
    """Called on task retry."""
    queue = getattr(sender, 'queue', 'default') or 'default'
    TASKS_RETRIED.labels(sender.name, queue).inc()
```

### Prometheus Configuration

**File:** `prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

scrape_configs:
  # Celery metrics
  - job_name: "celery"
    static_configs:
      - targets: ["localhost:9999"]
    metrics_path: /metrics

  # Redis exporter
  - job_name: "redis"
    static_configs:
      - targets: ["localhost:9121"]

  # FastAPI application
  - job_name: "fastapi"
    static_configs:
      - targets: ["localhost:8000"]
    metrics_path: /metrics
```

### Docker Compose with Prometheus

**Add to `docker-compose.monitoring.yml`:**

```yaml
  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: agensium-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./alerts.yml:/etc/prometheus/alerts.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=15d'
    restart: unless-stopped
    networks:
      - agensium-network

  redis-exporter:
    image: oliver006/redis_exporter:latest
    container_name: agensium-redis-exporter
    ports:
      - "9121:9121"
    environment:
      - REDIS_ADDR=redis://redis:6379
    depends_on:
      - redis
    restart: unless-stopped
    networks:
      - agensium-network

volumes:
  prometheus_data:
```

---

## Grafana Dashboards

### Docker Setup

```yaml
  grafana:
    image: grafana/grafana:10.2.2
    container_name: agensium-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_INSTALL_PLUGINS=redis-datasource
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    depends_on:
      - prometheus
    restart: unless-stopped
    networks:
      - agensium-network

volumes:
  grafana_data:
```

### Datasource Configuration

**File:** `grafana/datasources/prometheus.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

### Celery Dashboard JSON

**File:** `grafana/dashboards/celery.json`

```json
{
  "dashboard": {
    "id": null,
    "title": "Agensium Celery Queue",
    "tags": ["celery", "queue"],
    "timezone": "browser",
    "panels": [
      {
        "title": "Tasks Per Second",
        "type": "graph",
        "gridPos": { "x": 0, "y": 0, "w": 12, "h": 8 },
        "targets": [
          {
            "expr": "rate(celery_tasks_succeeded_total[5m])",
            "legendFormat": "{{task_name}}"
          }
        ]
      },
      {
        "title": "Task Duration (95th)",
        "type": "graph",
        "gridPos": { "x": 12, "y": 0, "w": 12, "h": 8 },
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(celery_task_duration_seconds_bucket[5m]))",
            "legendFormat": "{{task_name}}"
          }
        ]
      },
      {
        "title": "Success Rate",
        "type": "gauge",
        "gridPos": { "x": 0, "y": 8, "w": 6, "h": 6 },
        "targets": [
          {
            "expr": "sum(rate(celery_tasks_succeeded_total[5m])) / sum(rate(celery_tasks_received_total[5m])) * 100"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "thresholds": {
              "mode": "absolute",
              "steps": [
                { "value": 0, "color": "red" },
                { "value": 95, "color": "yellow" },
                { "value": 99, "color": "green" }
              ]
            }
          }
        }
      },
      {
        "title": "Queue Depth",
        "type": "stat",
        "gridPos": { "x": 6, "y": 8, "w": 6, "h": 6 },
        "targets": [
          {
            "expr": "celery_queue_length"
          }
        ]
      },
      {
        "title": "Failed Tasks",
        "type": "stat",
        "gridPos": { "x": 12, "y": 8, "w": 6, "h": 6 },
        "targets": [
          {
            "expr": "sum(increase(celery_tasks_failed_total[1h]))"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "mode": "absolute",
              "steps": [
                { "value": 0, "color": "green" },
                { "value": 5, "color": "yellow" },
                { "value": 10, "color": "red" }
              ]
            }
          }
        }
      },
      {
        "title": "Active Workers",
        "type": "stat",
        "gridPos": { "x": 18, "y": 8, "w": 6, "h": 6 },
        "targets": [
          {
            "expr": "celery_active_workers"
          }
        ]
      }
    ]
  }
}
```

---

## Redis Monitoring

### Redis CLI Commands

```powershell
# Connect to Redis
redis-cli

# Check server info
INFO

# Check memory usage
INFO memory

# Check connected clients
INFO clients

# Check replication
INFO replication

# Monitor commands in real-time
MONITOR

# Check slow log
SLOWLOG GET 10
```

### Redis Key Metrics

| Metric    | Command         | Healthy Value                   |
| --------- | --------------- | ------------------------------- | ------------ |
| Memory    | `INFO memory    | grep used_memory_human`         | < 80% of max |
| Clients   | `INFO clients   | grep connected_clients`         | < 100        |
| Keyspace  | `INFO keyspace` | Varies                          |
| Ops/sec   | `INFO stats     | grep instantaneous_ops_per_sec` | Varies       |
| Evictions | `INFO stats     | grep evicted_keys`              | 0            |

### Python Redis Health Check

**File:** `celery_queue/health.py`

```python
"""
Queue Health Checks

Provides health check functions for Redis and Celery.
"""

import redis
from typing import Dict, Any
import logging

from .celery_app import celery_app
from .config import get_queue_config

logger = logging.getLogger(__name__)


def check_redis_health() -> Dict[str, Any]:
    """
    Check Redis connection and health.

    Returns:
        Dict with health status and metrics
    """
    config = get_queue_config()

    try:
        client = redis.from_url(config.redis_url)

        # Basic connectivity
        ping = client.ping()

        # Get info
        info = client.info()

        return {
            "status": "healthy" if ping else "unhealthy",
            "connected": ping,
            "version": info.get("redis_version"),
            "uptime_seconds": info.get("uptime_in_seconds"),
            "connected_clients": info.get("connected_clients"),
            "used_memory_human": info.get("used_memory_human"),
            "used_memory_peak_human": info.get("used_memory_peak_human"),
            "total_keys": sum(
                info.get(f"db{i}", {}).get("keys", 0)
                for i in range(16)
            ),
            "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec")
        }

    except redis.ConnectionError as e:
        logger.error(f"Redis connection failed: {e}")
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e)
        }
    except Exception as e:
        logger.exception(f"Redis health check failed: {e}")
        return {
            "status": "error",
            "connected": False,
            "error": str(e)
        }


def check_celery_health() -> Dict[str, Any]:
    """
    Check Celery workers health.

    Returns:
        Dict with health status and worker info
    """
    try:
        # Ping workers
        inspect = celery_app.control.inspect()

        ping_result = inspect.ping()
        active_result = inspect.active()
        stats_result = inspect.stats()

        if not ping_result:
            return {
                "status": "unhealthy",
                "workers": 0,
                "error": "No workers responding"
            }

        workers = []
        for worker_name, worker_stats in (stats_result or {}).items():
            workers.append({
                "name": worker_name,
                "pool": worker_stats.get("pool", {}).get("implementation"),
                "concurrency": worker_stats.get("pool", {}).get("max-concurrency"),
                "active_tasks": len((active_result or {}).get(worker_name, [])),
                "processed": worker_stats.get("total", {})
            })

        return {
            "status": "healthy",
            "workers": len(workers),
            "worker_details": workers,
            "total_active_tasks": sum(w["active_tasks"] for w in workers)
        }

    except Exception as e:
        logger.exception(f"Celery health check failed: {e}")
        return {
            "status": "error",
            "workers": 0,
            "error": str(e)
        }


def get_queue_stats() -> Dict[str, Any]:
    """
    Get queue statistics.

    Returns:
        Dict with queue depths and rates
    """
    config = get_queue_config()

    try:
        client = redis.from_url(config.redis_url)

        queues = {
            "default": client.llen("celery"),
            "profile": client.llen("profile"),
            "clean": client.llen("clean"),
            "master": client.llen("master"),
        }

        return {
            "status": "ok",
            "queues": queues,
            "total_pending": sum(queues.values())
        }

    except Exception as e:
        logger.exception(f"Failed to get queue stats: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
```

---

## Application Logging

### Structured Logging Configuration

**File:** `celery_queue/logging_config.py`

```python
"""
Logging Configuration for Queue System

Provides structured logging with task context.
"""

import logging
import logging.config
import json
from datetime import datetime
import sys


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields
        if hasattr(record, "task_id"):
            log_data["task_id"] = record.task_id

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        if hasattr(record, "agent"):
            log_data["agent"] = record.agent

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": JSONFormatter
        },
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": sys.stdout
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "json",
            "filename": "logs/celery.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5
        }
    },
    "loggers": {
        "queue": {
            "level": "INFO",
            "handlers": ["console", "file"],
            "propagate": False
        },
        "celery": {
            "level": "INFO",
            "handlers": ["console", "file"],
            "propagate": False
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"]
    }
}


def configure_logging():
    """Apply logging configuration."""
    import os
    os.makedirs("logs", exist_ok=True)
    logging.config.dictConfig(LOGGING_CONFIG)
```

### Task Logging Context

```python
import logging
from functools import wraps

def with_task_context(func):
    """Decorator to add task context to logs."""
    @wraps(func)
    def wrapper(self, task_id: str, user_id: int, *args, **kwargs):
        logger = logging.getLogger("queue.tasks")

        # Create adapter with context
        extra = {"task_id": task_id, "user_id": user_id}

        logger.info(
            f"Starting task {task_id}",
            extra=extra
        )

        try:
            result = func(self, task_id, user_id, *args, **kwargs)
            logger.info(
                f"Completed task {task_id}",
                extra=extra
            )
            return result
        except Exception as e:
            logger.exception(
                f"Failed task {task_id}: {e}",
                extra=extra
            )
            raise

    return wrapper
```

---

## Alerting Configuration

### Prometheus Alerts

**File:** `alerts.yml`

```yaml
groups:
  - name: celery_alerts
    rules:
      # No workers available
      - alert: CeleryNoWorkers
        expr: celery_active_workers == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "No Celery workers available"
          description: "No Celery workers have been active for 2 minutes"

      # High queue depth
      - alert: CeleryHighQueueDepth
        expr: celery_queue_length > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High queue depth"
          description: "Queue depth is {{ $value }} tasks"

      # High failure rate
      - alert: CeleryHighFailureRate
        expr: |
          sum(rate(celery_tasks_failed_total[5m])) 
          / sum(rate(celery_tasks_received_total[5m])) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High task failure rate"
          description: "Failure rate is {{ $value | humanizePercentage }}"

      # Task duration too high
      - alert: CelerySlowTasks
        expr: histogram_quantile(0.95, rate(celery_task_duration_seconds_bucket[5m])) > 600
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Tasks running slowly"
          description: "95th percentile task duration is {{ $value }}s"

  - name: redis_alerts
    rules:
      # Redis down
      - alert: RedisDown
        expr: redis_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis is down"
          description: "Redis has been unreachable for 1 minute"

      # Redis high memory
      - alert: RedisHighMemory
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Redis high memory usage"
          description: "Redis memory usage is {{ $value | humanizePercentage }}"
```

---

## Health Check Endpoints

### FastAPI Health Routes

**File:** `api/health.py`

```python
"""
Health Check Endpoints

Provides health status for load balancers and monitoring.
"""

from fastapi import APIRouter, Response
from typing import Dict, Any

from queue.health import (
    check_redis_health,
    check_celery_health,
    get_queue_stats
)
from queue.config import get_queue_config

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check.

    Returns 200 if application is running.
    """
    return {"status": "ok"}


@router.get("/ready")
async def readiness_check(response: Response) -> Dict[str, Any]:
    """
    Readiness check for Kubernetes.

    Returns 200 if all dependencies are healthy.
    """
    config = get_queue_config()

    checks = {
        "database": True,  # Add DB health check
    }

    # Only check queue if using Celery
    if config.use_celery:
        redis_health = check_redis_health()
        celery_health = check_celery_health()

        checks["redis"] = redis_health.get("status") == "healthy"
        checks["celery"] = celery_health.get("status") == "healthy"

    all_healthy = all(checks.values())

    if not all_healthy:
        response.status_code = 503

    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks
    }


@router.get("/queue")
async def queue_health() -> Dict[str, Any]:
    """
    Detailed queue health status.

    Returns Redis, Celery, and queue statistics.
    """
    config = get_queue_config()

    if not config.use_celery:
        return {
            "mode": "threading",
            "celery_enabled": False
        }

    return {
        "mode": "celery",
        "celery_enabled": True,
        "redis": check_redis_health(),
        "celery": check_celery_health(),
        "queues": get_queue_stats()
    }
```

### Register Health Routes

**File:** `main.py` (update)

```python
from api.health import router as health_router

app.include_router(health_router)
```

---

## Troubleshooting Guide

### Common Issues

#### 1. Tasks Not Being Picked Up

**Symptoms:** Tasks stay in QUEUED status

**Diagnosis:**

```powershell
# Check if workers are running
celery -A celery_queue.celery_app status

# Check queue depth
redis-cli LLEN celery

# Check worker logs
celery -A celery_queue.celery_app worker --loglevel=debug
```

**Solutions:**

- Ensure workers are started
- Check Redis connectivity
- Verify queue names match

#### 2. Tasks Failing Immediately

**Symptoms:** Tasks transition to FAILED quickly

**Diagnosis:**

```powershell
# Check Flower for error details
# http://localhost:5555/tasks

# Check worker logs
tail -f logs/celery.log | grep -i error
```

**Solutions:**

- Check import errors in task modules
- Verify database connectivity
- Check S3 credentials

#### 3. Redis Connection Refused

**Symptoms:** `redis.exceptions.ConnectionError`

**Diagnosis:**

```powershell
# Check Redis is running
redis-cli ping

# Check Redis port
netstat -an | findstr 6379
```

**Solutions:**

- Start Redis: `redis-server`
- Check firewall settings
- Verify REDIS_URL in environment

#### 4. Workers Consuming Too Much Memory

**Symptoms:** Workers crash or slow down

**Diagnosis:**

```powershell
# Check worker stats
celery -A celery_queue.celery_app inspect stats
```

**Solutions:**

- Reduce `--concurrency`
- Add `--max-memory-per-child=500000`
- Use `--autoscale`

#### 5. Task Timeouts

**Symptoms:** `SoftTimeLimitExceeded` errors

**Diagnosis:**

- Check task execution times in Grafana
- Review agent processing times

**Solutions:**

- Increase `soft_time_limit`
- Optimize slow agents
- Split large tasks

---

## Next Steps

1. ✅ Review monitoring setup
2. → Install monitoring stack (Docker Compose)
3. → Configure Grafana dashboards
4. → Set up alerting
5. → Proceed to [07_DEPLOYMENT.md](07_DEPLOYMENT.md)

