# Redis Cloud Setup Guide

**Document Version:** 2.0.0  
**Updated:** December 23, 2025  
**Purpose:** Step-by-step guide for setting up Redis Cloud as the message broker for Celery.

---

## Table of Contents

1. [Overview](#overview)
2. [Why Redis Cloud?](#why-redis-cloud)
3. [Redis Cloud Providers](#redis-cloud-providers)
4. [Upstash Setup (Recommended)](#upstash-setup-recommended)
5. [Railway Redis Setup](#railway-redis-setup)
6. [Configuration](#configuration)
7. [Testing Connection](#testing-connection)
8. [Local Development (Optional)](#local-development-optional)
9. [Troubleshooting](#troubleshooting)

---

## Overview

Redis serves two purposes in our architecture:

1. **Message Broker**: Stores task messages for Celery workers
2. **Result Backend**: Stores task results temporarily

**We use Redis Cloud instead of self-hosted Redis** for:

- Zero maintenance
- Automatic scaling
- Built-in security (TLS)
- No Docker/Kubernetes complexity

---

## Why Redis Cloud?

| Aspect              | Self-hosted Redis          | Redis Cloud         |
| ------------------- | -------------------------- | ------------------- |
| **Setup Time**      | 30-60 minutes              | 5 minutes           |
| **Maintenance**     | You manage updates/backups | Fully managed       |
| **Docker Required** | Yes                        | No                  |
| **Kubernetes**      | For production scaling     | Not needed          |
| **Security**        | Manual TLS setup           | TLS included        |
| **Cost**            | Server costs + time        | Free tier available |
| **Scaling**         | Manual                     | Automatic           |

**Recommendation: Use Redis Cloud** - It removes infrastructure complexity so you can focus on building features.

---

## Redis Cloud Providers

| Provider            | Free Tier    | Best For         | Pricing         |
| ------------------- | ------------ | ---------------- | --------------- |
| **Upstash**         | 10K cmds/day | Serverless apps  | Pay-per-request |
| **Railway**         | $5 credit/mo | Full-stack apps  | $0.000231/MB/hr |
| **Redis Labs**      | 30MB         | Enterprise       | Usage-based     |
| **AWS ElastiCache** | None         | AWS-heavy stacks | Instance-based  |

**For Agensium, we recommend Upstash or Railway.**

---

## Upstash Setup (Recommended)

Upstash is perfect for Celery because:

- Pay only for commands used
- Instant global replication
- Built-in TLS
- Generous free tier

### Step 1: Create Account

1. Go to [upstash.com](https://upstash.com)
2. Sign up with GitHub or email
3. Verify your email

### Step 2: Create Redis Database

1. Click **Create Database**
2. Configure:
   - **Name**: `agensium-queue`
   - **Region**: Choose closest to your server (e.g., `us-east-1`)
   - **Type**: Regional (single region is fine for start)
3. Click **Create**

### Step 3: Get Connection URL

After creation, you'll see your connection details:

```
UPSTASH_REDIS_REST_URL=https://xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=AYxxxx...

# For Celery, use the Redis URL (not REST):
REDIS_URL=rediss://default:YOUR_PASSWORD@xxx.upstash.io:6379
```

**Important:** Note the `rediss://` (double 's') - this enables TLS.

### Step 4: Copy Connection String

Click **Redis Connect** in the dashboard and copy the connection string:

```
rediss://default:AYxxxxxx@us1-xxxxxx.upstash.io:6379
```

---

## Railway Redis Setup

Railway is great if you're already deploying your FastAPI app there.

### Step 1: Create Account

1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub

### Step 2: Create Redis Service

1. Create a new project or open existing
2. Click **+ New** → **Database** → **Add Redis**
3. Wait for provisioning (~30 seconds)

### Step 3: Get Connection URL

1. Click on the Redis service
2. Go to **Variables** tab
3. Copy `REDIS_URL`

It will look like:

```
redis://default:xxxx@containers-us-west-xxx.railway.app:6379
```

**Note:** Railway Redis uses `redis://` (no TLS by default). For production, consider Upstash.

---

## Configuration

### Environment Variables

Add to your `.env` file:

```env
# ==============================================================================
# REDIS CLOUD CONFIGURATION
# ==============================================================================

# Redis Cloud URL (from Upstash, Railway, etc.)
# Format: rediss://username:password@host:port (TLS)
#     or: redis://username:password@host:port (no TLS)
REDIS_URL=rediss://default:YOUR_PASSWORD@your-redis-host.upstash.io:6379

# Celery uses the same URL for broker and backend
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}

# Feature flag: Enable Celery queue
USE_CELERY=true
```

### Celery Configuration

Update `queue/celery_config.py`:

```python
import os

# Get Redis URL from environment
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Broker and backend use the same Redis Cloud instance
broker_url = os.getenv("CELERY_BROKER_URL", redis_url)
result_backend = os.getenv("CELERY_RESULT_BACKEND", redis_url)

# SSL/TLS settings (automatic with rediss://)
# If using rediss://, Celery handles TLS automatically

# Connection pool settings optimized for cloud Redis
broker_transport_options = {
    'visibility_timeout': 3600,  # 1 hour
    'socket_timeout': 30,
    'socket_connect_timeout': 30,
    'socket_keepalive': True,
}

# Serialization
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

# Task settings
task_acks_late = True
task_reject_on_worker_lost = True
task_time_limit = 1800  # 30 minutes
task_soft_time_limit = 1500  # 25 minutes

# Result settings
result_expires = 86400  # 24 hours

# Worker settings
worker_prefetch_multiplier = 1
worker_concurrency = int(os.getenv("CELERY_WORKER_CONCURRENCY", 4))
```

---

## Testing Connection

### Test Script: `test_redis_cloud.py`

Create this file to verify your Redis Cloud connection:

```python
"""
Redis Cloud Connection Test

Tests connection to your Redis Cloud instance.
"""

import os
import redis
from dotenv import load_dotenv

load_dotenv()

def test_redis_connection():
    print("\n" + "="*60)
    print("REDIS CLOUD CONNECTION TEST")
    print("="*60)

    redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        print("❌ REDIS_URL not set in .env")
        return False

    # Mask password for display
    display_url = redis_url.split("@")[-1] if "@" in redis_url else redis_url
    print(f"\nConnecting to: ...@{display_url}")

    try:
        # Create connection from URL
        r = redis.from_url(redis_url, decode_responses=True)

        # Test 1: Ping
        print("\n1. Testing PING...")
        response = r.ping()
        print("   ✅ PING successful")

        # Test 2: Set/Get
        print("\n2. Testing SET/GET...")
        r.set("test_key", "test_value", ex=60)
        value = r.get("test_key")
        assert value == "test_value"
        r.delete("test_key")
        print("   ✅ SET/GET successful")

        # Test 3: List operations (Celery uses these)
        print("\n3. Testing LIST operations...")
        r.delete("test_queue")
        r.lpush("test_queue", "task1", "task2")
        length = r.llen("test_queue")
        assert length == 2
        r.delete("test_queue")
        print("   ✅ LIST operations successful")

        # Test 4: Connection info
        print("\n4. Getting connection info...")
        info = r.info("server")
        print(f"   Redis Version: {info.get('redis_version', 'unknown')}")

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED - Redis Cloud is ready!")
        print("="*60 + "\n")
        return True

    except redis.ConnectionError as e:
        print(f"\n❌ Connection Error: {e}")
        print("\nCheck:")
        print("1. REDIS_URL is correct")
        print("2. Password is valid")
        print("3. Network allows outbound connections")
        return False

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


if __name__ == "__main__":
    test_redis_connection()
```

### Run the Test

```powershell
cd "c:\Users\VIVEK BANSAL\Desktop\Agensium\Agensium-V2\backend"
.\.venv\Scripts\Activate.ps1
python docs/queue/test_redis_cloud.py
```

Expected output:

```
============================================================
REDIS CLOUD CONNECTION TEST
============================================================

Connecting to: ...@us1-xxxxx.upstash.io:6379

1. Testing PING...
   ✅ PING successful

2. Testing SET/GET...
   ✅ SET/GET successful

3. Testing LIST operations...
   ✅ LIST operations successful

4. Getting connection info...
   Redis Version: 7.0.11

============================================================
✅ ALL TESTS PASSED - Redis Cloud is ready!
============================================================
```

---

## Local Development (Optional)

For local development without internet, you can optionally run Redis locally:

### Option A: Docker (Quick)

```powershell
# Start local Redis
docker run -d -p 6379:6379 --name local-redis redis:7-alpine

# Test connection
docker exec -it local-redis redis-cli ping
```

Then use in `.env`:

```env
REDIS_URL=redis://localhost:6379/0
```

### Option B: WSL (Windows)

```bash
# In WSL terminal
sudo apt update
sudo apt install redis-server
sudo service redis-server start
redis-cli ping
```

### Switching Between Local and Cloud

In your `.env`:

```env
# Development (local)
# REDIS_URL=redis://localhost:6379/0

# Production (cloud)
REDIS_URL=rediss://default:xxxx@us1-xxxx.upstash.io:6379
```

---

## Troubleshooting

### Error: "Connection refused"

**Cause:** Redis URL is wrong or network blocked.

**Solutions:**

1. Verify REDIS_URL is correct (check for typos)
2. Ensure `rediss://` (TLS) vs `redis://` is correct
3. Check firewall allows outbound connections on port 6379

### Error: "NOAUTH Authentication required"

**Cause:** Password missing or incorrect.

**Solution:**
Check your connection URL includes the password:

```
rediss://default:YOUR_PASSWORD@host:port
```

### Error: "SSL: CERTIFICATE_VERIFY_FAILED"

**Cause:** TLS certificate issues.

**Solutions:**

1. Ensure you're using `rediss://` not `redis://`
2. Update your `certifi` package: `pip install --upgrade certifi`

### Error: "Connection timed out"

**Cause:** Network issues or wrong region.

**Solutions:**

1. Choose Redis Cloud region closest to your server
2. Check network/firewall settings
3. Try increasing timeout in celery_config.py

### Upstash "Command limit exceeded"

**Cause:** Free tier limit reached.

**Solutions:**

1. Upgrade to paid plan ($0.2 per 100K commands)
2. Or use Railway with $5/month credit

---

## Security Best Practices

1. **Always use TLS** (`rediss://` not `redis://`) in production
2. **Never commit** `.env` file with credentials
3. **Rotate passwords** periodically
4. **Use environment variables** in production (Railway, Render, etc. inject them)

---

## Quick Reference

### Connection URL Formats

```bash
# Upstash (with TLS)
rediss://default:PASSWORD@REGION-xxxxx.upstash.io:6379

# Railway (without TLS)
redis://default:PASSWORD@containers-us-west-xxx.railway.app:6379

# Local development
redis://localhost:6379/0
```

### Test Commands

```bash
# Test with redis-cli (if installed)
redis-cli -u "rediss://default:PASSWORD@host:6379" PING

# Test with Python
python -c "import redis; r = redis.from_url('$REDIS_URL'); print(r.ping())"
```

---

## Next Steps

1. ✅ Set up Redis Cloud (Upstash or Railway)
2. ✅ Add REDIS_URL to `.env`
3. ✅ Run `test_redis_cloud.py` successfully
4. → Proceed to [02_CELERY_SETUP.md](02_CELERY_SETUP.md) to configure Celery
5. → Proceed to [05_MIGRATION_GUIDE.md](05_MIGRATION_GUIDE.md) to migrate code
