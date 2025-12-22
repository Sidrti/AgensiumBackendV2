# V2.1 Architecture Plan - Backblaze B2 Integration

**Document Version:** 2.1  
**Created:** December 19, 2025  
**Updated:** December 19, 2025  
**Purpose:** Design document for migrating to Backblaze B2 storage with simplified task model

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Comparison](#architecture-comparison)
3. [New System Flow](#new-system-flow)
4. [Component Design](#component-design)
5. [Backblaze B2 Integration](#backblaze-b2-integration)
6. [API Design](#api-design)
7. [Migration Strategy](#migration-strategy)
8. [Future: Queue System](#future-queue-system)

---

## Overview

### Goals

1. **Decouple upload from processing** - Users don't wait for analysis
2. **Persistent storage** - Files AND parameters stored in Backblaze B2
3. **Task tracking** - Simplified lifecycle visibility
4. **Scalable downloads** - Presigned URLs, not base64 in response
5. **Foundation for queue system** - Easy migration to async processing

### Key Changes from V2

| Aspect             | V2                                | V2.1                                    |
| ------------------ | --------------------------------- | --------------------------------------- |
| Parameters Storage | Database JSON column              | Backblaze B2 (presigned URLs)           |
| Task Model         | Complex with many tracking fields | Simplified - removed redundant fields   |
| File Metadata      | Stored in database                | Derived from S3 structure (user/task)   |
| Results Storage    | Full results in database          | Only outputs in B2, no database storage |

### Key Changes from V1

| Aspect             | V1 (Current)               | V2.1 (New)                        |
| ------------------ | -------------------------- | --------------------------------- |
| File Upload        | Backend receives file      | Direct to B2 via presigned URL    |
| Parameters         | Form data or JSON in DB    | Uploaded to B2 with presigned URL |
| File Storage       | In-memory only             | Backblaze B2 (persistent)         |
| Processing Trigger | Upload triggers processing | Explicit API call after upload    |
| Status Tracking    | None                       | Full task lifecycle               |
| Results Storage    | In response only           | B2 storage                        |
| Downloads          | Base64 in JSON             | Presigned download URLs           |

---

## Architecture Comparison

### V1: Synchronous (Current)

```
┌──────────┐    ┌─────────────────────────────────────────────────────┐
│ Frontend │───►│ POST /analyze                                       │
└──────────┘    │ - Receive file (100MB)                              │
                │ - Read into memory                                   │
                │ - Execute agents (30-60 seconds)                     │
                │ - Generate reports                                   │
                │ - Return everything as JSON (150MB response!)        │
                └─────────────────────────────────────────────────────┘

Problem: User waits 60+ seconds, huge response, no persistence
```

### V2.1: Task-Based with B2 (Simplified)

```
┌──────────┐    ┌────────────────┐    ┌─────────────────┐
│ Frontend │───►│ POST /tasks    │───►│ Create Task     │
└──────────┘    │ (create task)  │    │ status=CREATED  │
     │          └────────────────┘    └─────────────────┘
     │                                        │
     ▼                                        ▼
┌──────────┐    ┌────────────────┐    ┌─────────────────┐
│ Frontend │───►│POST /tasks/:id │───►│ Generate URLs   │
│          │    │ /upload-urls   │    │ for files AND   │
└──────────┘    └────────────────┘    │ parameters.json │
     │                                 └─────────────────┘
     ▼                                        │
┌──────────┐    ┌────────────────┐    ┌─────────────────┐
│ Frontend │───►│ Backblaze B2   │───►│ Files + params  │
│          │    │ (presigned PUT)│    │ stored in S3    │
└──────────┘    └────────────────┘    └─────────────────┘
     │
     ▼
┌──────────┐    ┌────────────────┐    ┌─────────────────┐
│ Frontend │───►│POST /tasks/:id │───►│ Process task    │
│          │    │ /process       │    │ status=QUEUED   │
└──────────┘    └────────────────┘    │ →PROCESSING     │
     │                                │ →COMPLETED      │
     │                                └─────────────────┘
     ▼
┌──────────┐    ┌────────────────┐    ┌─────────────────┐
│ Frontend │───►│ GET /tasks/:id │───►│ Poll for status │
│          │    │                │    │ Get results     │
└──────────┘    └────────────────┘    └─────────────────┘
```

---

## New System Flow

### Phase 1: Task Creation

```
Frontend                          Backend                          Database
   │                                 │                                 │
   │ POST /tasks                     │                                 │
   │ {tool_id, agents}               │                                 │
   │ (NO parameters in request)      │                                 │
   │────────────────────────────────►│                                 │
   │                                 │ Create Task                     │
   │                                 │ task_id = UUID                  │
   │                                 │ status = CREATED                │
   │                                 │─────────────────────────────────►
   │                                 │                                 │
   │◄────────────────────────────────│                                 │
   │ {task_id, status: CREATED}      │                                 │
```

### Phase 2: Get Upload URLs (Files + Parameters)

```
Frontend                          Backend                          Backblaze B2
   │                                 │                                 │
   │ POST /tasks/:id/upload-urls     │                                 │
   │ {files: [primary, baseline],    │                                 │
   │  has_parameters: true}          │                                 │
   │────────────────────────────────►│                                 │
   │                                 │ Generate presigned URLs         │
   │                                 │ for files AND parameters.json   │
   │                                 │─────────────────────────────────►
   │                                 │◄────────────────────────────────│
   │                                 │ {presigned_urls}                │
   │                                 │                                 │
   │◄────────────────────────────────│                                 │
   │ {uploads: {                     │                                 │
   │    primary: {url, key},         │                                 │
   │    baseline: {url, key},        │                                 │
   │    parameters: {url, key}       │                                 │
   │  }}                             │                                 │
```

### Phase 3: Direct Upload (Files + Parameters)

```
Frontend                                                         Backblaze B2
   │                                                                   │
   │ PUT presigned_url (primary)                                       │
   │ Content-Type: text/csv                                            │
   │ Body: <file bytes>                                                │
   │──────────────────────────────────────────────────────────────────►│
   │                                                                   │
   │ PUT presigned_url (parameters)                                    │
   │ Content-Type: application/json                                    │
   │ Body: {"agent-1": {...}, "agent-2": {...}}                        │
   │──────────────────────────────────────────────────────────────────►│
   │                                                                   │
   │◄──────────────────────────────────────────────────────────────────│
   │ HTTP 200 OK                                                       │
```

### Phase 4: Trigger Processing

```
Frontend                          Backend                          Database
   │                                 │                                 │
   │ POST /tasks/:id/process         │                                 │
   │────────────────────────────────►│                                 │
   │                                 │ Verify files in B2              │
   │                                 │ Update status = QUEUED          │
   │                                 │─────────────────────────────────►
   │                                 │                                 │
   │                                 │ Execute analysis (sync for now) │
   │                                 │ - Read files from B2            │
   │                                 │ - Read parameters from B2       │
   │                                 │ - Process agents                │
   │                                 │ - Upload outputs to B2          │
   │                                 │                                 │
   │◄────────────────────────────────│                                 │
   │ {task_id, status: PROCESSING}   │                                 │
```

### Phase 5: Poll for Status

```
Frontend                          Backend                          Database
   │                                 │                                 │
   │ GET /tasks/:id                  │                                 │
   │────────────────────────────────►│                                 │
   │                                 │ Fetch task                      │
   │                                 │◄─────────────────────────────────
   │                                 │                                 │
   │◄────────────────────────────────│                                 │
   │ {task_id, status, progress,     │                                 │
   │  download_urls?}                │                                 │
```

---

## Component Design

### New Files Structure

```
backend/
├── services/
│   ├── __init__.py
│   └── s3_service.py           # Backblaze B2 client
├── api/
│   ├── routes.py               # Modified
│   └── task_routes.py          # NEW: Task endpoints
├── db/
│   └── models.py               # Add simplified Task model
├── transformers/
│   └── *.py                    # Modified: Read from S3
└── downloads/
    └── *.py                    # Modified: Write to S3
```

### S3 Service Design

```python
# services/s3_service.py

import boto3
import os
from typing import Optional, List, Dict, Any

class S3Service:
    """Backblaze B2 S3-compatible storage service."""

    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION"),
        )
        self.bucket = os.getenv("S3_BUCKET")

    def generate_upload_url(
        self,
        user_id: int,
        task_id: str,
        filename: str,
        content_type: str = "text/csv",
        expires_in: int = 900  # 15 minutes
    ) -> Dict[str, str]:
        """Generate presigned URL for file upload."""
        key = f"users/{user_id}/tasks/{task_id}/inputs/{filename}"
        url = self.client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": content_type
            },
            ExpiresIn=expires_in
        )
        return {"url": url, "key": key}

    def generate_parameter_upload_url(
        self,
        user_id: int,
        task_id: str,
        expires_in: int = 900
    ) -> Dict[str, str]:
        """Generate presigned URL for parameters.json upload."""
        key = f"users/{user_id}/tasks/{task_id}/inputs/parameters.json"
        url = self.client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": "application/json"
            },
            ExpiresIn=expires_in
        )
        return {"url": url, "key": key}

    def generate_download_url(
        self,
        key: str,
        expires_in: int = 3600  # 1 hour
    ) -> str:
        """Generate presigned URL for file download."""
        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in
        )

    def file_exists(self, key: str) -> bool:
        """Check if file exists in bucket."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except:
            return False

    def get_file_stream(self, key: str):
        """Get streaming body for file (for agent processing)."""
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response['Body']

    def get_file_bytes(self, key: str) -> bytes:
        """Get file content as bytes."""
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response['Body'].read()

    def get_parameters(self, user_id: int, task_id: str) -> Optional[Dict]:
        """Get parameters.json for a task."""
        key = f"users/{user_id}/tasks/{task_id}/inputs/parameters.json"
        if not self.file_exists(key):
            return None

        import json
        content = self.get_file_bytes(key)
        return json.loads(content.decode('utf-8'))

    def upload_file(
        self,
        key: str,
        content: bytes,
        content_type: str = "text/csv"
    ) -> None:
        """Upload file content to S3."""
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type
        )

    def list_output_files(
        self,
        user_id: int,
        task_id: str
    ) -> List[Dict[str, Any]]:
        """List all files in task outputs folder."""
        prefix = f"users/{user_id}/tasks/{task_id}/outputs/"
        response = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=prefix
        )

        files = []
        for obj in response.get('Contents', []):
            filename = obj['Key'].replace(prefix, '')
            if filename:
                files.append({
                    'key': obj['Key'],
                    'filename': filename,
                    'size': obj['Size'],
                    'last_modified': obj['LastModified']
                })
        return files
```

### B2 File Structure

```
s3://agensium-files/
└── users/
    └── {user_id}/
        └── tasks/
            └── {task_id}/
                ├── inputs/
                │   ├── primary.csv
                │   ├── baseline.csv        (optional)
                │   └── parameters.json     (NEW: parameters stored here)
                └── outputs/
                    ├── data_profile_report.xlsx
                    ├── data_profile_report.json
                    └── cleaned_data.csv    (for clean-my-data)
```

**Key Insight:** Since we follow structure `users/{user_id}/tasks/{task_id}`, we can derive:

- Who owns the task (user_id)
- Which task it is (task_id)
- No need to store this metadata in database!

---

## Backblaze B2 Integration

### Configuration (Already Set Up)

```env
# .env (already configured)
AWS_ACCESS_KEY_ID=005fb2e3bbdac0d0000000002
AWS_SECRET_ACCESS_KEY=K005zAnnw2vCoHK0jhT++tLScYAxjRE
AWS_ENDPOINT_URL=https://s3.us-east-005.backblazeb2.com
AWS_REGION=us-east-005
S3_BUCKET=agensium-files
```

### Verified Working (from test_b2_complete.py)

✅ Connection to B2  
✅ Presigned URL generation  
✅ File upload via presigned URL  
✅ File verification  
✅ Download URL generation  
✅ Bucket listing

---

## API Design

### New Task Endpoints

| Endpoint                       | Method | Purpose                             |
| ------------------------------ | ------ | ----------------------------------- |
| `/tasks`                       | POST   | Create new task                     |
| `/tasks/{task_id}`             | GET    | Get task status and results         |
| `/tasks/{task_id}/upload-urls` | POST   | Get presigned URLs (files + params) |
| `/tasks/{task_id}/process`     | POST   | Trigger processing                  |
| `/tasks/{task_id}/downloads`   | GET    | Get download URLs                   |
| `/tasks`                       | GET    | List user's tasks                   |

### Detailed Endpoint Specs

See [04_V2_API_SPECIFICATION.md](04_V2_API_SPECIFICATION.md)

---

## Migration Strategy

### Phase 1: Add Task Infrastructure (Week 1)

1. ✅ Create simplified Task model in `db/models.py`
2. ✅ Create S3 service in `services/s3_service.py`
3. ✅ Create task routes in `api/task_routes.py`
4. ✅ Run database migration

### Phase 2: Implement Upload Flow (Week 1-2)

1. ✅ `POST /tasks` - Create task
2. ✅ `POST /tasks/{id}/upload-urls` - Get presigned URLs (including parameters)
3. ✅ Frontend uploads files + parameters.json to B2
4. ✅ `POST /tasks/{id}/process` - Trigger processing

### Phase 3: Modify Transformers (Week 2)

1. ✅ Read files from S3 instead of UploadFile
2. ✅ Read parameters from S3 (parameters.json)
3. ✅ Write outputs to S3 instead of base64
4. ✅ Update downloads to return URLs

### Phase 4: Status & Results (Week 2-3)

1. ✅ `GET /tasks/{id}` - Status polling
2. ✅ `GET /tasks/{id}/downloads` - Download URLs
3. ✅ Minimal task tracking in database

### Phase 5: Deprecate Old Endpoint (Week 3+)

1. ⬜ Mark `POST /analyze` as deprecated
2. ⬜ Monitor usage
3. ⬜ Remove after transition period

---

## Future: Queue System

### Why Not Now?

The current synchronous implementation is **acceptable for MVP**:

- Processing time: 10-60 seconds per file
- Concurrent users: ~10-20 manageable
- Complexity: Queue adds significant infrastructure

### Future Queue Architecture

```
┌──────────┐    ┌────────────┐    ┌─────────┐    ┌─────────────┐
│ Frontend │───►│  API       │───►│  Redis  │───►│   Celery    │
│          │    │  (FastAPI) │    │  Queue  │    │   Workers   │
└──────────┘    └────────────┘    └─────────┘    └──────┬──────┘
                                                        │
                                                        ▼
                                                 ┌─────────────┐
                                                 │ Backblaze   │
                                                 │ B2 Storage  │
                                                 └─────────────┘
```

### Migration Path

The V2.1 design with simplified tasks makes queue migration **trivial**:

```python
# Current (V2.1 sync)
def process_task(task_id):
    task = get_task(task_id)
    result = run_analysis(task)  # Blocking
    save_result(task_id, result)

# Future (queue)
@celery.task
def process_task(task_id):
    task = get_task(task_id)
    result = run_analysis(task)  # Same logic!
    save_result(task_id, result)
```

The task abstraction makes the processing **location-agnostic**.

---

## Benefits of V2.1 Architecture

### For Users

- ✅ Immediate response (3 seconds vs 60 seconds)
- ✅ Progress visibility
- ✅ Resume interrupted uploads
- ✅ Access historical analyses
- ✅ Faster downloads (direct from B2)

### For System

- ✅ Lower memory usage (stream from S3)
- ✅ Better scalability (B2 handles storage)
- ✅ Simpler database schema
- ✅ No redundant metadata storage
- ✅ Retry capability (task-based)
- ✅ Future-proof for queue system

### For Development

- ✅ Cleaner separation of concerns
- ✅ Easier testing (mock S3)
- ✅ Better debugging (task status history)
- ✅ Incremental migration possible
- ✅ Simplified data model

---

## Next Steps

1. **Review** [03_TASK_LIFECYCLE.md](03_TASK_LIFECYCLE.md) - Task status design
2. **Review** [04_V2_API_SPECIFICATION.md](04_V2_API_SPECIFICATION.md) - API details
3. **Review** [05_DATABASE_SCHEMA_V2.md](05_DATABASE_SCHEMA_V2.md) - Simplified schema
4. **Start implementation** - Phase 1: Task infrastructure

---

**Document Status:** Complete  
**Last Updated:** December 19, 2025  
**Version:** 2.1
