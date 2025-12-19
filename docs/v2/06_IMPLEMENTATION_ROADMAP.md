# V2 Implementation Roadmap

**Document Version:** 1.0  
**Created:** December 19, 2025  
**Purpose:** Step-by-step implementation guide for V2 migration

---

## Table of Contents

1. [Overview](#overview)
2. [Phase 1: Infrastructure](#phase-1-infrastructure)
3. [Phase 2: Task API](#phase-2-task-api)
4. [Phase 3: Transformer Updates](#phase-3-transformer-updates)
5. [Phase 4: Downloads & Results](#phase-4-downloads--results)
6. [Phase 5: Testing & Migration](#phase-5-testing--migration)
7. [File Changes Summary](#file-changes-summary)

---

## Overview

### Timeline Estimate

| Phase                        | Duration       | Dependencies |
| ---------------------------- | -------------- | ------------ |
| Phase 1: Infrastructure      | 2-3 days       | None         |
| Phase 2: Task API            | 3-4 days       | Phase 1      |
| Phase 3: Transformer Updates | 3-4 days       | Phase 2      |
| Phase 4: Downloads & Results | 2-3 days       | Phase 3      |
| Phase 5: Testing & Migration | 2-3 days       | Phase 4      |
| **Total**                    | **~2-3 weeks** |              |

### Prerequisites

- [x] Backblaze B2 account configured
- [x] B2 credentials in `.env`
- [x] B2 connection tested (`test_b2_complete.py` passing)
- [ ] Alembic configured for migrations (optional)

---

## Phase 1: Infrastructure

### 1.1 Create S3 Service

**File:** `services/s3_service.py`

```python
"""
Backblaze B2 S3-compatible storage service.
"""
import boto3
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta


class S3Service:
    """Backblaze B2 S3-compatible storage service."""

    _instance = None

    def __new__(cls):
        """Singleton pattern for connection reuse."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize S3 client."""
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
        expires_in: int = 900
    ) -> Dict[str, Any]:
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
        return {
            "url": url,
            "key": key,
            "method": "PUT",
            "headers": {"Content-Type": content_type},
            "expires_at": datetime.utcnow() + timedelta(seconds=expires_in)
        }

    def generate_download_url(
        self,
        key: str,
        expires_in: int = 3600
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

    def get_file_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get file metadata."""
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)
            return {
                "size_bytes": response['ContentLength'],
                "content_type": response.get('ContentType'),
                "last_modified": response['LastModified']
            }
        except:
            return None

    def get_file_bytes(self, key: str) -> bytes:
        """Download file content as bytes."""
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response['Body'].read()

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

    def list_files(self, prefix: str) -> List[Dict[str, Any]]:
        """List files with given prefix."""
        response = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=prefix
        )

        files = []
        for obj in response.get('Contents', []):
            filename = obj['Key'].replace(prefix, '').lstrip('/')
            if filename:
                files.append({
                    'key': obj['Key'],
                    'filename': filename,
                    'size_bytes': obj['Size'],
                    'last_modified': obj['LastModified']
                })
        return files

    def delete_file(self, key: str) -> None:
        """Delete a file from S3."""
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def delete_folder(self, prefix: str) -> int:
        """Delete all files with given prefix. Returns count deleted."""
        files = self.list_files(prefix)
        for file in files:
            self.delete_file(file['key'])
        return len(files)


# Singleton instance
s3_service = S3Service()
```

**Create:** `services/__init__.py`

```python
from .s3_service import S3Service, s3_service

__all__ = ['S3Service', 's3_service']
```

### 1.2 Add Task Model

**Update:** `db/models.py`

Add the Task model and TaskStatus enum as defined in [05_DATABASE_SCHEMA_V2.md](05_DATABASE_SCHEMA_V2.md).

### 1.3 Run Database Migration

**Option A: Alembic (Recommended)**

```bash
alembic revision --autogenerate -m "Add tasks table"
alembic upgrade head
```

**Option B: Manual SQL**

```bash
mysql -u user -p database < docs/v2/migrations/001_create_tasks.sql
```

### 1.4 Add Task Schemas

**Update:** `db/schemas.py`

Add the Pydantic schemas as defined in [05_DATABASE_SCHEMA_V2.md](05_DATABASE_SCHEMA_V2.md#pydantic-schemas).

---

## Phase 2: Task API

### 2.1 Create Task Routes

**Create:** `api/task_routes.py`

```python
"""
Task API Routes for V2 Architecture
"""
import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from db.database import get_db
from db import models, schemas
from db.models import TaskStatus
from auth.dependencies import get_current_active_verified_user
from services.s3_service import s3_service


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=schemas.TaskResponse, status_code=201)
async def create_task(
    request: schemas.TaskCreateRequest,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """Create a new analysis task."""
    # Import tool definitions
    from main import TOOL_DEFINITIONS

    # Validate tool
    if request.tool_id not in TOOL_DEFINITIONS:
        raise HTTPException(status_code=400, detail=f"Invalid tool_id: {request.tool_id}")

    tool_def = TOOL_DEFINITIONS[request.tool_id]

    # Determine agents
    agents = request.agents or tool_def["tool"]["available_agents"]

    # Validate files
    tool_files = tool_def["tool"].get("files", {})
    for file_key in request.files.keys():
        if file_key not in tool_files:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown file key: {file_key}. Valid keys: {list(tool_files.keys())}"
            )

    # Check required files
    for file_key, file_def in tool_files.items():
        if file_def.get("required", False) and file_key not in request.files:
            raise HTTPException(
                status_code=400,
                detail=f"Required file missing: {file_key}"
            )

    # Create task
    task_id = str(uuid.uuid4())
    task = models.Task(
        task_id=task_id,
        user_id=current_user.id,
        tool_id=request.tool_id,
        agents=agents,
        parameters=request.parameters,
        files_metadata={k: v.dict() for k, v in request.files.items()},
        status=TaskStatus.CREATED.value,
        progress=0
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return schemas.TaskResponse(
        task_id=task.task_id,
        status=TaskStatus(task.status),
        tool_id=task.tool_id,
        agents=task.agents,
        progress=task.progress,
        created_at=task.created_at
    )


@router.post("/{task_id}/upload-urls", response_model=schemas.UploadUrlsResponse)
async def get_upload_urls(
    task_id: str,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """Generate presigned URLs for file upload."""
    # Get task
    task = db.query(models.Task).filter(
        models.Task.task_id == task_id,
        models.Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in [TaskStatus.CREATED.value, TaskStatus.UPLOAD_FAILED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot generate upload URLs for task in status: {task.status}"
        )

    # Generate URLs for each file
    uploads = {}
    s3_input_keys = []

    for file_key, file_meta in task.files_metadata.items():
        upload_info = s3_service.generate_upload_url(
            user_id=current_user.id,
            task_id=task_id,
            filename=file_meta['filename'],
            content_type=file_meta.get('content_type', 'text/csv')
        )
        uploads[file_key] = schemas.UploadUrlInfo(**upload_info)
        s3_input_keys.append(upload_info['key'])

    # Update task
    task.status = TaskStatus.UPLOADING.value
    task.upload_started_at = datetime.utcnow()
    task.s3_input_keys = s3_input_keys
    db.commit()

    return schemas.UploadUrlsResponse(
        task_id=task_id,
        status=TaskStatus.UPLOADING.value,
        uploads=uploads,
        expires_in_seconds=900,
        message="Upload files directly to the provided URLs using PUT method."
    )


@router.post("/{task_id}/process", response_model=schemas.TaskResponse)
async def trigger_processing(
    task_id: str,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """Verify uploads and trigger processing."""
    # Get task
    task = db.query(models.Task).filter(
        models.Task.task_id == task_id,
        models.Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in [TaskStatus.UPLOADING.value, TaskStatus.UPLOAD_FAILED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot process task in status: {task.status}"
        )

    # Verify all files exist in S3
    missing_files = []
    for key in task.s3_input_keys or []:
        if not s3_service.file_exists(key):
            # Extract file key name
            filename = key.split('/')[-1]
            missing_files.append(filename)

    if missing_files:
        task.status = TaskStatus.UPLOAD_FAILED.value
        task.error_message = f"Files not found: {', '.join(missing_files)}"
        db.commit()
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "FILES_NOT_FOUND",
                "message": "Required files not found in storage",
                "missing_files": missing_files
            }
        )

    # Update status
    task.status = TaskStatus.QUEUED.value
    task.files_verified_at = datetime.utcnow()
    db.commit()

    # For V2 synchronous: Execute immediately
    # TODO: In future, push to queue instead
    try:
        result = await _execute_task(task, current_user, db)
        return result
    except Exception as e:
        task.status = TaskStatus.FAILED.value
        task.error_code = "INTERNAL_ERROR"
        task.error_message = str(e)
        task.failed_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


async def _execute_task(
    task: models.Task,
    current_user: models.User,
    db: Session
) -> schemas.TaskResponse:
    """Execute task processing (synchronous for now)."""
    from transformers import (
        profile_my_data_transformer,
        clean_my_data_transformer,
        master_my_data_transformer
    )

    # Update status
    task.status = TaskStatus.PROCESSING.value
    task.processing_started_at = datetime.utcnow()
    db.commit()

    # Execute based on tool
    if task.tool_id == "profile-my-data":
        result = await profile_my_data_transformer.run_profile_my_data_analysis_v2(
            task=task,
            current_user=current_user,
            db=db
        )
    elif task.tool_id == "clean-my-data":
        result = await clean_my_data_transformer.run_clean_my_data_analysis_v2(
            task=task,
            current_user=current_user,
            db=db
        )
    elif task.tool_id == "master-my-data":
        result = await master_my_data_transformer.run_master_my_data_analysis_v2(
            task=task,
            current_user=current_user,
            db=db
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {task.tool_id}")

    # Update task with results
    if result.get("status") == "success":
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = datetime.utcnow()
        task.progress = 100
        task.result_summary = result.get("result_summary")
        task.s3_output_keys = result.get("s3_output_keys", [])
    else:
        task.status = TaskStatus.FAILED.value
        task.failed_at = datetime.utcnow()
        task.error_code = result.get("error_code", "PROCESSING_ERROR")
        task.error_message = result.get("error")

    db.commit()
    db.refresh(task)

    return schemas.TaskResponse(
        task_id=task.task_id,
        status=TaskStatus(task.status),
        tool_id=task.tool_id,
        agents=task.agents,
        progress=task.progress,
        created_at=task.created_at,
        completed_at=task.completed_at,
        result_summary=task.result_summary,
        report=result.get("report") if task.status == TaskStatus.COMPLETED.value else None,
        downloads_available=bool(task.s3_output_keys),
        error_code=task.error_code,
        error_message=task.error_message
    )


@router.get("/{task_id}", response_model=schemas.TaskResponse)
async def get_task(
    task_id: str,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """Get task status and results."""
    task = db.query(models.Task).filter(
        models.Task.task_id == task_id,
        models.Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return schemas.TaskResponse(
        task_id=task.task_id,
        status=TaskStatus(task.status),
        tool_id=task.tool_id,
        agents=task.agents,
        progress=task.progress,
        created_at=task.created_at,
        upload_started_at=task.upload_started_at,
        processing_started_at=task.processing_started_at,
        completed_at=task.completed_at,
        failed_at=task.failed_at,
        result_summary=task.result_summary,
        downloads_available=bool(task.s3_output_keys),
        error_code=task.error_code,
        error_message=task.error_message,
        failed_agent=task.failed_agent,
        partial_results=task.partial_results
    )


@router.get("/{task_id}/downloads", response_model=schemas.DownloadsResponse)
async def get_downloads(
    task_id: str,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """Get presigned download URLs for task outputs."""
    task = db.query(models.Task).filter(
        models.Task.task_id == task_id,
        models.Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Downloads not available for task in status: {task.status}"
        )

    downloads = []
    for key in task.s3_output_keys or []:
        file_info = s3_service.get_file_info(key)
        if file_info:
            filename = key.split('/')[-1]
            url = s3_service.generate_download_url(key)

            # Determine mime type
            if filename.endswith('.xlsx'):
                mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif filename.endswith('.json'):
                mime_type = "application/json"
            else:
                mime_type = "text/csv"

            downloads.append(schemas.DownloadInfo(
                download_id=filename.replace('.', '_'),
                filename=filename,
                type="report" if filename.endswith(('.xlsx', '.json')) else "data",
                mime_type=mime_type,
                size_bytes=file_info['size_bytes'],
                url=url,
                expires_at=datetime.utcnow() + timedelta(hours=1)
            ))

    return schemas.DownloadsResponse(
        task_id=task_id,
        downloads=downloads,
        expires_in_seconds=3600
    )


@router.get("", response_model=schemas.TaskListResponse)
async def list_tasks(
    status: Optional[str] = Query(None),
    tool_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """List user's tasks with pagination."""
    query = db.query(models.Task).filter(
        models.Task.user_id == current_user.id
    )

    if status:
        query = query.filter(models.Task.status == status)
    if tool_id:
        query = query.filter(models.Task.tool_id == tool_id)

    total = query.count()
    tasks = query.order_by(models.Task.created_at.desc()).offset(offset).limit(limit).all()

    return schemas.TaskListResponse(
        tasks=[
            schemas.TaskResponse(
                task_id=t.task_id,
                status=TaskStatus(t.status),
                tool_id=t.tool_id,
                agents=t.agents,
                progress=t.progress,
                created_at=t.created_at,
                completed_at=t.completed_at,
                result_summary=t.result_summary,
                downloads_available=bool(t.s3_output_keys)
            ) for t in tasks
        ],
        pagination={
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total
        }
    )
```

### 2.2 Register Routes

**Update:** `main.py`

```python
# Add import
from api.task_routes import router as task_router

# Add router
app.include_router(task_router)
```

---

## Phase 3: Transformer Updates

### 3.1 Create V2 Transformer Functions

Add new functions to each transformer that read from S3 instead of UploadFile.

**Update:** `transformers/profile_my_data_transformer.py`

```python
async def run_profile_my_data_analysis_v2(
    task: "models.Task",
    current_user: Any,
    db: Session
) -> Dict[str, Any]:
    """
    Execute profile-my-data analysis using S3 files.

    V2 version that reads from Backblaze B2 instead of UploadFile.
    """
    from services.s3_service import s3_service

    start_time = time.time()

    try:
        from main import TOOL_DEFINITIONS

        tool_def = TOOL_DEFINITIONS[task.tool_id]

        # Read files from S3
        files_map = {}
        for key in task.s3_input_keys:
            file_key = _extract_file_key(key)  # e.g., "primary" from path
            filename = key.split('/')[-1]
            content = s3_service.get_file_bytes(key)
            files_map[file_key] = (content, filename)

        # Convert to CSV if needed
        files_map = convert_files_to_csv(files_map)

        # Parse parameters
        parameters = task.parameters or {}

        agent_results = {}
        agents_completed = []

        # Initialize billing context
        with BillingContext(current_user) as billing:
            for agent_id in task.agents:
                try:
                    # Update task progress
                    task.current_agent = agent_id
                    task.progress = int((len(agents_completed) / len(task.agents)) * 80) + 15
                    db.commit()

                    # Billing
                    billing_error = billing.consume_credits_for_agent(
                        agent_id=agent_id,
                        tool_id=task.tool_id,
                        analysis_id=task.task_id,
                        start_time=start_time
                    )
                    if billing_error:
                        task.partial_results = agent_results
                        task.agents_completed = agents_completed
                        return billing_error

                    # Build agent input
                    agent_input = _build_agent_input(agent_id, files_map, parameters, tool_def)

                    # Execute agent
                    result = _execute_agent(agent_id, agent_input)

                    agent_results[agent_id] = result
                    agents_completed.append(agent_id)

                except Exception as e:
                    agent_results[agent_id] = {
                        "status": "error",
                        "error": str(e),
                        "execution_time_ms": 0
                    }

        # Transform results (same as before)
        final_result = transform_profile_my_data_response(
            agent_results,
            int((time.time() - start_time) * 1000),
            task.task_id,
            current_user
        )

        # Upload outputs to S3
        s3_output_keys = await _upload_outputs_to_s3(
            task=task,
            downloads=final_result.get("report", {}).get("downloads", []),
            s3_service=s3_service
        )

        # Remove base64 content from response
        final_result["report"]["downloads"] = _strip_base64_from_downloads(
            final_result.get("report", {}).get("downloads", [])
        )

        final_result["s3_output_keys"] = s3_output_keys
        final_result["result_summary"] = _build_result_summary(final_result)

        return final_result

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_code": "PROCESSING_ERROR",
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


async def _upload_outputs_to_s3(
    task: "models.Task",
    downloads: List[Dict],
    s3_service
) -> List[str]:
    """Upload download files to S3 and return keys."""
    s3_keys = []

    for download in downloads:
        content_b64 = download.get("content_base64")
        filename = download.get("file_name")

        if not content_b64 or not filename:
            continue

        # Decode content
        import base64
        content = base64.b64decode(content_b64)

        # Determine content type
        if filename.endswith('.xlsx'):
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif filename.endswith('.json'):
            content_type = "application/json"
        else:
            content_type = "text/csv"

        # Build S3 key
        key = f"users/{task.user_id}/tasks/{task.task_id}/outputs/{filename}"

        # Upload
        s3_service.upload_file(key, content, content_type)
        s3_keys.append(key)

    return s3_keys


def _strip_base64_from_downloads(downloads: List[Dict]) -> List[Dict]:
    """Remove base64 content from downloads (keep metadata only)."""
    return [
        {k: v for k, v in d.items() if k != 'content_base64'}
        for d in downloads
    ]


def _build_result_summary(result: Dict) -> Dict:
    """Build summary from full result."""
    report = result.get("report", {})
    return {
        "total_alerts": len(report.get("alerts", [])),
        "total_issues": len(report.get("issues", [])),
        "total_recommendations": len(report.get("recommendations", [])),
        "execution_time_ms": result.get("execution_time_ms", 0)
    }
```

---

## Phase 4: Downloads & Results

### 4.1 Update Downloads Module

Outputs are now stored in S3 with presigned download URLs.

The current downloads module generates base64 content. We keep that logic but:

1. Upload the generated content to S3
2. Return URLs instead of base64 in API response

This is handled by `_upload_outputs_to_s3` in Phase 3.

---

## Phase 5: Testing & Migration

### 5.1 Test Plan

```
1. Unit Tests
   - [ ] S3Service - all methods
   - [ ] Task creation
   - [ ] Upload URL generation
   - [ ] File verification
   - [ ] Task status transitions

2. Integration Tests
   - [ ] Full flow: create → upload → process → download
   - [ ] Error handling: missing files
   - [ ] Error handling: billing errors
   - [ ] Partial results on failure

3. Load Tests
   - [ ] 10 concurrent uploads
   - [ ] Large file handling (100MB)
```

### 5.2 Migration Checklist

```
Pre-Migration:
- [ ] Database backup
- [ ] B2 credentials verified
- [ ] Test environment validated

Migration:
- [ ] Run database migration
- [ ] Deploy new code
- [ ] Verify task endpoints work
- [ ] Test full flow

Post-Migration:
- [ ] Monitor error rates
- [ ] Check B2 storage growth
- [ ] Verify billing integration
```

---

## File Changes Summary

### New Files

| File                     | Purpose              |
| ------------------------ | -------------------- |
| `services/__init__.py`   | Services module init |
| `services/s3_service.py` | Backblaze B2 client  |
| `api/task_routes.py`     | Task API endpoints   |

### Modified Files

| File                                          | Changes                           |
| --------------------------------------------- | --------------------------------- |
| `db/models.py`                                | Add Task model, TaskStatus enum   |
| `db/schemas.py`                               | Add task-related Pydantic schemas |
| `main.py`                                     | Register task routes              |
| `transformers/profile_my_data_transformer.py` | Add V2 function                   |
| `transformers/clean_my_data_transformer.py`   | Add V2 function                   |
| `transformers/master_my_data_transformer.py`  | Add V2 function                   |

### Database Changes

| Table   | Change                    |
| ------- | ------------------------- |
| `tasks` | NEW table                 |
| `users` | Add relationship to tasks |

---

**Document Status:** Complete  
**Last Updated:** December 19, 2025
