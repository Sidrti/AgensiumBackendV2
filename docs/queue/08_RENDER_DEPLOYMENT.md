# Render Deployment Guide for Celery Queue System

**Document Version:** 1.0.0  
**Created:** December 24, 2025  
**Purpose:** Complete guide for deploying Celery workers on Render with proper concurrency.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Windows Development vs Production](#windows-development-vs-production)
3. [Render Services Setup](#render-services-setup)
4. [Environment Variables](#environment-variables)
5. [Worker Concurrency Explained](#worker-concurrency-explained)
6. [Flower Monitoring on Render](#flower-monitoring-on-render)
7. [Scaling Strategies](#scaling-strategies)
8. [Cost Optimization](#cost-optimization)
9. [Troubleshooting](#troubleshooting)
10. [Command Reference](#command-reference)

---

## Architecture Overview

### Production Architecture on Render

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RENDER DEPLOYMENT ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    RENDER WEB SERVICE                                │    │
│  │                 (agensium-backend-web)                               │    │
│  │                                                                      │    │
│  │  uvicorn main:app --host 0.0.0.0 --port $PORT                       │    │
│  │                                                                      │    │
│  │  Handles:                                                           │    │
│  │  - REST API requests                                                │    │
│  │  - File uploads                                                     │    │
│  │  - Task submission to queue                                         │    │
│  │  - User authentication                                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                            │                                                 │
│                            ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    REDIS CLOUD (Upstash)                            │    │
│  │                                                                      │    │
│  │  - Message broker                                                   │    │
│  │  - Task queue storage                                               │    │
│  │  - Result backend                                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                            │                                                 │
│                            ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                RENDER BACKGROUND WORKER                              │    │
│  │               (agensium-backend-worker)                              │    │
│  │                                                                      │    │
│  │  celery -A celery_queue.celery_app worker \                         │    │
│  │      --loglevel=info \                                              │    │
│  │      --concurrency=4                                                │    │
│  │                                                                      │    │
│  │  4 CONCURRENT PROCESSES:                                            │    │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                        │    │
│  │  │Worker 1│ │Worker 2│ │Worker 3│ │Worker 4│                        │    │
│  │  │ Task A │ │ Task B │ │ Task C │ │ Task D │                        │    │
│  │  └────────┘ └────────┘ └────────┘ └────────┘                        │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │            RENDER BACKGROUND WORKER (Optional)                       │    │
│  │                  (agensium-flower)                                   │    │
│  │                                                                      │    │
│  │  celery -A celery_queue.celery_app flower --port=$PORT              │    │
│  │                                                                      │    │
│  │  Monitoring Dashboard                                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Windows Development vs Production

### Why `--pool=solo` on Windows?

**The Problem:** Celery's default process pool (prefork) uses `fork()` which is a Unix-only system call. Windows doesn't support `fork()`.

**The Solution:** Use `--pool=solo` on Windows, which runs tasks in the main process sequentially.

| Environment    | Pool Type | Concurrency         | Why                          |
| -------------- | --------- | ------------------- | ---------------------------- |
| Windows Dev    | `solo`    | 1 (sequential)      | Windows can't fork processes |
| Linux/Mac Dev  | `prefork` | Multiple (parallel) | Unix supports forking        |
| Render (Linux) | `prefork` | Multiple (parallel) | Render runs Linux containers |

### Windows Development Commands

```powershell
# Windows - Single worker, sequential tasks (only option)
celery -A celery_queue.celery_app worker --loglevel=info --pool=solo

# Even with --concurrency=4, solo pool ignores it and runs sequentially
celery -A celery_queue.celery_app worker --loglevel=info --pool=solo --concurrency=4
# ↑ This still runs 1 task at a time!
```

### Alternative: Run Multiple Solo Workers on Windows

If you need to test concurrency on Windows, run multiple terminals:

```powershell
# Terminal 1
celery -A celery_queue.celery_app worker --loglevel=info --pool=solo -n worker1@%computername%

# Terminal 2
celery -A celery_queue.celery_app worker --loglevel=info --pool=solo -n worker2@%computername%

# Terminal 3
celery -A celery_queue.celery_app worker --loglevel=info --pool=solo -n worker3@%computername%

# Terminal 4
celery -A celery_queue.celery_app worker --loglevel=info --pool=solo -n worker4@%computername%
```

This simulates 4 concurrent workers, each in its own process.

### Production Commands (Render/Linux)

```bash
# Linux - Uses prefork pool by default with actual concurrency
celery -A celery_queue.celery_app worker --loglevel=info --concurrency=4

# This creates 4 worker processes that run tasks in parallel!
```

---

## Render Services Setup

### Service 1: Web Service (FastAPI)

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** → **Web Service**
3. Connect your GitHub repository
4. Configure:

```yaml
Name: agensium-backend
Region: Oregon (or closest to users)
Branch: main
Root Directory: backend # Important!
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
Instance Type: Starter ($7/mo) or Standard ($25/mo)
```

### Service 2: Background Worker (Celery)

1. Click **New** → **Background Worker**
2. Connect same GitHub repository
3. Configure:

```yaml
Name: agensium-worker
Region: Same as web service
Branch: main
Root Directory: backend # Important!
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: celery -A celery_queue.celery_app worker --loglevel=info --concurrency=4
Instance Type: Starter ($7/mo) or Standard ($25/mo)
```

**Important Notes:**

- Background Workers don't have a `$PORT` variable - they don't listen on a port
- The `--concurrency=4` flag creates 4 worker processes
- Render's Linux containers support prefork pool natively

### Service 3: Flower Monitoring (Optional)

**Option A: As a Web Service (Recommended)**

```yaml
Name: agensium-flower
Region: Same as other services
Branch: main
Root Directory: backend
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: celery -A celery_queue.celery_app flower --port=$PORT --basic_auth=admin:YOUR_SECURE_PASSWORD
Instance Type: Starter ($7/mo)
```

This exposes Flower on a public URL with basic auth protection.

**Option B: Skip Flower on Production**

Flower uses additional resources. For cost savings, you can:

- Skip Flower in production
- Use Render's logs for monitoring
- Access Redis directly for queue status

---

## Environment Variables

### Required Environment Variables for All Services

Set these in Render Dashboard → Service → Environment:

```env
# =============================================================================
# REDIS CLOUD (Upstash) - Required for all services
# =============================================================================
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST.upstash.io:6379
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}

# =============================================================================
# CELERY SETTINGS
# =============================================================================
USE_CELERY=true
CELERY_WORKER_CONCURRENCY=4
CELERY_TASK_TIME_LIMIT=1800
CELERY_TASK_SOFT_TIME_LIMIT=1500

# =============================================================================
# DATABASE (PlanetScale or other MySQL)
# =============================================================================
DATABASE_URL=mysql+pymysql://user:password@host:3306/database

# =============================================================================
# S3 STORAGE (Backblaze B2)
# =============================================================================
S3_ENDPOINT_URL=https://s3.us-west-000.backblazeb2.com
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_BUCKET_NAME=your-bucket

# =============================================================================
# OPENAI
# =============================================================================
OPENAI_API_KEY=sk-your-api-key

# =============================================================================
# APPLICATION
# =============================================================================
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### Using Environment Groups (Render Feature)

Render allows creating environment groups to share variables across services:

1. Go to **Settings** → **Environment Groups**
2. Create group: `agensium-shared`
3. Add all common variables
4. Link group to all three services (web, worker, flower)

---

## Worker Concurrency Explained

### What is Concurrency?

Concurrency is the number of tasks a worker can process **simultaneously**.

```
Concurrency=4 means:
┌─────────────────────────────────────────────────────────────┐
│                   CELERY WORKER PROCESS                     │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Child 1  │ │ Child 2  │ │ Child 3  │ │ Child 4  │       │
│  │ Task A   │ │ Task B   │ │ Task C   │ │ Task D   │       │
│  │ Running  │ │ Running  │ │ Running  │ │ Running  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                             │
│  All 4 tasks run at the SAME TIME!                         │
└─────────────────────────────────────────────────────────────┘
```

### How to Choose Concurrency

| Instance Type  | CPU Cores | Recommended Concurrency |
| -------------- | --------- | ----------------------- |
| Starter ($7)   | Shared    | 2                       |
| Standard ($25) | 0.5       | 2                       |
| Pro ($85)      | 1         | 4                       |
| Pro+ ($175)    | 2         | 8                       |

**Rule of thumb:** `concurrency = 2 * CPU cores` for I/O-bound tasks

### Memory Considerations

Each worker process uses memory. With concurrency=4:

```
Total Memory = Base Memory + (4 × Per-Task Memory)

Example for data analysis:
- Base: 100MB
- Per task: 200-400MB (loading DataFrames)
- Total: 100 + (4 × 300) = 1.3GB needed
```

**Render Memory Limits:**
| Plan | Memory | Safe Concurrency |
|------|--------|------------------|
| Starter | 512MB | 1-2 |
| Standard | 2GB | 4 |
| Pro | 4GB | 8 |

---

## Flower Monitoring on Render

### Accessing Flower Dashboard

If deployed as a web service:

```
https://agensium-flower.onrender.com
Username: admin
Password: YOUR_SECURE_PASSWORD (from start command)
```

### Flower Dashboard Features

1. **Workers Tab:**

   - See all connected workers
   - View concurrency per worker
   - Monitor CPU/memory usage

2. **Tasks Tab:**

   - View task history
   - See success/failure rates
   - Inspect task arguments and results

3. **Broker Tab:**
   - Monitor queue length
   - View message rates

### Flower Environment Variables

```env
# Optional Flower settings
FLOWER_BASIC_AUTH=admin:secure_password
FLOWER_URL_PREFIX=/flower
FLOWER_PURGE_OFFLINE_WORKERS=300
```

### Security: Protecting Flower

**Option 1: Basic Auth (Simple)**

```bash
celery -A celery_queue.celery_app flower --port=$PORT --basic_auth=admin:password
```

**Option 2: Using Environment Variable**

```env
FLOWER_BASIC_AUTH=admin:password
```

**Option 3: IP Whitelist (Render)**
Render doesn't support IP whitelisting on standard plans.

---

## Scaling Strategies

### Horizontal Scaling (More Workers)

Create multiple worker services in Render:

```yaml
# Service: agensium-worker-1
Start Command: celery -A celery_queue.celery_app worker --loglevel=info --concurrency=4 -n worker1@%h

# Service: agensium-worker-2
Start Command: celery -A celery_queue.celery_app worker --loglevel=info --concurrency=4 -n worker2@%h
```

This gives you 8 concurrent tasks (4 per worker).

### Vertical Scaling (Bigger Workers)

Upgrade instance type:

- Starter → Standard: More CPU/memory
- Standard → Pro: More resources

Then increase concurrency:

```bash
celery -A celery_queue.celery_app worker --loglevel=info --concurrency=8
```

### Auto-Scaling (Not Available on Render)

Render doesn't support auto-scaling for background workers.

**Alternative: Queue-Based Scaling**

1. Monitor queue length via Flower or Redis
2. Manually add/remove worker services as needed

---

## Cost Optimization

### Minimum Viable Setup ($14/month)

| Service         | Instance | Cost       |
| --------------- | -------- | ---------- |
| Web (FastAPI)   | Starter  | $7/mo      |
| Worker (Celery) | Starter  | $7/mo      |
| Flower          | Skip     | $0         |
| **Total**       |          | **$14/mo** |

### Recommended Production Setup ($32/month)

| Service         | Instance | Cost       |
| --------------- | -------- | ---------- |
| Web (FastAPI)   | Starter  | $7/mo      |
| Worker (Celery) | Standard | $25/mo     |
| Flower          | Skip     | $0         |
| **Total**       |          | **$32/mo** |

### High Volume Setup ($57/month)

| Service         | Instance | Cost       |
| --------------- | -------- | ---------- |
| Web (FastAPI)   | Standard | $25/mo     |
| Worker (Celery) | Standard | $25/mo     |
| Flower          | Starter  | $7/mo      |
| **Total**       |          | **$57/mo** |

### External Service Costs

| Service               | Plan          | Cost     |
| --------------------- | ------------- | -------- |
| Redis Cloud (Upstash) | Free tier     | $0       |
| MySQL (PlanetScale)   | Hobby         | $0       |
| S3 (Backblaze B2)     | Pay as you go | ~$1-5/mo |

---

## Troubleshooting

### Worker Not Starting

**Error:** `ModuleNotFoundError: No module named 'celery_queue'`

**Solution:** Ensure `Root Directory` is set to `backend` in Render settings.

### Worker Not Processing Tasks

**Check 1:** Verify REDIS_URL is the same for web and worker

```python
# In Python shell
import os
print(os.getenv("REDIS_URL"))
```

**Check 2:** Verify worker is connected

Look for this in worker logs:

```
[2025-12-24 10:00:00,000: INFO/MainProcess] Connected to rediss://...
[2025-12-24 10:00:00,000: INFO/MainProcess] celery@... ready.
```

### Tasks Stuck in Queue

**Check queue length:**

```python
import redis
import os
r = redis.from_url(os.getenv("REDIS_URL"))
print(r.llen("celery"))  # Number of pending tasks
```

### Memory Issues

**Error:** `Worker exited prematurely: signal 9 (SIGKILL)`

**Solution:** Reduce concurrency or upgrade instance:

```bash
# Reduce concurrency
celery -A celery_queue.celery_app worker --loglevel=info --concurrency=2
```

### Connection Timeouts

**Error:** `ConnectionError: Error 110 connecting to redis`

**Solution:** Check Redis URL format and increase timeouts in celery_config.py:

```python
broker_transport_options = {
    'socket_timeout': 60,
    'socket_connect_timeout': 60,
}
```

---

## Command Reference

### Development (Windows)

```powershell
# Start FastAPI
uvicorn main:app --reload --port 8000

# Start single Celery worker (solo pool - only option on Windows)
celery -A celery_queue.celery_app worker --loglevel=info --pool=solo

# Start multiple workers (multiple terminals)
celery -A celery_queue.celery_app worker --loglevel=info --pool=solo -n worker1@%computername%
celery -A celery_queue.celery_app worker --loglevel=info --pool=solo -n worker2@%computername%

# Start Flower
celery -A celery_queue.celery_app flower --port=5555
```

### Production (Render/Linux)

```bash
# FastAPI (Web Service)
uvicorn main:app --host 0.0.0.0 --port $PORT

# Celery Worker (Background Worker)
celery -A celery_queue.celery_app worker --loglevel=info --concurrency=4

# Flower with auth (Web Service)
celery -A celery_queue.celery_app flower --port=$PORT --basic_auth=admin:password
```

### Celery Management Commands

```bash
# List registered tasks
celery -A celery_queue.celery_app inspect registered

# List active tasks
celery -A celery_queue.celery_app inspect active

# Purge all tasks (dangerous!)
celery -A celery_queue.celery_app purge

# Check worker status
celery -A celery_queue.celery_app status
```

---

## Deployment Checklist

### Before Deployment

- [ ] Redis Cloud (Upstash) set up and tested
- [ ] All environment variables documented
- [ ] requirements.txt includes celery, redis, flower

### Deploy Web Service

- [ ] Create Web Service in Render
- [ ] Set Root Directory to `backend`
- [ ] Configure start command
- [ ] Add all environment variables
- [ ] Test API endpoints

### Deploy Worker Service

- [ ] Create Background Worker in Render
- [ ] Set Root Directory to `backend`
- [ ] Configure start command with `--concurrency=4`
- [ ] Add same environment variables as web
- [ ] Verify worker connects (check logs)

### Deploy Flower (Optional)

- [ ] Create Web Service for Flower
- [ ] Add `--basic_auth` for security
- [ ] Verify dashboard accessible
- [ ] Verify workers show up

### Post-Deployment Testing

- [ ] Submit a test task through API
- [ ] Verify task appears in Celery logs
- [ ] Verify task completes successfully
- [ ] Check task status via API
- [ ] Monitor memory/CPU usage

---

## Summary

| Aspect           | Windows Development | Render Production           |
| ---------------- | ------------------- | --------------------------- |
| Pool             | `--pool=solo`       | `prefork` (default)         |
| Concurrency      | 1 per terminal      | 4 per worker (configurable) |
| Multiple Workers | Multiple terminals  | Multiple services           |
| Flower           | Optional            | Optional (adds $7/mo)       |
| Memory           | N/A                 | Monitor and scale           |

**Key Takeaways:**

1. **Windows can't do real concurrency** - Use `--pool=solo` and run multiple terminals if needed
2. **Render uses Linux** - Full concurrency works with `--concurrency=4`
3. **Monitor memory** - Reduce concurrency if workers get killed
4. **Flower is optional** - Skip it to save $7/month
5. **Use Environment Groups** - Share variables across services

---

## Next Steps

1. ✅ Understand Windows vs Linux concurrency
2. → Set up services in Render Dashboard
3. → Configure environment variables
4. → Deploy and test
5. → Monitor with Flower or logs
