# Deployment Guide for Agensium Backend

This document outlines the resource requirements, specifications, and scalability strategies for deploying the Agensium Backend application.

## 1. System Requirements

The resource requirements heavily depend on the size of the datasets being processed, as the application currently performs in-memory data processing using Polars and Pandas.

### Minimum Requirements (Development / Small Datasets < 100MB)

- **CPU:** 2 vCPUs
- **RAM:** 4 GB
- **Storage:** 10 GB SSD
- **OS:** Ubuntu 22.04 LTS / Debian 11

### Recommended Requirements (Production / Medium Datasets up to 1GB)

- **CPU:** 4+ vCPUs (Compute Optimized)
- **RAM:** 16 GB - 32 GB
- **Storage:** 50 GB NVMe SSD
- **OS:** Ubuntu 22.04 LTS

### High Performance Requirements (Large Datasets > 1GB)

- **CPU:** 8+ vCPUs
- **RAM:** 64 GB+ (Rule of thumb: 3-5x the size of the largest dataset to be processed concurrently)
- **Storage:** 100 GB+ NVMe SSD

## 2. Software Specifications

- **Language:** Python 3.10+
- **Framework:** FastAPI
- **Server:** Uvicorn (ASGI)
- **Database:**
  - _Current:_ SQLite (Development only)
  - _Production:_ MySQL 8+ is **strongly recommended** to handle concurrent writes and multiple API hits.
- **External Services:**
  - OpenAI API Key (Required for AI agents)

## 3. Deployment Architecture

### Single Instance (Simple Deployment)

Suitable for low traffic and small teams.

```mermaid
graph LR
    Client --> Nginx[Nginx Reverse Proxy]
    Nginx --> Uvicorn[Uvicorn / FastAPI]
    Uvicorn --> SQLite[(SQLite DB)]
```

### Scalable Architecture (Production)

Suitable for high traffic and multiple concurrent users.

```mermaid
graph LR
    Client --> LB[Load Balancer]
    LB --> App1[App Instance 1]
    LB --> App2[App Instance 2]
    LB --> AppN[App Instance N]
    App1 --> DB[(MySQL Primary)]
    App2 --> DB
    AppN --> DB
```

## 4. Handling Multiple API Hits & Scalability

The current application processes data synchronously in memory. This presents challenges for scaling.

### Bottlenecks

1.  **Memory Usage:** Each concurrent file upload/processing request consumes RAM proportional to the file size. If 10 users upload 500MB files simultaneously, the server needs ~15-20GB RAM instantly.
2.  **CPU Blocking:** Heavy data processing (profiling, cleansing) blocks the CPU. Although FastAPI is async, CPU-bound tasks in Python can block the event loop if not handled correctly (e.g., running in a thread pool).
3.  **Database Locking:** SQLite locks the entire database file during writes, causing failures under high concurrency.

### Scaling Strategies

#### 1. Vertical Scaling (Scale Up)

Increase the RAM and CPU of the single server. This is the easiest immediate fix but has a ceiling.

#### 2. Horizontal Scaling (Scale Out)

- **Migrate to MySQL:** Replace SQLite with MySQL to allow concurrent database connections from multiple application instances.
- **Load Balancing:** Deploy multiple instances of the application behind a Load Balancer (e.g., AWS ALB, Nginx).
- **Containerization:** Dockerize the application to easily spin up new instances.

#### 3. Asynchronous Processing (Recommended for V2)

For a robust production environment, long-running data tasks should be offloaded to a background worker queue.

- **Architecture:** API receives file -> Saves to S3/Blob Storage -> Pushes job to Redis Queue -> Celery Worker picks up job -> Processes data -> Updates DB.
- **Benefit:** The API remains responsive, and you can scale "Workers" independently of "Web Servers".

## 5. Configuration

### Environment Variables

Ensure the following environment variables are set in production:

```bash
# Application
PORT=8000
FRONTEND_URL=https://your-frontend-domain.com

# Database (If migrating to MySQL)
DATABASE_URL=mysql+mysqlconnector://user:password@host:3306/dbname

# Security
SECRET_KEY=your-super-secret-key-change-this
ALGORITHM=HS256

# External APIs
OPENAI_API_KEY=sk-...
```

### Gunicorn with Uvicorn Workers

In production, run the application using Gunicorn as a process manager with Uvicorn workers to utilize multiple CPU cores.

```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

_`-w 4`: Number of workers (usually 2 x CPU cores + 1)_

## 6. Monitoring & Maintenance

- **Resource Monitoring:** Use tools like Prometheus/Grafana or Datadog to monitor RAM and CPU usage. Set alerts for >80% memory usage.
- **Logs:** Centralize logs (e.g., ELK stack, CloudWatch) to track errors during data processing.
- **Database Backups:** Schedule daily backups of the MySQL database.
