# Async Analysis Architecture & File Management

## Overview

This document outlines the architecture for handling data analysis requests asynchronously. The goal is to immediately acknowledge user requests, safely store incoming files without overloading memory, and manage the lifecycle of analysis jobs using a database-driven status system.

## 1. Database Schema Design

We will introduce a new table `analysis_jobs` to track the state of each analysis request.

### Table: `analysis_jobs`

| Column Name  | Type        | Constraints     | Description                                                                  |
| :----------- | :---------- | :-------------- | :--------------------------------------------------------------------------- |
| `id`         | VARCHAR(36) | PRIMARY KEY     | UUID of the analysis job.                                                    |
| `user_id`    | INTEGER     | FOREIGN KEY     | ID of the user who requested the analysis.                                   |
| `tool_id`    | VARCHAR(50) | NOT NULL        | The tool being used (e.g., `profile-my-data`).                               |
| `status`     | ENUM        | NOT NULL        | Current state: `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`.               |
| `created_at` | DATETIME    | DEFAULT NOW()   | Timestamp when the request was received.                                     |
| `updated_at` | DATETIME    | ON UPDATE NOW() | Timestamp of the last status change.                                         |
| `agents`     | TEXT        | NULLABLE        | Comma-separated list of agent IDs used for this analysis (or tool defaults). |
| `error`      | TEXT        | NULLABLE        | Error message if status is `FAILED`.                                         |

**Note**: `parameters_json` is stored as a file (`parameters.json`) in the inputs directory rather than in the database.

### Status Workflow

1.  **PENDING**: File uploaded, job created, waiting for worker.
2.  **PROCESSING**: Worker has picked up the job and is running agents.
3.  **COMPLETED**: Analysis finished successfully, results available.
4.  **FAILED**: Analysis encountered an error.

## 2. File Storage Structure

We will use a structured directory hierarchy to organize files by User and Analysis ID. This ensures isolation and easy cleanup.

### Directory Structure

```
backend/
└── uploads/
    └── {user_id}/
        └── {analysis_id}/
            ├── inputs/
            │   ├── primary.csv
            │   ├── baseline.csv
            │   └── parameters.json
            └── outputs/
                ├── cleaned_data.csv
                ├── report.json
                └── ....other
```

### Naming Conventions

- **Root Folder**: `uploads/` (located in backend root).
- **User Folder**: `{user_id}` (Integer ID of the user).
- **Analysis Folder**: `{analysis_id}` (UUID of the job).
- **Input Folder**: `inputs/` - Stores raw files uploaded by the user and analysis parameters.
  - `primary.csv` - Primary data file.
  - `baseline.csv` - Optional baseline/reference file.
  - `parameters.json` - Agent-specific parameters passed in the API request.
- **Output Folder**: `outputs/` - Stores generated files, reports, and other files if any.
- **File Names**: Keep original filenames or standardize to `primary.csv`, `baseline.csv`, `parameters.json` to avoid encoding issues.

## 3. API Flow (Asynchronous)

### POST `/api/analyze`

**Current Behavior**: Reads files to memory -> Runs Analysis -> Returns Result (Synchronous).
**New Behavior**:

1.  **Receive Request**: Validate inputs (tool_id, agents).
2.  **Generate ID**: Create a unique `analysis_id` (UUID).
3.  **Stream to Disk**:
    - Create directory `uploads/{user_id}/{analysis_id}/inputs/`.
    - Stream uploaded files (`primary`, `baseline`) directly to this folder.
    - Save `agents` and `parameters_json` as a `parameters.json` file in the inputs folder.
    - **Crucial**: Do not load the entire file into RAM.
4.  **Create DB Record**: Insert into `analysis_jobs` with status `PENDING` and `agents` field populated (or null for defaults).
5.  **Return Response**:
    - HTTP 202 Accepted.
    - JSON: `{"analysis_id": "...", "status": "PENDING", "message": "Analysis started."}`.

### GET `/api/analyze/{analysis_id}`

1.  **Lookup**: Fetch job from `analysis_jobs` by `analysis_id`.
2.  **Check Status**:
    - If `PENDING` or `PROCESSING`: Return `{"status": "..."}`.
    - If `COMPLETED`: Return `{"status": "COMPLETED", "result": {...}}`.
    - If `FAILED`: Return `{"status": "FAILED", "error": "..."}`.

### GET `/api/analyses`

1.  **Fetch User's Jobs**: Query `analysis_jobs` table filtered by `user_id` of the authenticated user.
2.  **Order & Pagination**: Sort by `created_at` DESC, support optional pagination (limit, offset).
3.  **Return Response**:
    - HTTP 200 OK.
    - JSON:
    ```json
    {
      "analyses": [
        {
          "id": "...",
          "tool_id": "profile-my-data",
          "status": "COMPLETED",
          "agents": "agent1,agent2",
          "created_at": "2025-12-10T10:30:00Z",
          "updated_at": "2025-12-10T10:45:00Z",
          "error": null
        },
        ...
      ],
      "total": 25,
      "limit": 10,
      "offset": 0
    }
    ```

## 4. Implementation Steps

1.  **Create Model**: Add `AnalysisJob` class to `db/models.py` with columns: `id`, `user_id`, `tool_id`, `status`, `created_at`, `updated_at`, `agents`, and `error`.
2.  **Create Schema**: Add Pydantic models for Job response in `db/schemas.py`.
3.  **Update Routes**:
    - Modify `POST /analyze` to implement the file streaming and DB insertion logic.
    - Store `agents` field in the database record.
    - Save `agents` and `parameters_json` as `parameters.json` file in the inputs folder.
    - Add `GET /analyze/{analysis_id}` endpoint.
    - Add `GET /analyses` endpoint to list all analyses for the authenticated user (with pagination support).
4.  **Update Transformers**:
    - Refactor transformers to accept file paths derived from `user_id` and `analysis_id` instead of `UploadFile` objects.
    - Update them to read from `uploads/{user_id}/{analysis_id}/inputs/`, including reading `parameters.json` from disk.
5.  **File Discovery**:
    - When retrieving job details, dynamically determine available files from the directory structure using `user_id` and `analysis_id`.
    - No database queries needed for file references; they are known from the directory layout.
6.  **Background Execution**:
    - (Temporary) Trigger the transformer in a `BackgroundTasks` (FastAPI) or separate thread after sending the response.
    - (Future) Push task ID to a queue (Redis) for a separate worker process.

## 5. Code Snippets

### Streaming Upload to Disk

```python
import shutil
from pathlib import Path

def save_upload_file(upload_file: UploadFile, destination: Path):
    try:
        with destination.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    finally:
        upload_file.file.close()
```

### Database Model

```python
class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    tool_id = Column(String(50))
    status = Column(Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED"), default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    agents = Column(String(500), nullable=True)  # Comma-separated or None for defaults
    error = Column(Text, nullable=True)

    # File paths are derived from: uploads/{user_id}/{id}/inputs/ and uploads/{user_id}/{id}/outputs/
    # Parameters JSON is stored as a file: uploads/{user_id}/{id}/inputs/parameters.json
```
