# Frontend Integration Guide

**Last Updated:** December 20, 2025  
**Audience:** Frontend Developers & AI Agents

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Complete User Flow](#complete-user-flow)
4. [API Reference](#api-reference)
5. [TypeScript Types](#typescript-types)
6. [Implementation Guide](#implementation-guide)
7. [State Management](#state-management)
8. [Error Handling](#error-handling)
9. [UI Components](#ui-components)
10. [Code Examples](#code-examples)
11. [Best Practices](#best-practices)

---

## Quick Start

### Task-Based Flow (5 Steps - Async Model)

```
1. POST /tasks                     → Create task, get task_id
2. POST /tasks/{id}/upload-urls    → Get presigned S3 URLs
3. PUT to S3 URLs                  → Upload files directly to B2
4. POST /tasks/{id}/process        → Trigger processing (returns immediately!)
5. Navigate to /tasks              → User tracks progress from Tasks List
```

**V2.1.1 Change:** Step 4 now returns immediately. Processing happens in the background. No polling required during task creation. User tracks progress from the Tasks List page.

### Key Features

| Feature              | Description                           |
| -------------------- | ------------------------------------- |
| File Upload          | Direct to Backblaze B2 presigned URLs |
| Parameters           | Uploaded as `parameters.json` to S3   |
| Results              | Download from presigned URLs          |
| **Async Processing** | Backend processes in background       |
| **Immediate Return** | Frontend redirects immediately        |
| **Task Tracking**    | Progress tracked from Tasks List page |

---

## Architecture Overview

### Sequence Diagram

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐
│ Frontend │    │  Backend │    │   B2/S3  │    │  Database │
└────┬─────┘    └────┬─────┘    └────┬─────┘    └─────┬─────┘
     │               │               │                │
     │ POST /tasks   │               │                │
     │──────────────>│               │                │
     │               │ INSERT task   │                │
     │               │───────────────────────────────>│
     │   task_id     │               │                │
     │<──────────────│               │                │
     │               │               │                │
     │ POST /upload-urls             │                │
     │──────────────>│               │                │
     │               │ Generate URLs │                │
     │               │──────────────>│                │
     │ presigned URLs│               │                │
     │<──────────────│               │                │
     │               │               │                │
     │ PUT file      │               │                │
     │───────────────────────────────>│                │
     │               │               │  (file stored) │
     │               │               │                │
     │ POST /process │               │                │
     │──────────────>│               │                │
     │               │ Verify files  │                │
     │               │──────────────>│                │
     │               │ Get files     │                │
     │               │<──────────────│                │
     │               │ Execute agents│                │
     │               │ Upload outputs│                │
     │               │──────────────>│                │
     │               │ UPDATE task   │                │
     │               │───────────────────────────────>│
     │  COMPLETED    │               │                │
     │<──────────────│               │                │
     │               │               │                │
     │ GET /downloads│               │                │
     │──────────────>│               │                │
     │               │ List outputs  │                │
     │               │──────────────>│                │
     │ download URLs │               │                │
     │<──────────────│               │                │
     │               │               │                │
     │ GET file      │               │                │
     │───────────────────────────────>│                │
     │ file content  │               │                │
     │<──────────────────────────────│                │
```

### Key Concepts

1. **Task**: A unit of work with a lifecycle (CREATED → UPLOADING → PROCESSING → COMPLETED)
2. **Presigned URLs**: Time-limited URLs that allow direct upload/download to S3
3. **Polling**: Periodically checking task status during processing
4. **Downloads**: Output files stored in S3, accessed via presigned URLs

---

## Complete User Flow

### Step-by-Step Implementation

#### Step 1: Create Task

```typescript
// Request
const response = await fetch('/tasks', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    tool_id: 'profile-my-data',
    agents: ['unified-profiler', 'score-risk']  // Optional, defaults to all
  })
});

// Response
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "CREATED",
  "tool_id": "profile-my-data",
  "agents": ["unified-profiler", "score-risk"],
  "created_at": "2025-12-19T10:00:00Z",
  "message": "Task created. Request upload URLs to proceed."
}
```

#### Step 2: Get Upload URLs

```typescript
// Request
const uploadUrlsResponse = await fetch(`/tasks/${taskId}/upload-urls`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    files: {
      primary: {
        filename: 'customer_data.csv',
        content_type: 'text/csv'
      }
      // Optional: baseline for drift detection
      // baseline: {
      //   filename: 'baseline.csv',
      //   content_type: 'text/csv'
      // }
    },
    has_parameters: true  // Set true if you have parameters to upload
  })
});

// Response
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "UPLOADING",
  "uploads": {
    "primary": {
      "url": "https://s3.us-east-005.backblazeb2.com/agensium-files/users/123/tasks/550e.../inputs/customer_data.csv?X-Amz-Algorithm=...",
      "key": "users/123/tasks/550e8400-e29b-41d4-a716-446655440000/inputs/customer_data.csv",
      "method": "PUT",
      "headers": {
        "Content-Type": "text/csv"
      },
      "expires_at": "2025-12-19T10:15:00Z"
    },
    "parameters": {
      "url": "https://s3.us-east-005.backblazeb2.com/agensium-files/users/123/tasks/550e.../inputs/parameters.json?X-Amz-Algorithm=...",
      "key": "users/123/tasks/550e8400-e29b-41d4-a716-446655440000/inputs/parameters.json",
      "method": "PUT",
      "headers": {
        "Content-Type": "application/json"
      },
      "expires_at": "2025-12-19T10:15:00Z"
    }
  },
  "expires_in_seconds": 900,
  "message": "Upload files directly to the provided URLs using PUT method."
}
```

#### Step 3: Upload Files to S3

```typescript
// Upload data file
await fetch(uploads.primary.url, {
  method: "PUT",
  headers: uploads.primary.headers,
  body: file, // File object from input element
});

// Upload parameters (if has_parameters was true)
const parameters = {
  // Agent-specific parameters
  "unified-profiler": {
    sample_size: 10000,
  },
  "score-risk": {
    risk_threshold: 0.7,
  },
};

await fetch(uploads.parameters.url, {
  method: "PUT",
  headers: uploads.parameters.headers,
  body: JSON.stringify(parameters),
});
```

**Important S3 Upload Notes:**

- Use `PUT` method (not POST)
- Include the exact headers from the response
- Do NOT include Authorization header (URL is pre-signed)
- Handle CORS errors (should be configured on B2 bucket)

#### Step 4: Trigger Processing (Async)

```typescript
// Request
const processResponse = await fetch(`/tasks/${taskId}/process`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

// Response (Immediate - V2.1.1 Async Model)
// Backend returns immediately! Processing continues in background.
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING",
  "message": "Processing started. Track progress from the Tasks page.",
  "tool_id": "profile-my-data",
  "agents": ["unified-profiler", "score-risk"],
  "progress": 0,
  "created_at": "2025-12-19T10:00:00Z",
  "processing_started_at": "2025-12-19T10:01:00Z"
}

// Response (if failed - e.g., billing error)
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "FAILED",
  "error_code": "BILLING_INSUFFICIENT_CREDITS",
  "error_message": "Insufficient credits for agent execution",
  "failed_at": "2025-12-19T10:01:30Z"
}
```

**V2.1.1 Async Behavior:**

- Backend returns **immediately** after starting background processing
- No need to wait for completion during task creation flow
- Frontend should **navigate to /tasks** after receiving this response
- User tracks progress from the Tasks List page

#### Step 5: Navigate to Tasks List

After triggering processing, redirect the user to the Tasks List page:

```typescript
// After receiving the processing response
if (processResponse.status === "PROCESSING") {
  // Show success message
  toast.success("Task started! Track progress from the Tasks page.");

  // Navigate to tasks list
  navigate("/tasks");
}
```

The Tasks List page shows all user tasks with their current status. Users can:

- See real-time status updates (PROCESSING → COMPLETED)
- View task details when completed
- Download results from completed tasks

#### Step 6: Get Downloads (From Tasks List)

When viewing a completed task from the Tasks List:

```typescript
const response = await fetch(`/tasks/${taskId}/downloads`, {
  headers: { 'Authorization': `Bearer ${token}` }
});

// Response
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "downloads": [
    {
      "filename": "profile_report.json",
      "url": "https://s3.../outputs/profile_report.json?X-Amz-...",
      "content_type": "application/json",
      "size_bytes": 45678,
      "expires_at": "2025-12-19T11:00:00Z"
    }
  ]
}
```

---

## Polling for Status (Tasks List Page)

On the Tasks List page, poll for status updates:

```typescript
const pollStatus = async (taskId: string): Promise<TaskResponse> => {
  const response = await fetch(`/tasks/${taskId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return response.json();
};

// Polling loop for tasks in PROCESSING status
const refreshProcessingTasks = async (tasks: Task[]): Promise<void> => {
  const processingTasks = tasks.filter((t) => t.status === "PROCESSING");

  for (const task of processingTasks) {
    const updated = await pollStatus(task.task_id);
    // Update task in state
  }
};

// Poll every 5 seconds
useEffect(() => {
  const interval = setInterval(() => {
    refreshProcessingTasks(tasks);
  }, 5000);

  return () => clearInterval(interval);
}, [tasks]);
```

---

## API Reference

### Base URL

```
Production: https://api.agensium.com
Development: http://localhost:8000
```

### Authentication

All endpoints require Bearer token authentication:

```
Authorization: Bearer <jwt_token>
```

---

### POST /tasks

Create a new analysis task.

**Request:**

```typescript
interface TaskCreateRequest {
  tool_id: "profile-my-data" | "clean-my-data" | "master-my-data";
  agents?: string[]; // Optional, defaults to tool's available_agents
}
```

**Response:** `201 Created`

```typescript
interface TaskCreateResponse {
  task_id: string; // UUID
  status: "CREATED";
  tool_id: string;
  agents: string[];
  created_at: string; // ISO 8601
  message: string;
}
```

**Errors:**
| Code | Error | Description |
|------|-------|-------------|
| 400 | Invalid tool_id | Tool not found |
| 400 | Invalid agents | Agent not available for tool |
| 401 | Unauthorized | Missing or invalid token |

---

### POST /tasks/{task_id}/upload-urls

Get presigned URLs for file uploads.

**Request:**

```typescript
interface UploadUrlsRequest {
  files: {
    [key: string]: {
      // 'primary', 'baseline', etc.
      filename: string;
      content_type: string; // 'text/csv', 'application/vnd.ms-excel', etc.
    };
  };
  has_parameters: boolean; // Include parameters.json URL
}
```

**Response:** `200 OK`

```typescript
interface UploadUrlsResponse {
  task_id: string;
  status: "UPLOADING";
  uploads: {
    [key: string]: UploadUrlInfo;
  };
  expires_in_seconds: number; // 900 (15 minutes)
  message: string;
}

interface UploadUrlInfo {
  url: string; // Presigned PUT URL
  key: string; // S3 object key
  method: "PUT";
  headers: {
    "Content-Type": string;
  };
  expires_at: string; // ISO 8601
}
```

**Errors:**
| Code | Error | Description |
|------|-------|-------------|
| 400 | Invalid status | Task not in CREATED or UPLOAD_FAILED status |
| 404 | Not found | Task doesn't exist or belongs to another user |

---

### POST /tasks/{task_id}/process

Trigger task processing.

**Request:** No body required

**Response:** `200 OK`

```typescript
interface TaskResponse {
  task_id: string;
  status: TaskStatus;
  tool_id: string;
  agents: string[];
  progress: number; // 0-100
  created_at: string;
  upload_started_at?: string;
  processing_started_at?: string;
  completed_at?: string;
  failed_at?: string;
  downloads_available: boolean;
  execution_time_ms?: number;
  error_code?: string;
  error_message?: string;
  message?: string;
}

type TaskStatus =
  | "CREATED"
  | "UPLOADING"
  | "UPLOAD_FAILED"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "EXPIRED";
```

**Errors:**
| Code | Error | Description |
|------|-------|-------------|
| 400 | FILES_NOT_FOUND | Required files not in S3 |
| 400 | Invalid status | Task not in UPLOADING status |
| 402 | BILLING_INSUFFICIENT_CREDITS | Not enough credits for all agents |
| 500 | PROCESSING_ERROR | Agent execution failed |

> **Note:** Billing is checked **upfront** for ALL agents before execution begins. If the user doesn't have enough credits for all selected agents, the task fails immediately with `BILLING_INSUFFICIENT_CREDITS` - no partial execution occurs.

---

### GET /tasks/{task_id}

Get task status.

**Response:** `200 OK` - Same as TaskResponse above

---

### GET /tasks/{task_id}/downloads

Get download URLs for completed task.

**Response:** `200 OK`

```typescript
interface DownloadsResponse {
  task_id: string;
  downloads: DownloadInfo[];
  expires_in_seconds: number; // 3600 (1 hour)
}

interface DownloadInfo {
  download_id: string;
  filename: string;
  type: "report" | "data" | "other";
  mime_type: string;
  size_bytes: number;
  url: string; // Presigned GET URL
  expires_at: string; // ISO 8601
}
```

**Errors:**
| Code | Error | Description |
|------|-------|-------------|
| 400 | Task not completed | Downloads only available for COMPLETED tasks |
| 404 | Not found | Task doesn't exist |

---

### GET /tasks/{task_id}/report

Get the complete analysis report for viewing in the results pages. This endpoint retrieves the JSON report from S3 and formats it for the frontend ResultWrapper2 component.

**Response:** `200 OK`

```typescript
interface TaskReportResponse {
  analysis_id: string; // Same as task_id
  tool: string; // Tool identifier
  status: "success" | "error";
  timestamp: string; // ISO 8601
  execution_time_ms: number;
  report: {
    executiveSummary?: object;
    analysisSummary?: object;
    rowLevelIssues?: any[];
    issueSummary?: object;
    routingDecisions?: any[];
    downloads: DownloadInfo[];
    agentResults?: Record<string, any>;
    [key: string]: any; // Additional fields from JSON report
  };
}
```

**Usage:** This endpoint is used by the `ResultWrapper2` component to display completed task results.

**Frontend Hook:**

```typescript
import { useGetTaskReport } from "@/services/taskServicesV2";

function ResultsPage({ taskId }) {
  const { data, isLoading, error } = useGetTaskReport(taskId);

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return <ProfileMyDataResult result={data} />;
}
```

**Errors:**
| Code | Error | Description |
|------|-------|-------------|
| 400 | Task not completed | Report only available for COMPLETED tasks |
| 404 | Not found | Task doesn't exist |
| 404 | Report not found | No JSON report file in S3 |

---

### GET /tasks

List user's tasks with pagination.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | - | Filter by status |
| tool_id | string | - | Filter by tool |
| limit | number | 20 | Max results (1-100) |
| offset | number | 0 | Pagination offset |

**Response:** `200 OK`

```typescript
interface TaskListResponse {
  tasks: TaskListItem[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

interface TaskListItem {
  task_id: string;
  status: TaskStatus;
  tool_id: string;
  progress: number;
  created_at: string;
  completed_at?: string;
}
```

---

### POST /tasks/{task_id}/cancel

Cancel a processing task.

**Response:** `200 OK`

```typescript
interface TaskCancelResponse {
  task_id: string;
  status: "CANCELLED";
  message: string;
  cancelled_at: string;
}
```

**Errors:**
| Code | Error | Description |
|------|-------|-------------|
| 400 | Cannot cancel | Task not in PROCESSING or QUEUED status |

---

### DELETE /tasks/{task_id}

Delete task and S3 files.

**Response:** `200 OK`

```typescript
interface TaskDeleteResponse {
  task_id: string;
  message: string;
  files_deleted: number;
}
```

---

## TypeScript Types

### Complete Type Definitions

```typescript
// ============================================================================
// ENUMS
// ============================================================================

export type TaskStatus =
  | "CREATED"
  | "UPLOADING"
  | "UPLOAD_FAILED"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "EXPIRED";

export type ToolId = "profile-my-data" | "clean-my-data" | "master-my-data";

export type FileType = "report" | "data" | "other";

// ============================================================================
// REQUEST TYPES
// ============================================================================

export interface TaskCreateRequest {
  tool_id: ToolId;
  agents?: string[];
}

export interface FileMetadata {
  filename: string;
  content_type: string;
}

export interface UploadUrlsRequest {
  files: Record<string, FileMetadata>;
  has_parameters: boolean;
}

// ============================================================================
// RESPONSE TYPES
// ============================================================================

export interface TaskCreateResponse {
  task_id: string;
  status: TaskStatus;
  tool_id: ToolId;
  agents: string[];
  created_at: string;
  message: string;
}

export interface UploadUrlInfo {
  url: string;
  key: string;
  method: "PUT";
  headers: Record<string, string>;
  expires_at: string;
}

export interface UploadUrlsResponse {
  task_id: string;
  status: TaskStatus;
  uploads: Record<string, UploadUrlInfo>;
  expires_in_seconds: number;
  message: string;
}

export interface TaskResponse {
  task_id: string;
  status: TaskStatus;
  tool_id: ToolId;
  agents: string[];
  progress: number;
  created_at: string;
  upload_started_at?: string;
  processing_started_at?: string;
  completed_at?: string;
  failed_at?: string;
  downloads_available: boolean;
  execution_time_ms?: number;
  error_code?: string;
  error_message?: string;
  message?: string;
}

export interface DownloadInfo {
  download_id: string;
  filename: string;
  type: FileType;
  mime_type: string;
  size_bytes: number;
  url: string;
  expires_at: string;
}

export interface DownloadsResponse {
  task_id: string;
  downloads: DownloadInfo[];
  expires_in_seconds: number;
}

export interface TaskListItem {
  task_id: string;
  status: TaskStatus;
  tool_id: ToolId;
  progress: number;
  created_at: string;
  completed_at?: string;
}

export interface PaginationInfo {
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface TaskListResponse {
  tasks: TaskListItem[];
  pagination: PaginationInfo;
}

export interface TaskCancelResponse {
  task_id: string;
  status: "CANCELLED";
  message: string;
  cancelled_at: string;
}

export interface TaskDeleteResponse {
  task_id: string;
  message: string;
  files_deleted: number;
}

// ============================================================================
// ERROR TYPES
// ============================================================================

export interface ApiError {
  detail: string;
  error_code?: string;
}

export interface FilesNotFoundError {
  error_code: "FILES_NOT_FOUND";
  message: string;
  missing_files: string[];
  task_status: "UPLOAD_FAILED";
}

// ============================================================================
// PARAMETERS TYPES (for parameters.json)
// ============================================================================

export interface ProfileParameters {
  "unified-profiler"?: {
    sample_size?: number;
    include_correlations?: boolean;
  };
  "score-risk"?: {
    risk_threshold?: number;
    weights?: Record<string, number>;
  };
  "drift-detector"?: {
    baseline_column_mapping?: Record<string, string>;
  };
}

export interface CleanParameters {
  "null-handler"?: {
    strategy?:
      | "drop"
      | "fill_mean"
      | "fill_median"
      | "fill_mode"
      | "fill_value";
    fill_value?: any;
    columns?: string[];
  };
  "outlier-remover"?: {
    method?: "iqr" | "zscore";
    threshold?: number;
    columns?: string[];
  };
  "type-fixer"?: {
    column_types?: Record<string, "string" | "number" | "date" | "boolean">;
  };
  "duplicate-resolver"?: {
    key_columns?: string[];
    keep?: "first" | "last";
  };
}

export interface MasterParameters {
  "key-identifier"?: {
    candidate_columns?: string[];
    uniqueness_threshold?: number;
  };
  "semantic-mapper"?: {
    source_columns?: string[];
    target_schema?: Record<string, string>;
  };
  "golden-record-builder"?: {
    survivorship_rules?: Record<
      string,
      "most_recent" | "most_frequent" | "longest"
    >;
  };
}
```

---

## Implementation Guide

### API Client

```typescript
// api/taskApi.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class TaskApi {
  private token: string;

  constructor(token: string) {
    this.token = token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${this.token}`,
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new ApiError(error.detail, error.error_code);
    }

    return response.json();
  }

  // Create task
  async createTask(request: TaskCreateRequest): Promise<TaskCreateResponse> {
    return this.request("/tasks", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  // Get upload URLs
  async getUploadUrls(
    taskId: string,
    request: UploadUrlsRequest
  ): Promise<UploadUrlsResponse> {
    return this.request(`/tasks/${taskId}/upload-urls`, {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  // Upload file to S3 (no auth header!)
  async uploadToS3(
    uploadInfo: UploadUrlInfo,
    content: Blob | string
  ): Promise<void> {
    const response = await fetch(uploadInfo.url, {
      method: "PUT",
      headers: uploadInfo.headers,
      body: content,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }
  }

  // Trigger processing
  async triggerProcessing(taskId: string): Promise<TaskResponse> {
    return this.request(`/tasks/${taskId}/process`, {
      method: "POST",
    });
  }

  // Get task status
  async getTask(taskId: string): Promise<TaskResponse> {
    return this.request(`/tasks/${taskId}`);
  }

  // Get downloads
  async getDownloads(taskId: string): Promise<DownloadsResponse> {
    return this.request(`/tasks/${taskId}/downloads`);
  }

  // List tasks
  async listTasks(params?: {
    status?: TaskStatus;
    tool_id?: ToolId;
    limit?: number;
    offset?: number;
  }): Promise<TaskListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.tool_id) searchParams.set("tool_id", params.tool_id);
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.offset) searchParams.set("offset", params.offset.toString());

    const query = searchParams.toString();
    return this.request(`/tasks${query ? `?${query}` : ""}`);
  }

  // Cancel task
  async cancelTask(taskId: string): Promise<TaskCancelResponse> {
    return this.request(`/tasks/${taskId}/cancel`, {
      method: "POST",
    });
  }

  // Delete task
  async deleteTask(taskId: string): Promise<TaskDeleteResponse> {
    return this.request(`/tasks/${taskId}`, {
      method: "DELETE",
    });
  }
}

class ApiError extends Error {
  code?: string;

  constructor(message: string, code?: string) {
    super(message);
    this.code = code;
  }
}

export { TaskApi, ApiError };
```

---

### Task Orchestrator Hook (Async Model - V2.1.1)

```typescript
// hooks/useTaskOrchestratorAsync.ts

import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { TaskApi, ApiError } from "../api/taskApi";

interface UseTaskOrchestratorAsyncOptions {
  onStepChange?: (step: string) => void;
  onTriggered?: (taskId: string) => void;
  onError?: (error: ApiError) => void;
  navigateOnComplete?: boolean; // Default: true
}

export function useTaskOrchestratorAsync(
  token: string,
  options: UseTaskOrchestratorAsyncOptions = {}
) {
  const {
    onStepChange,
    onTriggered,
    onError,
    navigateOnComplete = true,
  } = options;

  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const api = new TaskApi(token);

  const runAnalysisAsync = useCallback(
    async (
      toolId: ToolId,
      files: { [key: string]: File },
      parameters?: Record<string, any>,
      agents?: string[]
    ) => {
      setIsLoading(true);
      setError(null);

      try {
        // Step 1: Create task
        setCurrentStep("creating");
        onStepChange?.("creating");
        const createResponse = await api.createTask({
          tool_id: toolId,
          agents,
        });
        setTaskId(createResponse.task_id);

        // Step 2: Get upload URLs
        setCurrentStep("getting_urls");
        onStepChange?.("getting_urls");
        const filesMetadata: Record<string, FileMetadata> = {};
        for (const [key, file] of Object.entries(files)) {
          filesMetadata[key] = {
            filename: file.name,
            content_type: file.type || "text/csv",
          };
        }

        const uploadResponse = await api.getUploadUrls(createResponse.task_id, {
          files: filesMetadata,
          has_parameters: !!parameters,
        });

        // Step 3: Upload files
        setCurrentStep("uploading");
        onStepChange?.("uploading");
        for (const [key, file] of Object.entries(files)) {
          const uploadInfo = uploadResponse.uploads[key];
          if (uploadInfo) {
            await api.uploadToS3(uploadInfo, file);
          }
        }

        // Upload parameters if provided
        if (parameters && uploadResponse.uploads.parameters) {
          await api.uploadToS3(
            uploadResponse.uploads.parameters,
            JSON.stringify(parameters)
          );
        }

        // Step 4: Trigger processing (ASYNC - returns immediately!)
        setCurrentStep("triggering");
        onStepChange?.("triggering");
        const triggerResponse = await api.triggerProcessing(
          createResponse.task_id
        );

        // Backend returns immediately with status: "PROCESSING"
        // No polling here! User tracks from Tasks List page.

        setCurrentStep("triggered");
        onStepChange?.("triggered");
        onTriggered?.(createResponse.task_id);

        // Navigate to tasks list page
        if (navigateOnComplete) {
          setTimeout(() => {
            navigate("/tasks");
          }, 3000); // 3 second delay to show success message
        }

        return {
          taskId: createResponse.task_id,
          status: triggerResponse.status,
        };
      } catch (err) {
        const apiError =
          err instanceof ApiError ? err : new ApiError((err as Error).message);
        setError(apiError);
        onError?.(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [api, onStepChange, onTriggered, onError, navigateOnComplete, navigate]
  );

  return {
    runAnalysisAsync,
    isLoading,
    taskId,
    currentStep,
    error,
  };
}
```

**Key Changes from Sync Model:**

- No polling during task creation flow
- Returns immediately after triggering processing
- Navigates user to `/tasks` page to track progress
- Steps: creating → getting_urls → uploading → triggering → triggered

````

---

## State Management

### Task State Machine

```typescript
// state/taskMachine.ts (using XState or similar)

const taskStates = {
  idle: {
    on: { START: "creating" },
  },
  creating: {
    on: {
      CREATED: "uploading",
      ERROR: "error",
    },
  },
  uploading: {
    on: {
      UPLOADED: "processing",
      ERROR: "upload_failed",
    },
  },
  upload_failed: {
    on: {
      RETRY: "uploading",
      CANCEL: "idle",
    },
  },
  processing: {
    on: {
      PROGRESS: "processing", // Self-transition with progress update
      COMPLETED: "completed",
      FAILED: "failed",
      CANCEL: "cancelled",
    },
  },
  completed: {
    type: "final",
  },
  failed: {
    on: { RETRY: "creating" },
  },
  cancelled: {
    type: "final",
  },
  error: {
    on: { RETRY: "idle" },
  },
};
````

### Redux/Zustand Store

```typescript
// store/taskStore.ts (using Zustand)

import { create } from "zustand";

interface TaskState {
  // Current task
  currentTaskId: string | null;
  status: TaskStatus | null;
  progress: number;
  error: string | null;

  // Downloads
  downloads: DownloadInfo[];

  // History
  taskHistory: TaskListItem[];

  // Actions
  setTask: (taskId: string, status: TaskStatus) => void;
  setProgress: (progress: number) => void;
  setError: (error: string) => void;
  setDownloads: (downloads: DownloadInfo[]) => void;
  reset: () => void;
}

export const useTaskStore = create<TaskState>((set) => ({
  currentTaskId: null,
  status: null,
  progress: 0,
  error: null,
  downloads: [],
  taskHistory: [],

  setTask: (taskId, status) => set({ currentTaskId: taskId, status }),
  setProgress: (progress) => set({ progress }),
  setError: (error) => set({ error }),
  setDownloads: (downloads) => set({ downloads }),
  reset: () =>
    set({
      currentTaskId: null,
      status: null,
      progress: 0,
      error: null,
      downloads: [],
    }),
}));
```

---

## Error Handling

### Billing System

The billing system uses **upfront credit validation**. When you trigger task processing:

1. The system calculates the total cost for ALL selected agents
2. Checks if the user can afford the total cost
3. If insufficient credits: Returns `BILLING_INSUFFICIENT_CREDITS` immediately (no partial execution)
4. If sufficient credits: Deducts ALL credits upfront, then runs agents

This means:

- **No partial results** - Either all agents execute or none do
- **Predictable costs** - Users know upfront if they can afford the task
- **Simple error handling** - Only one billing error to handle

#### Billing Error Response

```typescript
// 402 Payment Required
{
  "status": "error",
  "error_code": "BILLING_INSUFFICIENT_CREDITS",
  "error_message": "Insufficient credits for agent execution. Required: 150, Available: 50",
  "context": {
    "available": 50,      // Current balance
    "required": 150,      // Total cost for all agents
    "shortfall": 100,     // How many more credits needed
    "breakdown": {        // Cost per agent
      "unified-profiler": 50,
      "score-risk": 50,
      "drift-detector": 50
    }
  },
  "execution_time_ms": 125
}
```

#### Handling Billing Errors

```typescript
const handleProcessingResponse = (response: TaskResponse) => {
  if (response.error_code === "BILLING_INSUFFICIENT_CREDITS") {
    const shortfall = response.context?.shortfall || 0;
    showModal({
      title: "Insufficient Credits",
      message: `You need ${shortfall} more credits to run this analysis.`,
      actions: [
        { label: "Purchase Credits", onClick: () => router.push("/billing") },
        { label: "Select Fewer Agents", onClick: () => openAgentSelector() },
      ],
    });
    return;
  }
  // Handle other errors...
};
```

### Error Codes Reference

| Error Code                     | HTTP | Description                  | User Action              |
| ------------------------------ | ---- | ---------------------------- | ------------------------ |
| `FILES_NOT_FOUND`              | 400  | Required files missing in S3 | Re-upload files          |
| `BILLING_INSUFFICIENT_CREDITS` | 402  | Not enough credits           | Purchase credits         |
| `PROCESSING_ERROR`             | 500  | Agent execution failed       | Retry or contact support |
| `INVALID_TOOL_ID`              | 400  | Unknown tool                 | Check tool_id spelling   |
| `INVALID_AGENTS`               | 400  | Unknown agents               | Check available agents   |
| `UPLOAD_EXPIRED`               | 400  | Upload URLs expired          | Get new upload URLs      |

### Error Handling Component

```typescript
// components/TaskErrorHandler.tsx

interface TaskErrorHandlerProps {
  error: ApiError;
  onRetry: () => void;
  onCancel: () => void;
}

export function TaskErrorHandler({
  error,
  onRetry,
  onCancel,
}: TaskErrorHandlerProps) {
  const getErrorMessage = () => {
    switch (error.code) {
      case "FILES_NOT_FOUND":
        return "Some required files were not uploaded. Please upload all files and try again.";
      case "BILLING_INSUFFICIENT_CREDITS":
        return "You don't have enough credits. Please purchase more credits to continue.";
      case "PROCESSING_ERROR":
        return "An error occurred during processing. Please try again.";
      default:
        return error.message || "An unexpected error occurred.";
    }
  };

  const canRetry = ["FILES_NOT_FOUND", "PROCESSING_ERROR"].includes(
    error.code || ""
  );
  const showPurchase = error.code === "BILLING_INSUFFICIENT_CREDITS";

  return (
    <div className="error-container">
      <AlertCircle className="error-icon" />
      <p>{getErrorMessage()}</p>
      <div className="error-actions">
        {canRetry && <button onClick={onRetry}>Retry</button>}
        {showPurchase && (
          <button onClick={() => router.push("/billing")}>
            Purchase Credits
          </button>
        )}
        <button onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}
```

---

## UI Components

### ResultWrapper2

A simplified component for viewing completed task analysis results. This component is used on the `/task/:taskId/results` route.

**Location:** `src/pages/results/ResultWrapper2.jsx`

**Features:**

- Fetches report data using `useGetTaskReport` hook
- Routes to the appropriate result component based on tool type
- Clean implementation without Redux complexity
- Loading and error states with animations

**Usage:**

```jsx
// In App.jsx routing
<Route path="/task/:taskId/results" element={<ResultWrapper2 />} />
```

**How it works:**

1. Extracts `taskId` from URL params
2. Calls `GET /tasks/{task_id}/report` API
3. Based on `tool` field, renders:
   - `ProfileMyDataResult` for profile-my-data
   - `CleanMyDataResult` for clean-my-data
   - `MasterMyDataResult` for master-my-data

**Accessing from TaskDetails:**
The TaskDetails page shows a "View Complete Analysis" button for completed tasks that navigates to this component.

---

### Progress Indicator

```typescript
// components/TaskProgress.tsx

interface TaskProgressProps {
  status: TaskStatus;
  progress: number;
  agents: string[];
}

export function TaskProgress({ status, progress, agents }: TaskProgressProps) {
  const getStatusLabel = () => {
    switch (status) {
      case "CREATED":
        return "Initializing...";
      case "UPLOADING":
        return "Uploading files...";
      case "PROCESSING":
        return "Processing...";
      case "COMPLETED":
        return "Complete!";
      case "FAILED":
        return "Failed";
      case "CANCELLED":
        return "Cancelled";
      default:
        return status;
    }
  };

  const completedAgents = agents.filter(
    (_, i) => i < Math.floor((progress / 100) * agents.length)
  );

  return (
    <div className="task-progress">
      <div className="progress-header">
        <span>{getStatusLabel()}</span>
        <span>{progress}%</span>
      </div>

      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>

      <div className="agents-list">
        {agents.map((agent, i) => (
          <div
            key={agent}
            className={`agent-item ${
              completedAgents.includes(agent) ? "completed" : "pending"
            }`}
          >
            {completedAgents.includes(agent) ? "✓" : "○"} {agent}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Download List

```typescript
// components/DownloadList.tsx

interface DownloadListProps {
  downloads: DownloadInfo[];
  onDownload: (download: DownloadInfo) => void;
  onDownloadAll: () => void;
}

export function DownloadList({
  downloads,
  onDownload,
  onDownloadAll,
}: DownloadListProps) {
  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getIcon = (type: FileType) => {
    switch (type) {
      case "report":
        return "📊";
      case "data":
        return "📄";
      default:
        return "📁";
    }
  };

  return (
    <div className="downloads-container">
      <div className="downloads-header">
        <h3>Downloads Ready</h3>
        <button onClick={onDownloadAll}>Download All</button>
      </div>

      <ul className="downloads-list">
        {downloads.map((download) => (
          <li key={download.download_id} className="download-item">
            <span className="download-icon">{getIcon(download.type)}</span>
            <div className="download-info">
              <span className="download-name">{download.filename}</span>
              <span className="download-size">
                {formatSize(download.size_bytes)}
              </span>
            </div>
            <button onClick={() => onDownload(download)}>Download</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

### File Upload with S3

```typescript
// components/S3FileUpload.tsx

interface S3FileUploadProps {
  uploadInfo: UploadUrlInfo;
  file: File;
  onProgress: (percent: number) => void;
  onComplete: () => void;
  onError: (error: Error) => void;
}

export function uploadFileToS3({
  uploadInfo,
  file,
  onProgress,
  onComplete,
  onError,
}: S3FileUploadProps) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        onProgress(percent);
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onComplete();
        resolve();
      } else {
        const error = new Error(`Upload failed: ${xhr.statusText}`);
        onError(error);
        reject(error);
      }
    });

    xhr.addEventListener("error", () => {
      const error = new Error("Upload failed");
      onError(error);
      reject(error);
    });

    xhr.open("PUT", uploadInfo.url);

    Object.entries(uploadInfo.headers).forEach(([key, value]) => {
      xhr.setRequestHeader(key, value);
    });

    xhr.send(file);
  });
}
```

---

## Code Examples

### Complete React Component

```typescript
// pages/AnalyzePage.tsx

import { useState } from "react";
import { useTaskOrchestrator } from "../hooks/useTaskOrchestrator";
import { TaskProgress } from "../components/TaskProgress";
import { DownloadList } from "../components/DownloadList";
import { TaskErrorHandler } from "../components/TaskErrorHandler";

export function AnalyzePage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedTool, setSelectedTool] = useState<ToolId>("profile-my-data");
  const [downloads, setDownloads] = useState<DownloadInfo[]>([]);

  const { token } = useAuth();

  const { runAnalysis, cancel, isLoading, status, progress, error } =
    useTaskOrchestrator(token, {
      onComplete: (downloads) => setDownloads(downloads),
      onProgress: (progress) => console.log(`Progress: ${progress}%`),
    });

  const handleSubmit = async () => {
    if (!selectedFile) return;

    try {
      await runAnalysis(
        selectedTool,
        { primary: selectedFile },
        undefined, // parameters (optional)
        undefined // agents (optional, uses all)
      );
    } catch (err) {
      console.error("Analysis failed:", err);
    }
  };

  const handleDownload = (download: DownloadInfo) => {
    window.open(download.url, "_blank");
  };

  const handleDownloadAll = () => {
    downloads.forEach(handleDownload);
  };

  return (
    <div className="analyze-page">
      <h1>Data Analysis</h1>

      {/* Tool Selection */}
      <select
        value={selectedTool}
        onChange={(e) => setSelectedTool(e.target.value as ToolId)}
        disabled={isLoading}
      >
        <option value="profile-my-data">Profile My Data</option>
        <option value="clean-my-data">Clean My Data</option>
        <option value="master-my-data">Master My Data</option>
      </select>

      {/* File Input */}
      <input
        type="file"
        accept=".csv,.xlsx,.xls"
        onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
        disabled={isLoading}
      />

      {/* Submit Button */}
      <button onClick={handleSubmit} disabled={!selectedFile || isLoading}>
        {isLoading ? "Processing..." : "Analyze"}
      </button>

      {/* Cancel Button */}
      {isLoading && status === "PROCESSING" && (
        <button onClick={cancel}>Cancel</button>
      )}

      {/* Progress */}
      {isLoading && status && (
        <TaskProgress
          status={status}
          progress={progress}
          agents={["unified-profiler", "score-risk"]}
        />
      )}

      {/* Error */}
      {error && (
        <TaskErrorHandler
          error={error}
          onRetry={handleSubmit}
          onCancel={() => {}}
        />
      )}

      {/* Downloads */}
      {downloads.length > 0 && (
        <DownloadList
          downloads={downloads}
          onDownload={handleDownload}
          onDownloadAll={handleDownloadAll}
        />
      )}
    </div>
  );
}
```

### Task History Page

```typescript
// pages/TaskHistoryPage.tsx

import { useEffect, useState } from "react";
import { TaskApi } from "../api/taskApi";

export function TaskHistoryPage() {
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [filter, setFilter] = useState<TaskStatus | "">("");

  const { token } = useAuth();
  const api = new TaskApi(token);

  useEffect(() => {
    loadTasks();
  }, [filter]);

  const loadTasks = async (offset = 0) => {
    const response = await api.listTasks({
      status: filter || undefined,
      limit: 20,
      offset,
    });
    setTasks(response.tasks);
    setPagination(response.pagination);
  };

  const handleDelete = async (taskId: string) => {
    if (confirm("Delete this task and all associated files?")) {
      await api.deleteTask(taskId);
      loadTasks();
    }
  };

  return (
    <div className="task-history">
      <h1>Task History</h1>

      {/* Filter */}
      <select
        value={filter}
        onChange={(e) => setFilter(e.target.value as TaskStatus)}
      >
        <option value="">All Statuses</option>
        <option value="COMPLETED">Completed</option>
        <option value="FAILED">Failed</option>
        <option value="PROCESSING">Processing</option>
      </select>

      {/* Task List */}
      <table>
        <thead>
          <tr>
            <th>Task ID</th>
            <th>Tool</th>
            <th>Status</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr key={task.task_id}>
              <td>{task.task_id.slice(0, 8)}...</td>
              <td>{task.tool_id}</td>
              <td>
                <span className={`status-badge ${task.status.toLowerCase()}`}>
                  {task.status}
                </span>
              </td>
              <td>{new Date(task.created_at).toLocaleString()}</td>
              <td>
                {task.status === "COMPLETED" && (
                  <button
                    onClick={() =>
                      router.push(`/tasks/${task.task_id}/downloads`)
                    }
                  >
                    Downloads
                  </button>
                )}
                <button onClick={() => handleDelete(task.task_id)}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Pagination */}
      {pagination && (
        <div className="pagination">
          <button
            disabled={pagination.offset === 0}
            onClick={() => loadTasks(pagination.offset - pagination.limit)}
          >
            Previous
          </button>
          <span>
            Showing {pagination.offset + 1}-
            {Math.min(pagination.offset + pagination.limit, pagination.total)}{" "}
            of {pagination.total}
          </span>
          <button
            disabled={!pagination.has_more}
            onClick={() => loadTasks(pagination.offset + pagination.limit)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
```

---

## Best Practices

### Performance

1. **Parallel uploads**: Upload multiple files in parallel
2. **Poll interval**: Use 3-5 second intervals during processing
3. **Caching**: Cache task list responses
4. **Lazy loading**: Load downloads only when needed

### User Experience

1. **Show progress**: Display percentage during processing
2. **Enable cancellation**: Allow users to cancel long-running tasks
3. **Handle expiry**: Re-fetch download URLs if expired
4. **Offline support**: Queue tasks when offline, submit when online

### Error Recovery

1. **Retry logic**: Implement exponential backoff for retries
2. **Partial uploads**: Track uploaded files to resume on failure
3. **Session persistence**: Store task_id to recover after page refresh
4. **Clear errors**: Show actionable error messages

### Security

1. **Token refresh**: Refresh auth token before it expires
2. **URL expiry**: Don't store presigned URLs long-term
3. **Validate files**: Check file type/size before upload
4. **Sanitize inputs**: Validate parameters before sending

---

## Appendix

### Available Agents by Tool

#### profile-my-data

- `unified-profiler` - Data profiling and statistics
- `score-risk` - Risk scoring
- `drift-detector` - Drift detection (requires baseline file)
- `readiness-rater` - Data readiness assessment
- `governance-checker` - Governance compliance
- `test-coverage` - Test coverage analysis

#### clean-my-data

- `null-handler` - Handle null/missing values
- `outlier-remover` - Remove outliers
- `type-fixer` - Fix data types
- `duplicate-resolver` - Resolve duplicates
- `field-standardization` - Standardize fields
- `quarantine-agent` - Quarantine bad records
- `cleanse-previewer` - Preview changes
- `cleanse-writeback` - Write cleaned data

#### master-my-data

- `key-identifier` - Identify keys
- `contract-enforcer` - Enforce contracts
- `semantic-mapper` - Map semantics
- `lineage-tracer` - Trace lineage
- `golden-record-builder` - Build golden records
- `survivorship-resolver` - Resolve survivorship
- `master-writeback` - Write master data
- `stewardship-flagger` - Flag for stewardship

### HTTP Status Codes

| Code | Meaning                                 |
| ---- | --------------------------------------- |
| 200  | Success                                 |
| 201  | Created (task creation)                 |
| 400  | Bad Request (validation error)          |
| 401  | Unauthorized (invalid token)            |
| 402  | Payment Required (insufficient credits) |
| 404  | Not Found (task doesn't exist)          |
| 500  | Internal Server Error                   |

### Supported File Types

| Extension | MIME Type                                                         | Use Case            |
| --------- | ----------------------------------------------------------------- | ------------------- |
| .csv      | text/csv                                                          | Primary data format |
| .xlsx     | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | Excel files         |
| .xls      | application/vnd.ms-excel                                          | Legacy Excel        |
| .json     | application/json                                                  | Parameters          |
