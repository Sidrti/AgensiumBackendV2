# Agensium V2.1 Architecture & Roadmap

**Document Version:** 2.1.1  
**Created:** December 20, 2025  
**Purpose:** Single-pane overview that merges the current state analysis, the V2.1 architecture plan, and the step-by-step implementation roadmap into one cohesive, actionable reference.

---

## Executive Summary

Agensium V2 was built as a synchronous FastAPI application that received files directly, processed them in memory, executed a chain of agents, and returned all results in one giant JSON response. This approach worked for small-scale usage but created long response times (10–60+ seconds), memory pressure with large uploads, no persistence, and opaque user experience around progress, retries, and downloads.

V2.1 flips the script: uploads go directly to Backblaze B2, parameters stream from the same storage, execution is broken into explicit tasks, status is tracked, and outputs live entirely in S3 with presigned download links. The result is a resilient, auditable workflow built for scale, with a clean migration path to queue-backed workers.

## What We Are Solving

| Pain Point                                              | V2.1 Target                                                                     |
| ------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Blocking `/analyze` that does everything in one request | Decouple creation, upload, processing, and download into task lifecycle stages  |
| In-memory file pounding (100MB = 500MB+ real usage)     | Stream from Backblaze B2; inputs stay in S3 and never live fully in RAM         |
| Massive base64 responses                                | Outputs stay in S3, responses contain URLs (no base64 blobs)                    |
| No history/no retry                                     | Task records persist, status is queryable, failed or expired states can restart |
| No progress or download tracking                        | Task status, progress percentage, and downloads are explicit REST resources     |

## High-Level Architecture

```
Frontend        Backend             Storage (B2 S3-compatible)
   │               │                        │
   │ POST /tasks   │                        │
   │──────────────►│ Create Task record     │
   │               │                        │
   │ request URLs  │                        │
   │──────────────►│ Generate presigned URLs│
   │               │                        │
   │ Upload files  │                        │
   │───(PUT to B2)─►│                        │
   │ Upload params │                        │
   │──────────────►│                        │
   │ trigger proc. │                        │
   │──────────────►│ Verify files, run agents │
   │               │                        │
   │ Poll /tasks   │◄────────────────────────┘
```

V1 (current) accepts everything in `POST /analyze` and sticks all data and results into a single response. V2.1 replaces that call with a task lifecycle. The remaining documentation (see Companion doc “Task Lifecycle + API + Schema”) covers the precise task states, error codes, API contracts, and schema.

## Key V2.1 Goals

1. Decouple uploads, parameters, and processing so users don’t wait on backend resources.
2. Persist metadata and status in a simplified `tasks` table (no redundant file metadata).
3. Store every artifact in Backblaze B2, using presigned URLs to upload/download.
4. Provide clear lifecycle visibility: CREATED → UPLOADING → QUEUED → PROCESSING → terminal states.
5. Lay the groundwork for future queue-based (Celery/Redis) workers by keeping processing logic agnostic to invocation context.

## System Flow: From Task to Output

1. **Create Task (`POST /tasks`)**: Accept tool ID + optional agent list → return `task_id`, status `CREATED`. No files or parameters yet.
2. **Request Upload URLs (`POST /tasks/{id}/upload-urls`)**: Provide metadata for each expected file plus `has_parameters`. Backend returns presigned PUT URLs for each input plus `parameters.json`. Task status transitions to `UPLOADING` and records `upload_started_at`.
3. **Upload Files + Parameters**: Frontend PUTs files + parameters directly to B2 using the presigned URLs. Files live under `users/{user_id}/tasks/{task_id}/inputs/`.
4. **Trigger Processing (`POST /tasks/{id}/process`)**: Backend verifies inputs, marks task `QUEUED` (immediately `PROCESSING` in current sync model), loads inputs + parameters from B2, executes agent chain, and uploads outputs/manifest to `users/{user_id}/tasks/{task_id}/outputs/`. Task transitions through PROCESSING → COMPLETED/FAILED/other terminal state.
5. **Poll Status & Downloads (`GET /tasks/{id}`, `/downloads`)**: Frontend monitors progress, sees the current agent, and finally fetches download links for Excel/JSON/cleaned files; all live in S3.

## Component Design & Responsibilities

### Services Layer

- `services/s3_service.py`: Singleton encapsulating Backblaze B2 (S3-compatible) access. Key methods:
  - `generate_upload_url` / `generate_parameter_upload_url`: Presigned PUT URLs with Content-Type enforcement.
  - `generate_download_url`: Presigned GET URLs for outputs.
  - `file_exists`, `list_files`, `list_output_files`: Support verification/manifesting.
  - `get_parameters`, `get_file_bytes`: Reading inputs for transformers.
  - `upload_file`, `delete_folder`: Output persistence + cleanup.
  - `delete_folder` used by cleanup jobs once retention windows expire.
- `services/__init__.py`: Exports `s3_service` singleton for reuse.

### Task Infrastructure

- `Task` model (see companion doc) holds minimal tracking fields: `task_id`, `user_id`, `tool_id`, `agents`, `status`, timing fields, `progress`, `current_agent`, and cleanup flag.
- No `parameters` or file metadata in DB; all derived from S3 prefixes (`users/{user_id}/tasks/{task_id}/inputs` and `/outputs`). The B2 key structure is deterministic, so ownership and task identity are implicit.

### Transformers & Downloads

- Each transformer (profile/clean/master) now has a `run_*_analysis_v2_1` variant that:
  1. Lists input files from S3.
  2. Reads bytes (skipping `parameters.json`), converts to CSV if needed.
  3. Loads parameters via `s3_service.get_parameters`.
  4. Executes agents with billing context updates (credit checks happen before agent execution).
  5. Uploads outputs that previously were returned base64 to `outputs/` via `s3_service.upload_file` and records downloads for the `GET /downloads` endpoint.
- `downloads` modules continue to describe the types of artifacts (reports, data exports), but the presigned URLs now stream directly from S3.

### Billing

- Billing remains unchanged: `BillingContext` debits credits before each agent runs. If insufficient, processing ends early with `FAILED` and a descriptive error code.

### Backblaze B2 Layout & Credentials

```
s3://agensium-files/
└── users/{user_id}/
    └── tasks/{task_id}/
        ├── inputs/
        │   ├── primary.csv
        │   ├── baseline.csv (optional)
        │   └── parameters.json
        └── outputs/
            ├── data_profile_report.xlsx
            ├── data_profile_report.json
            └── cleaned_data.csv
```

**Env variables (already in `.env`):**

```
AWS_ACCESS_KEY_ID=005fb2e3bbdac0d0000000002
AWS_SECRET_ACCESS_KEY=K005zAnnw2vCoHK0jhT++tLScYAxjRE
AWS_ENDPOINT_URL=https://s3.us-east-005.backblazeb2.com
AWS_REGION=us-east-005
S3_BUCKET=agensium-files
```

## Migration & Implementation Plan

| Phase                      | Focus                  | Key Deliverables                                                              |
| -------------------------- | ---------------------- | ----------------------------------------------------------------------------- |
| **1: Infrastructure**      | Task table + S3 client | `tasks` table, `services/s3_service.py`, singleton export, B2 creds validated |
| **2: Task API**            | CRUD + lifecycle       | `api/task_routes.py`, integrate router in `main.py`                           |
| **3: Transformers**        | Read/Write S3          | V2.1 variants of transformers, read parameters from B2, upload outputs        |
| **4: Downloads & Results** | Serve URLs             | Outputs stay in S3, downloads endpoint returns presigned links                |
| **5: Testing & Migration** | QA + rollout           | Unit/integration/load tests, cleanup jobs, Deprecate `/analyze` gradually     |

### Timeline Estimate

- Phase 1: 2-3 days
- Phase 2: 2-3 days
- Phase 3: 2-3 days
- Phase 4: 1-2 days
- Phase 5: 2-3 days

**Total:** ~10–14 days. Simplified model and clear service boundaries make it faster than the original V2 efforts.

### Testing & Migration Checklist

**Unit tests:** S3 service, task creation, upload URLs, status transitions.  
**Integration tests:** Full end-to-end flow (create → upload inputs + params → trigger → download).  
**Load tests:** 10 concurrent tasks, 100MB files, large `parameters.json`.  
**Migration Steps:**

1. Backup database.
2. Run migration (Alembic or manual SQL from companion doc).
3. Deploy new code; verify new endpoints.
4. Test migration flow with parameter uploads to B2.
5. Monitor metrics post-deploy (error rates, B2 storage, billing events).

## Benefits & Future Path

| Audience       | Benefit                                                                              |
| -------------- | ------------------------------------------------------------------------------------ |
| **Users**      | Immediate responses, persistence, progress, resumable uploads, fast downloads via B2 |
| **System**     | Lower memory pressure, simplified schema, S3 as single source of truth               |
| **Developers** | Clear separation of concerns, easier mocks/stubs, queue-ready architecture           |

**Future queue-ready path (V2.1.1):** The task model lets you replace the synchronous `_execute_task` entry point with a Celery worker that picks up the same `task_id`, so shifting from blocking to asynchronous only requires wrapping the processing block in a background job without touching storage or schema.

## Next Steps

1. Finish companion doc with lifecycle, API contracts, and schema details.
2. Implement cleanup jobs to expire stale tasks and delete B2 artifacts (see lifecycle doc for thresholds).
3. Deprecate `/analyze` once the new workflow is verified and widely adopted.

> For detailed lifecycle states, endpoint specs, request/response schemas, error codes, and the full simplified `Task` model, see **Task Lifecycle + API + Schema** (the second consolidated document).
