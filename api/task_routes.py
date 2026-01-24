"""
Task API Routes for V2.1 Architecture

Endpoints for task-based file processing with Backblaze B2 integration.
Key changes:
- Skip QUEUED status, go directly to PROCESSING after trigger
- Processing happens in background thread OR Celery queue (based on USE_CELERY env var)
- Frontend should poll /tasks/{id} or track from tasks list page
"""

import os
import uuid
import asyncio
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc

from db.database import get_db, SessionLocal
from db import models, schemas
from db.models import TaskStatus
from auth.dependencies import get_current_active_verified_user
from services.s3_service import s3_service


router = APIRouter(prefix="/tasks", tags=["tasks"])


# =============================================================================
# CELERY CONFIGURATION
# =============================================================================

def use_celery() -> bool:
    """Check if Celery queue should be used for task processing."""
    return os.getenv("USE_CELERY", "false").lower() in ("true", "1", "yes")


def send_to_celery(task_id: str, user_id: int) -> str:
    """
    Send task to Celery queue for processing.
    
    Returns:
        Celery task ID
    """
    from celery_queue.tasks import process_analysis
    
    celery_task = process_analysis.delay(task_id, user_id)
    print(f"[Celery] Task {task_id} queued with Celery task ID: {celery_task.id}")
    return celery_task.id


# ============================================================================
# CREATE TASK
# ============================================================================

@router.post("", response_model=schemas.TaskCreateResponse, status_code=201)
async def create_task(
    request: schemas.TaskCreateRequest,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Create a new analysis task.
    
    Note: Parameters are NOT included in this request. They will be uploaded
    to S3 separately using the upload URLs from /tasks/{id}/upload-urls.
    
    Args:
        request: Task creation request with tool_id and optional agents
        
    Returns:
        Created task with task_id and status CREATED
    """
    from main import TOOL_DEFINITIONS

    # Validate tool
    if request.tool_id not in TOOL_DEFINITIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid tool_id: {request.tool_id}. Valid tools: {list(TOOL_DEFINITIONS.keys())}"
        )

    tool_def = TOOL_DEFINITIONS[request.tool_id]

    # Determine agents to run
    if request.agents:
        # Validate requested agents
        available_agents = tool_def["tool"]["available_agents"]
        invalid_agents = [a for a in request.agents if a not in available_agents]
        if invalid_agents:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agents for {request.tool_id}: {invalid_agents}. Available: {available_agents}"
            )
        agents = request.agents
    else:
        agents = tool_def["tool"]["available_agents"]

    # Create task (simplified - no parameters, no files metadata)
    task_id = str(uuid.uuid4())
    task = models.Task(
        task_id=task_id,
        user_id=current_user.id,
        tool_id=request.tool_id,
        agents=agents,
        status=TaskStatus.CREATED.value,
        progress=0
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return schemas.TaskCreateResponse(
        task_id=task.task_id,
        status=schemas.TaskStatusEnum(task.status),
        tool_id=task.tool_id,
        agents=task.agents,
        created_at=task.created_at,
        message="Task created. Request upload URLs to proceed."
    )


# ============================================================================
# GET UPLOAD URLs
# ============================================================================

@router.post("/{task_id}/upload-urls", response_model=schemas.UploadUrlsResponse)
async def get_upload_urls(
    task_id: str,
    request: schemas.UploadUrlsRequest,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Generate presigned URLs for file uploads (including parameters.json).
    
    Frontend should upload files directly to these URLs using PUT method.
    
    Args:
        task_id: Task ID
        request: Upload URLs request with file metadata
        
    Returns:
        Presigned upload URLs for each file and optionally parameters
    """
    # Get task
    task = db.query(models.Task).filter(
        models.Task.task_id == task_id,
        models.Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.can_generate_upload_urls():
        raise HTTPException(
            status_code=400,
            detail=f"Cannot generate upload URLs for task in status: {task.status}. "
                   f"Allowed statuses: CREATED, UPLOAD_FAILED"
        )

    # Generate URLs for each file
    uploads = {}
    expires_in = 900  # 15 minutes

    for file_key, file_meta in request.files.items():
        upload_info = s3_service.generate_upload_url(
            user_id=current_user.id,
            task_id=task_id,
            filename=file_meta.filename,
            content_type=file_meta.content_type,
            expires_in=expires_in
        )
        uploads[file_key] = schemas.UploadUrlInfo(**upload_info)

    # Generate URL for parameters if requested
    if request.has_parameters:
        param_upload_info = s3_service.generate_parameter_upload_url(
            user_id=current_user.id,
            task_id=task_id,
            expires_in=expires_in
        )
        uploads['parameters'] = schemas.UploadUrlInfo(**param_upload_info)

    # Update task status
    task.status = TaskStatus.UPLOADING.value
    task.upload_started_at = datetime.now(timezone.utc)
    db.commit()

    return schemas.UploadUrlsResponse(
        task_id=task_id,
        status=TaskStatus.UPLOADING.value,
        uploads=uploads,
        expires_in_seconds=expires_in,
        message="Upload files directly to the provided URLs using PUT method. Include parameters.json if needed."
    )


# ============================================================================
# TRIGGER PROCESSING
# ============================================================================

@router.post("/{task_id}/process", response_model=schemas.TaskResponse)
async def trigger_processing(
    task_id: str,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Verify uploads and trigger processing in background.
    
    V2.1 Note: We skip QUEUED status and go directly to PROCESSING.
    Processing happens in a background thread - this endpoint returns immediately.
    Frontend should track task progress from the tasks list page.
    
    Args:
        task_id: Task ID
        background_tasks: FastAPI background tasks
        
    Returns:
        Task status (PROCESSING) - immediately after triggering
    """
    from main import TOOL_DEFINITIONS

    # Get task
    task = db.query(models.Task).filter(
        models.Task.task_id == task_id,
        models.Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.can_process():
        raise HTTPException(
            status_code=400,
            detail=f"Cannot process task in status: {task.status}. "
                   f"Allowed statuses: UPLOADING, UPLOAD_FAILED"
        )

    # Verify required files exist in S3
    tool_def = TOOL_DEFINITIONS[task.tool_id]
    tool_files = tool_def["tool"].get("files", {})
    
    required_files = [
        file_key for file_key, file_def in tool_files.items()
        if file_def.get("required", False)
    ]

    verification = s3_service.verify_input_files(
        user_id=current_user.id,
        task_id=task_id,
        required_files=required_files
    )

    if not verification["verified"]:
        task.status = TaskStatus.UPLOAD_FAILED.value
        task.error_message = f"Required files not found: {', '.join(verification['missing'])}"
        db.commit()
        
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "FILES_NOT_FOUND",
                "message": "Required files not found in storage",
                "missing_files": verification["missing"],
                "task_status": TaskStatus.UPLOAD_FAILED.value
            }
        )

    # Skip QUEUED - go directly to PROCESSING (V2.1 simplification)
    # Note: When using Celery, we set QUEUED first, then Celery worker sets PROCESSING
    if use_celery():
        task.status = TaskStatus.QUEUED.value
    else:
        task.status = TaskStatus.PROCESSING.value
    task.processing_started_at = datetime.now(timezone.utc)
    task.progress = 15  # Files verified
    db.commit()
    db.refresh(task)

    # Store user ID for background task (we can't use current_user in background)
    user_id = current_user.id

    # Choose processing method based on USE_CELERY flag
    if use_celery():
        # Use Celery queue for processing
        try:
            celery_task_id = send_to_celery(task_id, user_id)
            message = f"Task queued for processing. Celery task ID: {celery_task_id}"
        except Exception as e:
            print(f"[Celery] Failed to queue task: {e}. Falling back to threading.")
            # Fallback to threading if Celery fails
            task.status = TaskStatus.PROCESSING.value
            db.commit()
            
            def run_background_task():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(_execute_task_background(task_id, user_id))
                finally:
                    loop.close()

            thread = threading.Thread(target=run_background_task, daemon=True)
            thread.start()
            message = "Processing started (fallback to threading)."
    else:
        # Use threading for processing (original behavior)
        def run_background_task():
            """Run the task execution in a separate thread with its own DB session."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_execute_task_background(task_id, user_id))
            finally:
                loop.close()

        thread = threading.Thread(target=run_background_task, daemon=True)
        thread.start()
        message = "Processing started. Track progress from the Tasks page."

    # Return immediately with current status
    return schemas.TaskResponse(
        task_id=task.task_id,
        status=schemas.TaskStatusEnum(task.status),
        tool_id=task.tool_id,
        agents=task.agents,
        progress=task.progress,
        created_at=task.created_at,
        processing_started_at=task.processing_started_at,
        downloads_available=False,
        message=message
    )


async def _execute_task_background(task_id: str, user_id: int):
    """
    Execute task processing in background thread.
    
    Uses its own database session since we're in a separate thread.
    """
    import time
    
    # Create a new database session for this thread
    db = SessionLocal()
    
    try:
        # Get task and user from new session
        task = db.query(models.Task).filter(models.Task.task_id == task_id).first()
        if not task:
            print(f"Background task error: Task {task_id} not found")
            return
            
        current_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not current_user:
            print(f"Background task error: User {user_id} not found")
            task.status = TaskStatus.FAILED.value
            task.error_code = "USER_NOT_FOUND"
            task.error_message = "User not found"
            task.failed_at = datetime.now(timezone.utc)
            db.commit()
            return

        start_time = time.time()

        # Execute based on tool
        result = None
        try:
            if task.tool_id == "profile-my-data":
                from transformers import profile_my_data_transformer
                result = await profile_my_data_transformer.run_profile_my_data_analysis_v2_1(
                    task=task,
                    current_user=current_user,
                    db=db
                )
            elif task.tool_id == "clean-my-data":
                from transformers import clean_my_data_transformer
                result = await clean_my_data_transformer.run_clean_my_data_analysis_v2_1(
                    task=task,
                    current_user=current_user,
                    db=db
                )
            elif task.tool_id == "master-my-data":
                from transformers import master_my_data_transformer
                result = await master_my_data_transformer.run_master_my_data_analysis_v2_1(
                    task=task,
                    current_user=current_user,
                    db=db
                )
            elif task.tool_id == "analyze-my-data" or task.tool_id == "customer-segmentation" or task.tool_id == "experimental-design" or task.tool_id == "market-basket-sequence"  or task.tool_id == "synthetic-control":
                from transformers import analyze_my_data_transformer
                result = await analyze_my_data_transformer.run_analyze_my_data_analysis_v2_1(
                    task=task,
                    current_user=current_user,
                    db=db
                )
            else:
                result = {"status": "error", "error": f"Unknown tool: {task.tool_id}", "error_code": "UNKNOWN_TOOL"}
        except Exception as e:
            result = {"status": "error", "error": str(e), "error_code": "INTERNAL_ERROR"}

        execution_time_ms = int((time.time() - start_time) * 1000)

        # Refresh task to get latest state
        db.refresh(task)

        # Update task based on result
        if result and result.get("status") == "success":
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = datetime.now(timezone.utc)
            task.progress = 100
            task.current_agent = None
            print(f"Task {task_id} completed successfully in {execution_time_ms}ms")
        else:
            task.status = TaskStatus.FAILED.value
            task.failed_at = datetime.now(timezone.utc)
            task.error_code = result.get("error_code", "PROCESSING_ERROR") if result else "PROCESSING_ERROR"
            task.error_message = result.get("error_message") or result.get("error") or "Unknown error" if result else "Unknown error"
            print(f"Task {task_id} failed: {task.error_message}")

        db.commit()
        
    except Exception as e:
        print(f"Background task execution error for task {task_id}: {e}")
        try:
            task = db.query(models.Task).filter(models.Task.task_id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED.value
                task.error_code = "INTERNAL_ERROR"
                task.error_message = str(e)
                task.failed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as db_error:
            print(f"Failed to update task status after error: {db_error}")
    finally:
        db.close()


# ============================================================================
# GET TASK STATUS
# ============================================================================

@router.get("/{task_id}", response_model=schemas.TaskResponse)
async def get_task(
    task_id: str,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Get task status and basic info.
    
    Note: Full results are NOT returned here. Use /downloads endpoint
    to get presigned URLs for output files.
    
    Args:
        task_id: Task ID
        
    Returns:
        Task status and metadata
    """
    task = db.query(models.Task).filter(
        models.Task.task_id == task_id,
        models.Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return schemas.TaskResponse(
        task_id=task.task_id,
        status=schemas.TaskStatusEnum(task.status),
        tool_id=task.tool_id,
        agents=task.agents,
        progress=task.progress,
        created_at=task.created_at,
        upload_started_at=task.upload_started_at,
        processing_started_at=task.processing_started_at,
        completed_at=task.completed_at,
        failed_at=task.failed_at,
        downloads_available=task.status == TaskStatus.COMPLETED.value,
        error_code=task.error_code,
        error_message=task.error_message
    )


# ============================================================================
# GET DOWNLOADS
# ============================================================================

@router.get("/{task_id}/downloads", response_model=schemas.DownloadsResponse)
async def get_downloads(
    task_id: str,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Get presigned download URLs for task outputs.
    
    Output files are stored in S3 and URLs are generated dynamically.
    URLs expire after 1 hour.
    
    Args:
        task_id: Task ID
        
    Returns:
        List of download URLs for output files
    """
    task = db.query(models.Task).filter(
        models.Task.task_id == task_id,
        models.Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Downloads not available for task in status: {task.status}. "
                   f"Task must be COMPLETED."
        )

    # List output files from S3 dynamically
    output_files = s3_service.list_output_files(current_user.id, task_id)
    
    expires_in = 3600  # 1 hour
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    downloads = []
    for file_info in output_files:
        filename = file_info['filename']
        url = s3_service.generate_download_url(file_info['key'], expires_in)

        # Determine mime type based on extension
        if filename.endswith('.xlsx'):
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            file_type = "report"
        elif filename.endswith('.json'):
            mime_type = "application/json"
            file_type = "report"
        elif filename.endswith('.csv'):
            mime_type = "text/csv"
            file_type = "data"
        else:
            mime_type = "application/octet-stream"
            file_type = "other"

        downloads.append(schemas.DownloadInfo(
            download_id=filename.replace('.', '_').replace(' ', '_'),
            filename=filename,
            type=file_type,
            mime_type=mime_type,
            size_bytes=file_info['size_bytes'],
            url=url,
            expires_at=expires_at
        ))

    return schemas.DownloadsResponse(
        task_id=task_id,
        downloads=downloads,
        expires_in_seconds=expires_in
    )


# ============================================================================
# GET TASK REPORT
# ============================================================================

@router.get("/{task_id}/report", response_model=schemas.TaskReportResponse)
async def get_task_report(
    task_id: str,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Get complete analysis report for a completed task.
    
    This endpoint retrieves the JSON report from S3 and converts it to the 
    format expected by the results page (ResultWrapper2). It returns the 
    complete analysis data including alerts, issues, recommendations, 
    executive summary, and all agent outputs.
    
    Args:
        task_id: Task ID
        
    Returns:
        Complete analysis report in the format expected by results page
    """
    import json
    
    # Get task
    task = db.query(models.Task).filter(
        models.Task.task_id == task_id,
        models.Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Report not available for task in status: {task.status}. "
                   f"Task must be COMPLETED."
        )

    # List output files from S3 to find the JSON report
    output_files = s3_service.list_output_files(current_user.id, task_id)
    
    json_report_file = None
    for file_info in output_files:
        if file_info['filename'].endswith('.json'):
            json_report_file = file_info
            break
    
    if not json_report_file:
        raise HTTPException(
            status_code=404,
            detail="JSON report not found in task outputs"
        )
    
    # Download and parse the JSON report
    try:
        json_content = s3_service.get_file_bytes(json_report_file['key'])
        report_data = json.loads(json_content.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse JSON report: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve report: {str(e)}"
        )
    
    # Generate download URLs for the response
    expires_in = 3600  # 1 hour
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    
    downloads_for_report = []
    for file_info in output_files:
        filename = file_info['filename']
        url = s3_service.generate_download_url(file_info['key'], expires_in)

        # Determine mime type based on extension
        if filename.endswith('.xlsx'):
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            file_type = "complete_report"
        elif filename.endswith('.json'):
            mime_type = "application/json"
            file_type = "report"
        elif filename.endswith('.csv'):
            mime_type = "text/csv"
            file_type = "cleaned_data"
        else:
            mime_type = "application/octet-stream"
            file_type = "other"

        downloads_for_report.append({
            "download_id": filename.replace('.', '_').replace(' ', '_'),
            "name": _get_download_name(filename, task.tool_id),
            "format": filename.split('.')[-1] if '.' in filename else "unknown",
            "file_name": filename,
            "description": _get_download_description(filename, task.tool_id),
            "mimeType": mime_type,
            "url": url,
            "size_bytes": file_info['size_bytes'],
            "creation_date": expires_at.isoformat(),
            "type": file_type,
            "expires_at": expires_at.isoformat()
        })
    
    # Build the response in the format expected by the results page
    # Extract data from the JSON report structure
    metadata = report_data.get("metadata", {})
    summary = report_data.get("summary", {})
    
    # Build the report object
    report = {
        "alerts": report_data.get("alerts", []),
        "issues": report_data.get("issues", []),
        "recommendations": report_data.get("recommendations", []),
        "executiveSummary": report_data.get("executive_summary", []),
        "analysisSummary": report_data.get("analysis_summary", {}),
        "rowLevelIssues": report_data.get("row_level_issues", []),
        "issueSummary": report_data.get("issue_summary", {}),
        "routing_decisions": report_data.get("routing_decisions", []),
        "downloads": downloads_for_report,
    }
    
    # Add agent results
    agent_results = report_data.get("agent_results", {})
    for agent_id, agent_output in agent_results.items():
        report[agent_id] = agent_output
    
    return schemas.TaskReportResponse(
        analysis_id=task_id,
        tool=task.tool_id,
        status="success",
        timestamp=metadata.get("timestamp", datetime.now(timezone.utc).isoformat()),
        execution_time_ms=metadata.get("execution_time_ms"),
        report=report
    )


def _get_download_name(filename: str, tool_id: str) -> str:
    """Generate a human-readable name for a download file."""

    from main import TOOL_DEFINITIONS
    
    # Get tool name from TOOL_DEFINITIONS
    tool_name = tool_id
    if tool_id in TOOL_DEFINITIONS:
        tool_name = TOOL_DEFINITIONS[tool_id]["tool"].get("name", tool_id)
    
    
    if filename.endswith('.xlsx'):
        return f"{tool_name} - Complete Analysis Report"
    elif filename.endswith('.json'):
        return f"{tool_name} - JSON Report"
    elif filename.endswith('.csv'):
        if 'cleaned' in filename.lower():
            return f"{tool_name} - Cleaned Data"
        elif 'master' in filename.lower() or 'golden' in filename.lower():
            return f"{tool_name} - Master Data"
        return f"{tool_name} - Data Export"
    return filename


def _get_download_description(filename: str, tool_id: str) -> str:
    """Generate a description for a download file."""
    if filename.endswith('.xlsx'):
        return "Comprehensive Excel report with all analysis data, agent results, and detailed metrics"
    elif filename.endswith('.json'):
        return "Complete hierarchical JSON report with all analysis data, including raw agent outputs"
    elif filename.endswith('.csv'):
        if 'cleaned' in filename.lower():
            return "Cleaned data file with all cleaning operations applied"
        elif 'master' in filename.lower() or 'golden' in filename.lower():
            return "Master data file with golden records"
        return "Data file export"
    return "Output file"


# ============================================================================
# LIST TASKS
# ============================================================================

@router.get("", response_model=schemas.TaskListResponse)
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    tool_id: Optional[str] = Query(None, description="Filter by tool"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    List user's tasks with pagination and filtering.
    
    Args:
        status: Optional status filter
        tool_id: Optional tool filter
        limit: Max results (1-100)
        offset: Pagination offset
        
    Returns:
        Paginated list of tasks
    """
    query = db.query(models.Task).filter(
        models.Task.user_id == current_user.id
    )

    # Apply filters
    if status:
        query = query.filter(models.Task.status == status)
    if tool_id:
        query = query.filter(models.Task.tool_id == tool_id)

    # Get total count
    total = query.count()

    # Apply pagination and ordering
    tasks = query.order_by(desc(models.Task.created_at)).offset(offset).limit(limit).all()

    task_items = [
        schemas.TaskListItem(
            task_id=t.task_id,
            status=schemas.TaskStatusEnum(t.status),
            tool_id=t.tool_id,
            progress=t.progress,
            created_at=t.created_at,
            completed_at=t.completed_at
        )
        for t in tasks
    ]

    return schemas.TaskListResponse(
        tasks=task_items,
        pagination=schemas.PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total
        )
    )


# ============================================================================
# CANCEL TASK
# ============================================================================

@router.post("/{task_id}/cancel", response_model=schemas.TaskCancelResponse)
async def cancel_task(
    task_id: str,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a task in progress.
    
    Note: Credits already consumed are not refunded.
    
    Args:
        task_id: Task ID
        
    Returns:
        Cancelled task status
    """
    task = db.query(models.Task).filter(
        models.Task.task_id == task_id,
        models.Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.can_cancel():
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel task in status: {task.status}. "
                   f"Only PROCESSING or QUEUED tasks can be cancelled."
        )

    task.status = TaskStatus.CANCELLED.value
    task.cancelled_at = datetime.now(timezone.utc)
    db.commit()

    return schemas.TaskCancelResponse(
        task_id=task.task_id,
        status=schemas.TaskStatusEnum(task.status),
        message="Task cancelled successfully",
        cancelled_at=task.cancelled_at
    )


# ============================================================================
# DELETE TASK
# ============================================================================

@router.delete("/{task_id}", response_model=schemas.TaskDeleteResponse)
async def delete_task(
    task_id: str,
    current_user: models.User = Depends(get_current_active_verified_user),
    db: Session = Depends(get_db)
):
    """
    Delete a task and its associated S3 files.
    
    Args:
        task_id: Task ID
        
    Returns:
        Deletion confirmation with files deleted count
    """
    task = db.query(models.Task).filter(
        models.Task.task_id == task_id,
        models.Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Delete S3 files
    files_deleted = 0
    try:
        files_deleted = s3_service.delete_task_files(current_user.id, task_id)
    except Exception as e:
        print(f"Warning: Failed to delete S3 files for task {task_id}: {e}")

    # Delete task from database
    db.delete(task)
    db.commit()

    return schemas.TaskDeleteResponse(
        task_id=task_id,
        message="Task and associated files deleted",
        files_deleted=files_deleted
    )
