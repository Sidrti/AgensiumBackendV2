# Deployment Guide

**Document Version:** 2.0.0  
**Updated:** December 23, 2025  
**Purpose:** Deploy the Celery + Redis Cloud queue system for Agensium.

---

## Table of Contents

1. [Deployment Overview](#deployment-overview)
2. [Local Development](#local-development)
3. [Production Deployment (Railway/Render)](#production-deployment-railwayrender)
4. [Environment Configuration](#environment-configuration)
5. [Scaling Workers](#scaling-workers)
6. [Monitoring with Flower](#monitoring-with-flower)
7. [Troubleshooting](#troubleshooting)

---

## Deployment Overview

### Simplified Architecture

With Redis Cloud, the deployment is much simpler:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AGENSIUM PRODUCTION ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                         YOUR HOSTING                               │     │
│   │              (Railway, Render, Heroku, VPS, etc.)                  │     │
│   │                                                                    │     │
│   │   ┌─────────────┐        ┌─────────────────────────────┐          │     │
│   │   │   FastAPI   │        │      Celery Worker(s)       │          │     │
│   │   │   Server    │        │                             │          │     │
│   │   │             │        │   Single unified worker     │          │     │
│   │   │  (Web API)  │────────│   handles all tool types    │          │     │
│   │   │             │        │                             │          │     │
│   │   └─────────────┘        └─────────────────────────────┘          │     │
│   │         │                              │                           │     │
│   │         │                              │                           │     │
│   └─────────┼──────────────────────────────┼───────────────────────────┘     │
│             │                              │                                  │
│             ▼                              ▼                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                       MANAGED SERVICES                               │   │
│   │                                                                      │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│   │   │ Redis Cloud │  │    MySQL    │  │ Backblaze   │                 │   │
│   │   │  (Upstash)  │  │ (PlanetScale│  │     B2      │                 │   │
│   │   │             │  │  or Railway)│  │   (S3)      │                 │   │
│   │   │  Message    │  │             │  │             │                 │   │
│   │   │  Broker     │  │  Database   │  │  Files      │                 │   │
│   │   └─────────────┘  └─────────────┘  └─────────────┘                 │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### What You Need

| Service            | Purpose       | Recommendation                 |
| ------------------ | ------------- | ------------------------------ |
| **Web Hosting**    | Run FastAPI   | Railway, Render, or any VPS    |
| **Worker Hosting** | Run Celery    | Same as web (separate process) |
| **Redis**          | Message queue | Upstash (free tier)            |
| **MySQL**          | Database      | PlanetScale or Railway         |
| **S3 Storage**     | Files         | Backblaze B2 (already set up)  |

**No Docker or Kubernetes required!**

---

## Local Development

### Prerequisites

1. **Python 3.11+** - Backend runtime
2. **Redis Cloud account** - For message broker (Upstash recommended)
3. **Virtual environment** - Already set up

### Quick Start

```powershell
# 1. Navigate to backend
cd "c:\Users\VIVEK BANSAL\Desktop\Agensium\Agensium-V2\backend"

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies (if needed)
pip install -r requirements.txt

# 4. Configure environment
# Edit .env and add your REDIS_URL from Upstash

# 5. Start FastAPI (Terminal 1)
uvicorn main:app --reload --port 8000

# 6. Start Celery Worker (Terminal 2)
celery -A queue.celery_app worker --loglevel=info --pool=solo

# 7. Start Flower (Optional, Terminal 3)
celery -A queue.celery_app flower --port=5555
```

### Windows Note

On Windows, use `--pool=solo` for Celery because Windows doesn't support forking:

```powershell
celery -A queue.celery_app worker --loglevel=info --pool=solo
```

---

## Production Deployment (Railway/Render)

### Railway Deployment

Railway is recommended for its simplicity and automatic deployments.

#### Step 1: Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click **New Project** → **Deploy from GitHub**
3. Connect your Agensium backend repository

#### Step 2: Add Services

Your Railway project needs 2 services:

**Service 1: Web (FastAPI)**

```
# Settings
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

**Service 2: Worker (Celery)**

```
# Settings
Start Command: celery -A queue.celery_app worker --loglevel=info --concurrency=4
```

#### Step 3: Add Environment Variables

In Railway, go to each service → **Variables** and add:

```env
# Database
DATABASE_URL=mysql+pymysql://user:pass@host:3306/db

# Redis Cloud (from Upstash)
REDIS_URL=rediss://default:xxxx@us1-xxxx.upstash.io:6379
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
USE_CELERY=true

# S3 Storage
S3_ENDPOINT_URL=https://s3.us-west-000.backblazeb2.com
S3_ACCESS_KEY=your-key
S3_SECRET_KEY=your-secret
S3_BUCKET_NAME=your-bucket

# OpenAI
OPENAI_API_KEY=sk-xxx

# Other
DEBUG=false
LOG_LEVEL=INFO
```

#### Step 4: Deploy

Railway auto-deploys on every push to your main branch!

### Render Deployment

Similar to Railway:

1. Create Web Service for FastAPI
2. Create Background Worker for Celery
3. Add environment variables
4. Connect to your GitHub repo

### Procfile (for Heroku-style platforms)

If your hosting uses Procfile:

```procfile
web: uvicorn main:app --host 0.0.0.0 --port $PORT
worker: celery -A queue.celery_app worker --loglevel=info --concurrency=4
```

---

## Environment Configuration

### Required Environment Variables

```env
# ==============================================================================
# REDIS CLOUD (Required)
# ==============================================================================
REDIS_URL=rediss://default:PASSWORD@HOST:6379
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}

# ==============================================================================
# CELERY SETTINGS
# ==============================================================================
USE_CELERY=true
CELERY_WORKER_CONCURRENCY=4
CELERY_TASK_TIME_LIMIT=1800
CELERY_TASK_SOFT_TIME_LIMIT=1500

# ==============================================================================
# DATABASE
# ==============================================================================
DATABASE_URL=mysql+pymysql://user:password@host:3306/database

# ==============================================================================
# S3 STORAGE
# ==============================================================================
S3_ENDPOINT_URL=https://s3.us-west-000.backblazeb2.com
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_BUCKET_NAME=your-bucket

# ==============================================================================
# OPENAI
# ==============================================================================
OPENAI_API_KEY=sk-your-api-key

# ==============================================================================
# APPLICATION
# ==============================================================================
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=production
```

---

## Scaling Workers

### When to Scale

| Symptom                | Action                            |
| ---------------------- | --------------------------------- |
| Tasks wait > 5 minutes | Add more workers                  |
| Worker CPU > 80%       | Add more workers                  |
| Memory usage > 70%     | Reduce concurrency or add workers |

### How to Scale

**Railway:**

- Create additional worker services
- Or increase the worker's resources

**Manual scaling:**

```bash
# Run 2 worker processes, each with 4 concurrent tasks
celery -A queue.celery_app worker --loglevel=info --concurrency=4

# In another terminal/service
celery -A queue.celery_app worker --loglevel=info --concurrency=4
```

### Recommended Configuration

| Stage  | Workers | Concurrency per Worker | Total Capacity      |
| ------ | ------- | ---------------------- | ------------------- |
| Start  | 1       | 4                      | 4 concurrent tasks  |
| Growth | 2       | 4                      | 8 concurrent tasks  |
| Scale  | 4       | 4                      | 16 concurrent tasks |

---

## Monitoring with Flower

Flower provides a web UI to monitor Celery tasks.

### Local Development

```powershell
# Start Flower on port 5555
celery -A queue.celery_app flower --port=5555

# Open in browser
start http://localhost:5555
```

### Production

**Option 1: Run as separate service**

Railway/Render:

```
Start Command: celery -A queue.celery_app flower --port=$PORT --basic_auth=admin:password
```

**Option 2: Use Flower Cloud** (if available)

### Flower Dashboard Features

- **Workers**: See which workers are online
- **Tasks**: View task history, success/failure rates
- **Queues**: Monitor queue depth
- **Graphs**: Task throughput over time

---

## Troubleshooting

### Worker not starting

```powershell
# Check for errors
celery -A queue.celery_app worker --loglevel=debug --pool=solo
```

**Common issues:**

1. `REDIS_URL` not set or incorrect
2. Missing dependencies (`pip install celery redis`)
3. Import errors in queue module

### Tasks stuck in queue

```python
# Check queue length
import redis
r = redis.from_url(os.getenv("REDIS_URL"))
print(r.llen("celery"))
```

**Solutions:**

1. Ensure worker is running
2. Check worker logs for errors
3. Verify REDIS_URL is same for API and worker

### Tasks failing silently

1. Check worker logs
2. Verify database connection works from worker
3. Check S3 credentials are accessible

### Connection timeout to Redis Cloud

```python
# Test connection
import redis
r = redis.from_url("rediss://default:xxx@host:6379")
print(r.ping())  # Should print True
```

**Solutions:**

1. Verify URL format (`rediss://` for TLS)
2. Check password is correct
3. Ensure network allows outbound connections

---

## Summary

### Local Development

```powershell
# Terminal 1: FastAPI
uvicorn main:app --reload --port 8000

# Terminal 2: Celery Worker
celery -A queue.celery_app worker --loglevel=info --pool=solo

# Terminal 3 (optional): Flower
celery -A queue.celery_app flower --port=5555
```

### Production Checklist

- [ ] Redis Cloud set up (Upstash)
- [ ] REDIS_URL configured in environment
- [ ] FastAPI service running
- [ ] Celery worker service running
- [ ] Flower monitoring (optional)
- [ ] Database accessible
- [ ] S3 credentials configured

---

## Next Steps

1. ✅ Set up Redis Cloud (see [03_REDIS_SETUP.md](03_REDIS_SETUP.md))
2. ✅ Configure environment variables
3. → Deploy FastAPI service
4. → Deploy Celery worker service
5. → Verify tasks are processing
