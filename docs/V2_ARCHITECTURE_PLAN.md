# V2 Architecture Plan: Asynchronous Processing

This document describes the plan to transition the Agensium backend from synchronous blocking processing to an asynchronous architecture using background workers, a fast message broker, and shared object storage. It focuses on the components, rationale, and implementation steps for non-blocking processing using Celery + Redis, shared file storage, task wrappers around existing agent logic, async API routes, and deployment options.

## Phase 1: Asynchronous Infrastructure (Celery + Redis)

**Goal:** Offload long-running data processing tasks to background workers to keep the API responsive.

### 1.1. Concepts & Definitions

- **Celery:**
  - _What is it?_ A distributed task queue.
  - _Why use it?_ It allows you to define Python functions as "tasks" that run in the background. This prevents your website from freezing while it processes a large file.
- **Redis:**
  - _What is it?_ An incredibly fast in-memory data store.
  - _Usage:_ In this architecture, it plays two roles:
    1.  **Message Broker:** The "mailbox" where the API puts tasks. The Workers check this mailbox to find work.
    2.  **Result Backend:** A place to store the final answer (e.g., the profile report) so the API can retrieve it later.

### 1.2. Implementation Steps

1.  **Infrastructure Setup:**

    - Provision a Redis instance (AWS ElastiCache or a local Docker container).

2.  **Dependency Updates:**

    - Add `celery` and `redis` to `requirements.txt`.

3.  **Celery Configuration (`backend/worker.py`):**

    - Create a central configuration file for the worker application.

    ```python
    from celery import Celery
    import os

    # Define the Celery application
    celery_app = Celery(
        "agensium_worker",
        # Broker: Where tasks are sent
        broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        # Backend: Where results are stored
        backend=os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )

    # Optimize configuration for JSON data
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        task_track_started=True,
    )
    ```

---

## Phase 2: Shared File Storage (S3 / Blob Storage)

**Goal:** Enable workers to access files uploaded via the API.

### 2.1. Concepts & Definitions

- **Object Storage (S3/Blob):**
  - _What is it?_ A service for storing large amounts of unstructured data (files), accessible via HTTP.
  - _Why use it?_ Passing a 500MB file through Redis (the message broker) will crash it. Instead, we save the file to S3, and just pass the _file path_ (a string) to the worker. The worker then downloads the file itself.
- **boto3:**
  - _What is it?_ The AWS SDK for Python.
  - _Usage:_ It provides easy Python functions to upload, download, and manage files on AWS S3.

### 2.2. Implementation Steps

1.  **Infrastructure Setup:**

    - Create an S3 Bucket (e.g., `agensium-user-uploads`).
    - Create an IAM User with read/write permissions to this bucket.

2.  **Storage Service (`backend/services/storage.py`):**

    - Create a helper class to handle uploads/downloads.

    ```python
    import boto3
    import os

    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    def upload_file(file_obj, object_name):
        """Uploads a file-like object to S3"""
        s3_client.upload_fileobj(file_obj, os.getenv("S3_BUCKET_NAME"), object_name)
        return object_name

    def download_file_as_bytes(object_name):
        """Downloads a file from S3 into memory"""
        response = s3_client.get_object(Bucket=os.getenv("S3_BUCKET_NAME"), Key=object_name)
        return response['Body'].read()
    ```

---

## Phase 3: Refactoring Agents to Tasks

**Goal:** Wrap existing synchronous agent logic into Celery tasks.

### 3.1. Concepts & Definitions

- **Task Wrapper:**
  - _What is it?_ A small function decorated with `@celery_app.task`.
  - _Usage:_ It handles the "plumbing" (downloading file, parsing params), calls your existing complex logic (the Agent), and returns the result. It keeps your core Agent logic pure and testable.

### 3.2. Implementation Steps

1.  **Create Task File (`backend/tasks/profiling_tasks.py`):**

    ```python
    from worker import celery_app
    from agents.unified_profiler import profile_data
    from services.storage import download_file_as_bytes

    @celery_app.task(bind=True)
    def run_profiling_task(self, file_storage_path, filename, params):
        # 1. Download file from S3 (Worker does this, not API)
        file_content = download_file_as_bytes(file_storage_path)

        # 2. Run existing agent logic (No changes needed to agent code)
        result = profile_data(file_content, filename, params)

        # 3. Return result (Celery automatically serializes this to JSON and saves to Redis)
        return result
    ```

---

## Phase 4: API Updates

**Goal:** Change API endpoints to be non-blocking ("Fire and Forget").

### 4.1. Concepts & Definitions

- **Asynchronous Request-Response Pattern:**
  - _What is it?_ Instead of the user waiting 30 seconds for a response, the server says "I accepted your request, here is a tracking ID." The user then asks "Is it done yet?" every few seconds until it is.
  - _Why use it?_ It prevents connection timeouts and allows the user to do other things while waiting.

### 4.2. Implementation Steps

1.  **Update Routes (`backend/api/routes.py`):**

    ```python
    from tasks.profiling_tasks import run_profiling_task
    from services.storage import upload_file

    @router.post("/profile/async")
    async def profile_data_async(file: UploadFile, background_tasks: BackgroundTasks):
        # 1. Upload file to S3 immediately
        s3_path = f"uploads/{uuid.uuid4()}/{file.filename}"
        upload_file(file.file, s3_path)

        # 2. Trigger the background task
        # .delay() is the magic method that sends the task to Redis
        task = run_profiling_task.delay(s3_path, file.filename, {})

        # 3. Return the Task ID immediately
        return {"task_id": task.id, "status": "processing"}
    ```

2.  **Add Status Endpoint:**

    ```python
    from celery.result import AsyncResult

    @router.get("/tasks/{task_id}")
    def get_task_status(task_id: str):
        # Check Redis for the status of this specific task ID
        task_result = AsyncResult(task_id)

        response = {
            "task_id": task_id,
            "status": task_result.status, # PENDING, STARTED, SUCCESS, FAILURE
        }

        if task_result.ready():
            response["result"] = task_result.result

        return response
    ```

---

## Phase 5: Deployment Configuration

**Goal:** Orchestrate all these moving parts.

### 5.1. Concepts & Definitions

- **Docker:**
  - _What is it?_ A platform that packages your application and all its dependencies (Python, libraries, OS settings) into a "container."
  - _Why use it?_ It ensures the app runs exactly the same on your laptop as it does on the production server.
- **Docker Compose:**
  - _What is it?_ A tool for defining and running multi-container Docker applications.
  - _Usage:_ It lets you start the API, the Worker, and Redis all with one command: `docker-compose up`.

### 5.2. Implementation Steps

1.  **Create `docker-compose.yml`:**

    ```yaml
    version: "3.8"
    services:
      # The Message Broker Service
      redis:
        image: redis:7
        ports:
          - "6379:6379"

      # The API Service (The Cashier)
      api:
        build: .
        command: uvicorn main:app --host 0.0.0.0 --port 8000
        environment:
          # DATABASE is managed separately; this doc focuses on async infra
          - REDIS_URL=redis://redis:6379/0
          - AWS_ACCESS_KEY_ID=...
        ports:
          - "8000:8000"
        depends_on:
          - redis

      # The Worker Service (The Chef)
      worker:
        build: .
        # Runs the Celery process instead of the Web Server
        command: celery -A worker.celery_app worker --loglevel=info
        environment:
          # DATABASE is managed separately; this doc focuses on async infra
          - REDIS_URL=redis://redis:6379/0
          - AWS_ACCESS_KEY_ID=...
        depends_on:
          - redis
    ```
