# Database Schema V2.1 - Simplified Task Model

**Document Version:** 2.1  
**Created:** December 19, 2025  
**Updated:** December 19, 2025  
**Purpose:** Simplified database schema for V2.1 task-based architecture

---

## Table of Contents

1. [Overview](#overview)
2. [New Task Model](#new-task-model)
3. [Existing Models (Unchanged)](#existing-models-unchanged)
4. [Migration Strategy](#migration-strategy)
5. [Indexes & Performance](#indexes--performance)
6. [SQLAlchemy Implementation](#sqlalchemy-implementation)

---

## Overview

### Schema Changes Summary

| Change Type   | Model                | Description              |
| ------------- | -------------------- | ------------------------ |
| **NEW**       | `Task`               | Simplified task tracking |
| **Unchanged** | `User`               | User authentication      |
| **Unchanged** | `CreditWallet`       | Credit balance           |
| **Unchanged** | `CreditTransaction`  | Transaction ledger       |
| **Unchanged** | `AgentCost`          | Agent pricing            |
| **Unchanged** | `StripeWebhookEvent` | Stripe events            |

### Key Simplifications from V2

**Removed Fields:**

- ❌ `parameters` - Now stored in B2, not database
- ❌ `files_metadata` - Derived from S3 structure
- ❌ `s3_input_keys` - Derived from user_id/task_id
- ❌ `s3_output_keys` - Retrieved dynamically from B2
- ❌ `result_summary` - Not stored in DB
- ❌ `result_full` - Not stored in DB
- ❌ `partial_results` - Not stored in DB
- ❌ `failed_agent` - Not needed for simplified model
- ❌ `agents_completed` - Not tracked in DB

**Rationale:**

- Files stored at `users/{user_id}/tasks/{task_id}/` - structure is predictable
- Parameters at `users/{user_id}/tasks/{task_id}/inputs/parameters.json`
- Output files listed dynamically from `users/{user_id}/tasks/{task_id}/outputs/`
- No need to duplicate this information in database

### New Relationships

```
User (1) ─────────────────── (*) Task
  │                              │
  │                              │ task_id referenced in
  │                              ▼
  └── (*) CreditTransaction ◄── analysis_id
```

---

## New Task Model

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                               TASK (Simplified)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ PK  task_id          VARCHAR(36)    UUID                                    │
│ FK  user_id          INTEGER        → users.id                              │
│                                                                             │
│     -- Task Configuration --                                                │
│     tool_id          VARCHAR(50)    profile-my-data, clean-my-data, etc    │
│     agents           JSON           ["unified-profiler", "score-risk"]      │
│                                                                             │
│     -- Status Tracking --                                                   │
│     status           VARCHAR(20)    CREATED, UPLOADING, PROCESSING, etc    │
│     progress         INTEGER        0-100                                   │
│     current_agent    VARCHAR(100)   Currently executing agent               │
│                                                                             │
│     -- Error Information --                                                 │
│     error_code       VARCHAR(50)    BILLING_INSUFFICIENT_CREDITS, etc       │
│     error_message    TEXT           Human-readable error                    │
│                                                                             │
│     -- Timestamps --                                                        │
│     created_at       DATETIME       Task creation time                      │
│     upload_started_at DATETIME      When upload URLs generated              │
│     processing_started_at DATETIME  When processing began                   │
│     completed_at     DATETIME       When completed successfully             │
│     failed_at        DATETIME       When task failed                        │
│     cancelled_at     DATETIME       When user cancelled                     │
│     expired_at       DATETIME       When task expired                       │
│     updated_at       DATETIME       Last modification                       │
│                                                                             │
│     -- Cleanup Flags --                                                     │
│     s3_cleaned       BOOLEAN        Whether S3 files cleaned up             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### SQL Table Definition

```sql
CREATE TABLE tasks (
    -- Primary Key
    task_id VARCHAR(36) PRIMARY KEY,

    -- Foreign Keys
    user_id INTEGER NOT NULL,

    -- Task Configuration
    tool_id VARCHAR(50) NOT NULL,
    agents JSON NOT NULL,

    -- Status Tracking
    status VARCHAR(20) NOT NULL DEFAULT 'CREATED',
    progress INTEGER NOT NULL DEFAULT 0,
    current_agent VARCHAR(100),

    -- Error Information
    error_code VARCHAR(50),
    error_message TEXT,

    -- Timestamps
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    upload_started_at DATETIME,
    processing_started_at DATETIME,
    completed_at DATETIME,
    failed_at DATETIME,
    cancelled_at DATETIME,
    expired_at DATETIME,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Cleanup
    s3_cleaned BOOLEAN NOT NULL DEFAULT FALSE,

    -- Constraints
    CONSTRAINT fk_task_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT chk_status CHECK (status IN (
        'CREATED', 'UPLOADING', 'UPLOAD_FAILED', 'QUEUED',
        'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED', 'EXPIRED'
    )),
    CONSTRAINT chk_progress CHECK (progress >= 0 AND progress <= 100),
    CONSTRAINT chk_tool_id CHECK (tool_id IN (
        'profile-my-data', 'clean-my-data', 'master-my-data'
    ))
);

-- Indexes
CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_tasks_tool_id ON tasks(tool_id);
```

### Field Count Comparison

| Version  | Total Fields | Tracking Fields | Data Storage |
| -------- | ------------ | --------------- | ------------ |
| **V2**   | 30+          | 15+             | DB + S3      |
| **V2.1** | 18           | 8               | S3 only      |

**40% fewer fields!**

---

## Existing Models (Unchanged)

### User Model

```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    stripe_customer_id = Column(String(255), unique=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    otp_code = Column(String(6))
    otp_expires_at = Column(DateTime)
    otp_type = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    wallet = relationship("CreditWallet", back_populates="user", uselist=False)
    transactions = relationship("CreditTransaction", back_populates="user")
    tasks = relationship("Task", back_populates="user")  # NEW RELATIONSHIP
```

### CreditTransaction Reference

The existing `CreditTransaction` model already has `analysis_id` field:

```python
class CreditTransaction(Base):
    # ... existing fields ...
    analysis_id = Column(String(100), nullable=True)  # Links to task_id
```

This will now reference `Task.task_id` for proper linking.

---

## Migration Strategy

### Alembic Migration Script

```python
"""Add simplified tasks table for V2.1 architecture

Revision ID: v2_1_001_add_simplified_tasks
Revises: previous_revision
Create Date: 2024-12-19 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers
revision = 'v2_1_001_add_simplified_tasks'
down_revision = 'previous_revision'
branch_labels = None
depends_on = None


def upgrade():
    # Create simplified tasks table
    op.create_table(
        'tasks',
        sa.Column('task_id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),

        # Task Configuration
        sa.Column('tool_id', sa.String(50), nullable=False),
        sa.Column('agents', mysql.JSON, nullable=False),

        # Status Tracking
        sa.Column('status', sa.String(20), nullable=False, default='CREATED'),
        sa.Column('progress', sa.Integer, nullable=False, default=0),
        sa.Column('current_agent', sa.String(100), nullable=True),

        # Error Information
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('upload_started_at', sa.DateTime, nullable=True),
        sa.Column('processing_started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('failed_at', sa.DateTime, nullable=True),
        sa.Column('cancelled_at', sa.DateTime, nullable=True),
        sa.Column('expired_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),

        # Cleanup
        sa.Column('s3_cleaned', sa.Boolean, default=False, nullable=False),
    )

    # Create indexes
    op.create_index('idx_tasks_user_id', 'tasks', ['user_id'])
    op.create_index('idx_tasks_status', 'tasks', ['status'])
    op.create_index('idx_tasks_user_status', 'tasks', ['user_id', 'status'])
    op.create_index('idx_tasks_created_at', 'tasks', ['created_at'])
    op.create_index('idx_tasks_tool_id', 'tasks', ['tool_id'])


def downgrade():
    op.drop_index('idx_tasks_tool_id', 'tasks')
    op.drop_index('idx_tasks_created_at', 'tasks')
    op.drop_index('idx_tasks_user_status', 'tasks')
    op.drop_index('idx_tasks_status', 'tasks')
    op.drop_index('idx_tasks_user_id', 'tasks')
    op.drop_table('tasks')
```

### Manual Migration SQL

For direct execution without Alembic:

```sql
-- Create simplified tasks table
CREATE TABLE IF NOT EXISTS tasks (
    task_id VARCHAR(36) PRIMARY KEY,
    user_id INTEGER NOT NULL,
    tool_id VARCHAR(50) NOT NULL,
    agents JSON NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'CREATED',
    progress INTEGER NOT NULL DEFAULT 0,
    current_agent VARCHAR(100),
    error_code VARCHAR(50),
    error_message TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    upload_started_at DATETIME,
    processing_started_at DATETIME,
    completed_at DATETIME,
    failed_at DATETIME,
    cancelled_at DATETIME,
    expired_at DATETIME,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    s3_cleaned BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_task_user FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Create indexes
CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_tasks_tool_id ON tasks(tool_id);
```

---

## Indexes & Performance

### Index Strategy

| Index Name              | Columns           | Purpose                             |
| ----------------------- | ----------------- | ----------------------------------- |
| `PRIMARY`               | `task_id`         | Primary key lookups                 |
| `idx_tasks_user_id`     | `user_id`         | List user's tasks                   |
| `idx_tasks_status`      | `status`          | Find tasks by status (cleanup jobs) |
| `idx_tasks_user_status` | `user_id, status` | User's tasks filtered by status     |
| `idx_tasks_created_at`  | `created_at`      | Expiry cleanup, sorting             |
| `idx_tasks_tool_id`     | `tool_id`         | Analytics, filtering                |

### Query Patterns

```sql
-- Get user's tasks (paginated)
SELECT * FROM tasks
WHERE user_id = ?
ORDER BY created_at DESC
LIMIT ? OFFSET ?;
-- Uses: idx_tasks_user_id, idx_tasks_created_at

-- Get user's active tasks
SELECT * FROM tasks
WHERE user_id = ? AND status IN ('PROCESSING', 'QUEUED')
ORDER BY created_at DESC;
-- Uses: idx_tasks_user_status

-- Cleanup expired tasks
UPDATE tasks
SET status = 'EXPIRED', expired_at = NOW()
WHERE status = 'CREATED'
AND created_at < NOW() - INTERVAL 15 MINUTE;
-- Uses: idx_tasks_status, idx_tasks_created_at

-- Get task by ID (with user ownership check)
SELECT * FROM tasks
WHERE task_id = ? AND user_id = ?;
-- Uses: PRIMARY
```

### How Data is Retrieved

```python
# Get input files for processing
def get_input_files(task: Task) -> List[str]:
    """Get S3 keys for input files."""
    prefix = f"users/{task.user_id}/tasks/{task.task_id}/inputs/"
    return s3_service.list_files(prefix)

# Get parameters
def get_parameters(task: Task) -> Optional[Dict]:
    """Get parameters from S3."""
    return s3_service.get_parameters(task.user_id, task.task_id)

# Get output files
def get_output_files(task: Task) -> List[Dict]:
    """Get S3 keys for output files."""
    return s3_service.list_output_files(task.user_id, task.task_id)
```

**No database queries needed for file metadata!**

---

## SQLAlchemy Implementation

### Task Model

```python
# db/models.py

from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
import enum


class TaskStatus(str, enum.Enum):
    """Task status enumeration."""
    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Task(Base):
    """
    Simplified Task model for V2.1 architecture.

    Stores minimal tracking information. All file metadata, parameters,
    and results are stored in Backblaze B2, not in database.
    """

    __tablename__ = "tasks"

    # Primary Key - UUID string
    task_id = Column(String(36), primary_key=True, index=True)

    # Foreign Key - User ownership
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Task Configuration
    tool_id = Column(String(50), nullable=False, index=True)
    agents = Column(JSON, nullable=False)  # List of agent IDs

    # Status Tracking
    status = Column(
        String(20),
        nullable=False,
        default=TaskStatus.CREATED.value,
        index=True
    )
    progress = Column(Integer, nullable=False, default=0)
    current_agent = Column(String(100), nullable=True)

    # Error Information
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    upload_started_at = Column(DateTime, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    expired_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Cleanup
    s3_cleaned = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="tasks")

    def __repr__(self):
        return f"<Task(id={self.task_id}, status={self.status}, tool={self.tool_id})>"

    # Helper methods

    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in [
            TaskStatus.COMPLETED.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELLED.value,
            TaskStatus.EXPIRED.value
        ]

    def can_process(self) -> bool:
        """Check if task can be processed."""
        return self.status in [
            TaskStatus.QUEUED.value,
            TaskStatus.UPLOAD_FAILED.value
        ]

    def can_cancel(self) -> bool:
        """Check if task can be cancelled."""
        return self.status in [
            TaskStatus.PROCESSING.value,
            TaskStatus.QUEUED.value
        ]

    def get_s3_prefix(self) -> str:
        """Get S3 prefix for this task."""
        return f"users/{self.user_id}/tasks/{self.task_id}/"

    def get_input_prefix(self) -> str:
        """Get S3 prefix for input files."""
        return f"{self.get_s3_prefix()}inputs/"

    def get_output_prefix(self) -> str:
        """Get S3 prefix for output files."""
        return f"{self.get_s3_prefix()}outputs/"
```

### Update User Model Relationship

```python
# Add to existing User model in db/models.py

class User(Base):
    # ... existing fields ...

    # Add relationship to tasks
    tasks = relationship("Task", back_populates="user", lazy="dynamic")
```

### Pydantic Schemas

```python
# db/schemas.py - Add simplified task schemas

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TaskStatusEnum(str, Enum):
    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class TaskCreateRequest(BaseModel):
    """Simplified request schema for creating a task."""
    tool_id: str = Field(..., description="Tool identifier")
    agents: Optional[List[str]] = Field(None, description="Agent IDs to run")

    class Config:
        json_schema_extra = {
            "example": {
                "tool_id": "profile-my-data",
                "agents": ["unified-profiler", "score-risk"]
            }
        }


class FileMetadata(BaseModel):
    """File metadata for upload URL generation."""
    filename: str
    content_type: str = "text/csv"


class UploadUrlsRequest(BaseModel):
    """Request for upload URLs."""
    files: Dict[str, FileMetadata]
    has_parameters: bool = False


class UploadUrlInfo(BaseModel):
    """Upload URL information."""
    url: str
    key: str
    method: str = "PUT"
    headers: Dict[str, str]
    expires_at: datetime


class UploadUrlsResponse(BaseModel):
    """Response with presigned upload URLs."""
    task_id: str
    status: str
    uploads: Dict[str, UploadUrlInfo]
    expires_in_seconds: int
    message: str


class ProgressDetail(BaseModel):
    """Detailed progress information."""
    current_agent: Optional[str] = None
    agents_total: int
    agents_completed: int


class TaskResponse(BaseModel):
    """Simplified response schema for task status."""
    task_id: str
    status: TaskStatusEnum
    tool_id: str
    agents: List[str]
    progress: int = 0
    progress_detail: Optional[ProgressDetail] = None

    # Timestamps
    created_at: datetime
    upload_started_at: Optional[datetime] = None
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None

    # Results
    downloads_available: bool = False

    # Errors
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class DownloadInfo(BaseModel):
    """Download file information."""
    download_id: str
    filename: str
    type: str
    mime_type: str
    size_bytes: int
    url: str
    expires_at: datetime


class DownloadsResponse(BaseModel):
    """Response with download URLs."""
    task_id: str
    downloads: List[DownloadInfo]
    expires_in_seconds: int


class TaskListResponse(BaseModel):
    """Response for listing tasks."""
    tasks: List[TaskResponse]
    pagination: Dict[str, Any]
```

---

## Data Retention

### Retention Policy

| Data Type       | Retention Period         | Action            |
| --------------- | ------------------------ | ----------------- |
| Task metadata   | 1 year                   | Soft delete after |
| S3 input files  | 7 days after completion  | Delete            |
| S3 output files | 30 days after completion | Delete            |

### Cleanup Queries

```sql
-- Soft delete very old tasks
UPDATE tasks
SET status = 'DELETED'
WHERE created_at < NOW() - INTERVAL 1 YEAR;

-- Find tasks for S3 cleanup (completed > 30 days)
SELECT task_id, user_id
FROM tasks
WHERE status = 'COMPLETED'
AND completed_at < NOW() - INTERVAL 30 DAY
AND s3_cleaned = FALSE;
```

---

## Storage Size Comparison

### V2 (Complex Model)

```
Average task record size:
- 30 fields × ~50 bytes average = ~1.5 KB
- parameters JSON: ~2 KB
- files_metadata JSON: ~500 bytes
- result_summary JSON: ~1 KB
- result_full: ~10-100 KB (can be huge!)
Total per task: ~15-105 KB in database
```

### V2.1 (Simplified Model)

```
Average task record size:
- 18 fields × ~40 bytes average = ~720 bytes
- agents JSON: ~200 bytes
Total per task: ~1 KB in database
```

**95% reduction in database storage!**

---

**Document Status:** Complete  
**Last Updated:** December 19, 2025  
**Version:** 2.1
