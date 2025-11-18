# Agensium Backend - Deployment & Production Guide

## Overview

This guide covers deploying Agensium Backend to production environments with focus on reliability, scalability, and monitoring.

---

## Local Development Setup

### Prerequisites

- Python 3.9+
- pip and virtualenv
- Git
- 2GB RAM minimum
- 1GB disk space minimum

### Installation

```bash
# Clone repository
git clone <repository-url>
cd Agensium-frontend-newbackend/backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo OPENAI_API_KEY=your_key_here > .env

# Run server
python main.py
```

Server runs on `http://localhost:8000`

API docs available at `http://localhost:8000/docs`

---

## Docker Deployment

### Building Docker Image

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["python", "main.py"]
```

### Building and Running

```bash
# Build image
docker build -t agensium-backend:1.0.0 .

# Run container
docker run -d \
  -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e WORKERS=4 \
  --name agensium-backend \
  agensium-backend:1.0.0

# View logs
docker logs -f agensium-backend

# Stop container
docker stop agensium-backend
```

### Docker Compose (Multi-Service)

Create `docker-compose.yml`:

```yaml
version: "3.8"

services:
  backend:
    build: .
    container_name: agensium-backend
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - WORKERS=4
      - LOG_LEVEL=INFO
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    networks:
      - agensium-network

  # Optional: Redis for caching
  redis:
    image: redis:7-alpine
    container_name: agensium-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - agensium-network
    restart: unless-stopped

volumes:
  redis-data:

networks:
  agensium-network:
    driver: bridge
```

Running:

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f backend

# Rebuild and start
docker-compose up -d --build
```

---

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.20+)
- kubectl configured
- Docker image pushed to registry

### Deployment YAML

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agensium-backend
  labels:
    app: agensium-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agensium-backend
  template:
    metadata:
      labels:
        app: agensium-backend
    spec:
      containers:
        - name: backend
          image: your-registry/agensium-backend:1.0.0
          imagePullPolicy: Always
          ports:
            - containerPort: 8000
          env:
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: agensium-secrets
                  key: openai-api-key
            - name: WORKERS
              value: "4"
            - name: LOG_LEVEL
              value: "INFO"
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 40
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 2
          volumeMounts:
            - name: uploads
              mountPath: /app/uploads
            - name: logs
              mountPath: /app/logs
      volumes:
        - name: uploads
          persistentVolumeClaim:
            claimName: agensium-uploads-pvc
        - name: logs
          persistentVolumeClaim:
            claimName: agensium-logs-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: agensium-backend-service
spec:
  selector:
    app: agensium-backend
  ports:
    - protocol: TCP
      port: 8000
      targetPort: 8000
  type: LoadBalancer

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agensium-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agensium-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### Deployment

```bash
# Create secrets
kubectl create secret generic agensium-secrets \
  --from-literal=openai-api-key=your_key

# Create PVCs for storage
kubectl apply -f k8s-pvc.yaml

# Deploy application
kubectl apply -f k8s-deployment.yaml

# Check status
kubectl get deployments
kubectl get pods
kubectl get svc

# View logs
kubectl logs -f deployment/agensium-backend

# Scale manually
kubectl scale deployment agensium-backend --replicas=5
```

---

## Cloud Platform Deployment

### AWS (EC2)

```bash
# SSH into EC2 instance
ssh -i key.pem ubuntu@ec2-instance-ip

# Install dependencies
sudo apt-get update
sudo apt-get install -y python3.9 python3-pip

# Clone and setup
git clone <repo-url>
cd Agensium-frontend-newbackend/backend
pip install -r requirements.txt

# Create systemd service
sudo tee /etc/systemd/system/agensium.service << EOF
[Unit]
Description=Agensium Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/Agensium-frontend-newbackend/backend
Environment="OPENAI_API_KEY=your_key"
ExecStart=/usr/bin/python3.9 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Start service
sudo systemctl enable agensium
sudo systemctl start agensium
sudo systemctl status agensium

# View logs
sudo journalctl -u agensium -f
```

### AWS (Elastic Beanstalk)

```bash
# Install EB CLI
pip install awsebcli

# Initialize
eb init -p python-3.9 agensium-backend

# Create environment
eb create agensium-prod --instance-type t3.medium

# Deploy
git add .
git commit -m "Deploy to EB"
eb deploy

# Monitor
eb status
eb logs
eb health
```

### Heroku

```bash
# Install Heroku CLI
# Download from heroku.com

# Login
heroku login

# Create app
heroku create agensium-backend

# Set environment variables
heroku config:set OPENAI_API_KEY=your_key

# Create Procfile
echo "web: python main.py" > Procfile
echo "release: pip install -r requirements.txt" >> Procfile

# Deploy
git push heroku main

# View logs
heroku logs -t

# Scale
heroku ps:scale web=2
```

### Google Cloud Run

```bash
# Authenticate
gcloud auth login

# Build and push to Container Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/agensium-backend

# Deploy to Cloud Run
gcloud run deploy agensium-backend \
  --image gcr.io/PROJECT_ID/agensium-backend \
  --platform managed \
  --region us-central1 \
  --memory 1Gi \
  --cpu 2 \
  --set-env-vars OPENAI_API_KEY=your_key \
  --allow-unauthenticated

# View logs
gcloud run services describe agensium-backend --platform managed
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=agensium-backend"
```

### Azure Container Instances

```bash
# Login to Azure
az login

# Create container registry
az acr create --resource-group myResourceGroup \
  --name agensiumregistry --sku Basic

# Build and push image
az acr build --registry agensiumregistry \
  --image agensium-backend:latest .

# Deploy container instance
az container create \
  --resource-group myResourceGroup \
  --name agensium-backend \
  --image agensiumregistry.azurecr.io/agensium-backend:latest \
  --cpu 2 --memory 1 \
  --ports 8000 \
  --environment-variables OPENAI_API_KEY=your_key
```

---

## Performance Optimization

### 1. Worker Configuration

Adjust in `main.py`:

```python
import uvicorn

# Calculate optimal workers
import multiprocessing
workers = max(1, multiprocessing.cpu_count() - 1)

uvicorn.run(
    "app:app",
    host="0.0.0.0",
    port=8000,
    workers=workers,  # Multiple worker processes
    loop="uvloop",    # Fast event loop
    log_level="info",
    access_log=True
)
```

**Guidelines**:

- **CPU-bound**: workers = CPU cores - 1
- **I/O-bound**: workers = (CPU cores × 2) + 1
- **Production**: Start with 4-8, monitor and adjust

### 2. Caching Strategy

```python
# With Redis
import redis
from functools import wraps
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_result(timeout=3600):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Check cache
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Execute function
            result = func(*args, **kwargs)

            # Cache result
            redis_client.setex(cache_key, timeout, json.dumps(result))

            return result
        return wrapper
    return decorator

# Usage
@cache_result(timeout=3600)
def analyze_file(filename):
    # Long-running analysis
    pass
```

### 3. Database Connection Pooling

```python
# Connection pool configuration
DB_POOL_SIZE = 20
DB_POOL_TIMEOUT = 30
DB_POOL_RECYCLE = 3600  # Recycle connections hourly

from sqlalchemy import create_engine

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=DB_POOL_SIZE,
    max_overflow=40,
    pool_timeout=DB_POOL_TIMEOUT,
    pool_recycle=DB_POOL_RECYCLE
)
```

### 4. Request/Response Optimization

```python
# Compress responses
from fastapi.middleware.gzip import GZIPMiddleware

app.add_middleware(GZIPMiddleware, minimum_size=1000)

# Request size limits
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB

# Streaming large responses
from fastapi.responses import StreamingResponse

@app.get("/download-report/{report_id}")
async def download_report(report_id: str):
    def stream_report():
        with open(f"reports/{report_id}.xlsx", "rb") as f:
            yield from f

    return StreamingResponse(
        stream_report(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
```

### 5. Async Operations

```python
# Use asyncio for I/O operations
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

@app.post("/analyze-async")
async def analyze_async(file: UploadFile):
    # Run sync code in executor
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        executor,
        perform_analysis,
        await file.read()
    )
    return result
```

---

## Monitoring & Logging

### 1. Application Metrics

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, start_http_server
import time

# Metrics
request_count = Counter(
    'agensium_requests_total',
    'Total requests',
    ['method', 'endpoint']
)

request_duration = Histogram(
    'agensium_request_duration_seconds',
    'Request duration',
    ['endpoint']
)

# Middleware to track metrics
@app.middleware("http")
async def track_metrics(request: Request, call_next):
    start = time.time()
    response = await call_next(request)

    request_count.labels(
        method=request.method,
        endpoint=request.url.path
    ).inc()

    request_duration.labels(
        endpoint=request.url.path
    ).observe(time.time() - start)

    return response

# Expose metrics endpoint
from prometheus_client import REGISTRY
@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain"
    )
```

### 2. Logging Configuration

```python
import logging
import logging.handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/agensium.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Rotate log files
file_handler = logging.handlers.RotatingFileHandler(
    'logs/agensium.log',
    maxBytes=10485760,  # 10MB
    backupCount=5
)
logger.addHandler(file_handler)

# Structured logging
import json

def log_event(event_type: str, **kwargs):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        **kwargs
    }
    logger.info(json.dumps(log_entry))

# Usage
log_event("analysis_started", file_size=1024, tool="clean-my-data")
log_event("analysis_completed", duration_ms=5000, status="success")
```

### 3. Monitoring Stack

Use Prometheus + Grafana:

```bash
# Docker Compose with monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

`docker-compose.monitoring.yml`:

```yaml
version: "3.8"

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  prometheus-data:
  grafana-data:
```

---

## Security

### 1. Environment Variables

```bash
# .env file (never commit to Git)
OPENAI_API_KEY=sk-...
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@host/db
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE=100MB
ALLOWED_ORIGINS=https://frontend.domain.com
```

### 2. HTTPS/SSL

```python
# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Run with HTTPS
uvicorn.run(
    "app:app",
    host="0.0.0.0",
    port=443,
    ssl_keyfile="key.pem",
    ssl_certfile="cert.pem"
)

# Or use reverse proxy (recommended)
# Nginx configuration for SSL termination
```

### 3. API Key Protection

```python
from fastapi.security import HTTPBearer, HTTPAuthCredential
from fastapi import Depends, HTTPException

security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthCredential = Depends(security)):
    if credentials.credentials != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return credentials.credentials

@app.post("/analyze")
async def analyze(file: UploadFile, api_key: str = Depends(verify_api_key)):
    # Protected endpoint
    pass
```

### 4. Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/analyze")
@limiter.limit("10/minute")
async def analyze(request: Request, file: UploadFile):
    # Rate limited to 10 requests per minute
    pass
```

### 5. CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://frontend.domain.com",
        "https://app.domain.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

## Backup & Recovery

### 1. Database Backups

```bash
# PostgreSQL backup
pg_dump -U user -d agensium_db > backup_$(date +%Y%m%d).sql

# Restore
psql -U user -d agensium_db < backup_20231215.sql

# Automated daily backups (cron)
# 0 2 * * * pg_dump -U user -d agensium_db | gzip > /backups/agensium_$(date +\%Y\%m\%d).sql.gz
```

### 2. File Backups

```bash
# Backup uploads and logs
tar -czf agensium_backup_$(date +%Y%m%d).tar.gz uploads/ logs/

# Sync to cloud storage
aws s3 sync ./backups s3://agensium-backups/
```

### 3. Disaster Recovery Plan

1. **Daily automated backups** to cloud storage
2. **Weekly restore tests** to verify backup integrity
3. **RTO target**: 4 hours (recovery time objective)
4. **RPO target**: 1 hour (recovery point objective)
5. **Failover procedure**: Switch DNS to standby instance

---

## Health Checks & Monitoring

### Health Endpoint

```python
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "dependencies": {
            "openai": check_openai_connection(),
            "database": check_database_connection(),
            "disk_space": check_disk_space()
        }
    }

def check_openai_connection():
    try:
        # Quick OpenAI API call
        openai.Completion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "ping"}]
        )
        return {"status": "healthy"}
    except:
        return {"status": "unhealthy"}
```

### Alerting

Configure alerts for:

- **High CPU/Memory**: > 80% for 5 minutes
- **High error rate**: > 5% of requests
- **Response time**: p99 > 10 seconds
- **Disk space**: < 10% remaining
- **API quota**: > 80% of OpenAI usage
- **Service unavailability**: > 1 minute downtime

---

## Scaling Strategies

### Horizontal Scaling

```yaml
# Kubernetes HPA for automatic scaling
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agensium-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agensium-backend
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "1000"
```

### Vertical Scaling

Increase resources per pod:

```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "1000m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
```

### Database Scaling

- **Read replicas** for scaling read operations
- **Connection pooling** to handle more connections
- **Partitioning** for large tables
- **Caching layer** (Redis) for frequently accessed data

---

## Troubleshooting

### High Memory Usage

```bash
# Check memory usage
docker stats agensium-backend

# Identify memory leaks
python -m memory_profiler main.py

# Solution: Implement object pooling, streaming for large responses
```

### Slow API Responses

```bash
# Profile execution time
python -m cProfile -s cumulative main.py

# Check database query performance
EXPLAIN ANALYZE SELECT * FROM analyses;

# Solutions: Add indexes, optimize queries, enable caching
```

### File Upload Failures

```
Issues: File size too large, timeout, memory exhausted

Solutions:
1. Stream file upload instead of loading into memory
2. Increase timeout limits
3. Chunk file processing (process 10,000 rows at a time)
4. Increase server memory/workers
```

### API Rate Limiting Issues

```
Solution: Implement queue system with background workers
```

---

## Rollback Procedures

### Docker

```bash
# Rollback to previous image version
docker run -d \
  -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  --name agensium-backend-old \
  agensium-backend:0.9.0

# Switch DNS to old instance
```

### Kubernetes

```bash
# View rollout history
kubectl rollout history deployment/agensium-backend

# Rollback to previous version
kubectl rollout undo deployment/agensium-backend

# Rollback to specific revision
kubectl rollout undo deployment/agensium-backend --to-revision=2
```

### Blue-Green Deployment

```yaml
# Blue (current) deployment running v1.0
# Green (new) deployment running v1.1
# Switch traffic from blue to green after validation
# Keep blue running for instant rollback
```

---

## Production Checklist

- [ ] SSL/HTTPS configured
- [ ] API keys and secrets in environment variables
- [ ] CORS properly configured
- [ ] Rate limiting enabled
- [ ] Monitoring and alerting set up
- [ ] Automated backups configured
- [ ] Log rotation configured
- [ ] Health checks working
- [ ] Error tracking configured (Sentry)
- [ ] Database connection pooling tuned
- [ ] Worker count optimized
- [ ] Load balancer configured
- [ ] CDN for static files (if applicable)
- [ ] DDoS protection enabled
- [ ] Security headers added
- [ ] API documentation up-to-date
- [ ] Incident response plan documented
- [ ] Disaster recovery plan tested
- [ ] Performance baselines established
- [ ] Cost monitoring enabled

---

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Documentation](https://docs.docker.com/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [AWS Best Practices](https://docs.aws.amazon.com/bestpractices/)
- [Google Cloud Documentation](https://cloud.google.com/docs)
- [Prometheus Monitoring](https://prometheus.io/)
- [Grafana Dashboards](https://grafana.com/)

---

## Support

For deployment issues:

1. Check [01_GETTING_STARTED.md](./01_GETTING_STARTED.md) for basic setup
2. Review [02_ARCHITECTURE.md](./02_ARCHITECTURE.md) for system understanding
3. Check server logs: `docker logs agensium-backend` or `journalctl -u agensium -f`
4. Verify environment variables are set correctly
5. Check API connectivity: `curl -X GET http://localhost:8000/health`
