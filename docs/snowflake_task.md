# Upload artifacts during download generation — Persist final transformer output to MySQL

## Summary

When downloads are produced (Excel, CSV, JSON) upload them directly to S3 and replace large in-memory base64 payloads with compact metadata. Persist the final analysis object (report + download metadata) in MySQL for auditing, queryability and idempotent re-processing. This file is a short, actionable plan (no implementation code).

## Goal

Reduce memory and HTTP payload sizes, make artifacts available quickly, and persist structured analysis output in MySQL.

- Upload artifacts as they are created so API responses don't carry base64 blobs.
- Store canonical artifact locations (S3) and short-lived presigned URLs for immediate access.
- Persist the final transformer return object in MySQL (JSON column + normalized per-artifact rows) using idempotent upserts.

## What to do (concise)

- Upload each artifact from its respective downloads module as it’s produced (Excel, JSON, cleaned CSV).
- Each download function should accept upload_to_s3 (default False) so tests and synchronous API flows can skip S3 uploads.

- When upload_to_s3=True, immediately upload bytes/base64 payload to S3 and replace content_base64 in the in-memory return object with metadata: download_id, file_name, format, size_bytes, s3_path and (optionally) presigned_url.

Key format for S3 objects

Use a predictable key layout to make artifacts discoverable and auditable:

{env}/{tool}/{analysis*id}/{timestamp}*{sanitized_file_name}

- Sanitize names, enforce lower-case, and append download_id or UUID when needed to avoid collisions.

Upload behavior

- downloads generators accept upload_to_s3: bool = False (default to preserve current behavior).
- If upload_to_s3=True the module uploads bytes/base64 to S3 as produced, returns compact metadata (download_id, file_name, format, size_bytes, s3_path, presigned_url, status), and drops content_base64 from in-memory result.

Persisting the final object

When the transformer constructs the final return object (with downloads converted to S3 metadata), persist it in MySQL. Rules:

- Persist after successful uploads — or after exhaustively retrying and marking failures — so DB references remain correct.
- Use idempotent upserts (INSERT ... ON DUPLICATE KEY UPDATE or SQLAlchemy merge) keyed on analysis_id and download_id.
- Wrap the report and downloads writes in one DB transaction when possible to avoid dangling metadata.

- update `requirements.txt` if 3rd-party libs are needed (boto3, mysqlclient or pymysql, localstack/minio clients for tests)

Why this is better

Benefits:

- Smaller API responses and lower memory use (no base64 blobs in responses).
- Immediate availability of artifacts using presigned URLs.
- Immutable canonical artifacts in S3 for reproducibility and audit.
- Queryable and auditable structured metadata stored in MySQL (JSON + normalized rows).

## Download metadata example

When an artifact is uploaded the download entry should be normalized to:

{
"download_id": "<uuid>",
"file_name": "cleaned_sample.csv",
"format": "csv",
"size_bytes": 12345,
"s3_path": "s3://bucket/prod/clean-my-data/abcd1234/2025-11-29_cleaned_sample.csv",
"presigned_url": "https://..." (optional),
"status": "uploaded" | "upload_failed"
}

## Recommended MySQL schema (SQLAlchemy / MySQL JSON)

Schema (MySQL, SQLAlchemy)

Persist the full final object in a JSON column and keep per-artifact rows in a `downloads` table for efficient queries.

analysis_reports

- id INT PK AUTO_INCREMENT
- analysis_id VARCHAR(128) UNIQUE NOT NULL
- tool VARCHAR(64)
- status VARCHAR(32)
- timestamp DATETIME
- execution_time_ms INT
- report JSON -- full final object (alerts, issues, downloads, agent outputs)
- created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP

downloads

- download_id VARCHAR(36) PRIMARY KEY
- analysis_id VARCHAR(128) NOT NULL (FK -> analysis_reports.analysis_id)
- file_name VARCHAR(255)
- format VARCHAR(32)
- size_bytes BIGINT
- s3_path VARCHAR(1024)
- presigned_url TEXT NULL
- status VARCHAR(32)
- created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Notes:

- Use INSERT ... ON DUPLICATE KEY UPDATE or SQLAlchemy session.merge() for idempotent writes.
- Wrap analytics_report + downloads in a DB transaction to avoid partially-persisted states.
- Consider keeping very large JSONs in S3 and storing a trimmed summary in MySQL if size becomes an issue.

## Implementation notes for the final object

Store the final transformer return object in `analysis_reports.report` as JSON, e.g.:
{
"analysis_id": "...",
"tool": "clean-my-data",
"status": "success",
"timestamp": "2025-11-29T12:34:56Z",
"execution_time_ms": 12345,
"report": {
"alerts": [...],
"issues": [...],
"recommendations": [...],
"executiveSummary": "...",
"analysisSummary": {...},
"rowLevelIssues": [...],
"issueSummary": {...},
"routing_decisions": {...},
"downloads": [...],
...agent_outputs
}
}
Edge cases & recommendations

- Worker vs synchronous API: perform heavy uploads in workers to avoid blocking HTTP requests; allow on-the-fly uploads from workers/tests.
- If S3 upload fails repeatedly: mark download.status="upload_failed" and persist that; or keep content_base64 for very small files until re-upload (less ideal).
- JSON reports: store canonical JSON in S3 and a copy/summary in MySQL if you need VARIANT-style querying.
- Retry/backoff: configurable retries + exponential backoff for uploads, with error/status persisted for later re-processing.
- Security: restrictive S3 ACLs, least-privilege credentials, short presigned URL TTLs, and sanitized key components.
- Monitoring: track upload latency and failures — surface metrics for retries and alerts.

## Edge cases & recommendations

- Worker vs synchronous API: Prefer performing S3 uploads in worker processes for heavy/long-running jobs to avoid blocking web requests. Still support on-the-fly uploads in downloads modules for worker sketches or tests.
- If S3 upload fails after retries, choose a consistent failure mode:
  - Option A: Mark the download metadata with status=upload_failed and persist the report with that flag set so consumers can detect missing artifacts.
  - Option B: Temporarily keep content_base64 for small-ish files until upload succeeds — this is not recommended for large files due to memory cost.
- For JSON reports: consider hybrid storage — write canonical JSON to S3 (complete artifact) and optionally persist the report as VARIANT in Snowflake for queryability; keep S3 path in Snowflake as the canonical artifact location.
- Retry & backoff: implement configurable retries + exponential backoff for uploads. If a complete failure occurs, persist metadata with status and error messages (for later re-processing).
- Security: store files with restrictive S3 ACLs and prefer presigned URLs for temporary client access. Sanitize all filename components used in S3 keys.
- Monitoring & telemetry: track upload durations, failures and presigned URL generation; alert on repeated failures.

## Testing

- Unit tests: mock S3 + MySQL to check upload_to_s3 toggle, content_base64 replacement, retries, and idempotent DB writes.
- Integration tests: minio + local/dev MySQL instance for end-to-end verification.

## Next steps (minimal implementation plan)

1. Add an S3 service helper: `services/s3_storage.py`

   - helpers: upload_bytes, generate_presigned_url, delete, key generation
   - config: env-based prefix, retries, timeouts

Next steps (minimal implementation plan)

1. S3 helper: `services/s3_storage.py`

   - upload_bytes, generate_presigned_url, delete
   - deterministic key generation, configurable retries, presigned URL TTLs

2. MySQL helper: `services/mysql_storage.py`
   - persist_analysis_report(report_obj), per-download upserts, idempotent merges and transactions

3) Modify download modules (`downloads/*_downloads.py`)

   - add parameter upload_to_s3:bool = False
   - when True: upload files as produced and replace content_base64 with S3 metadata

4) Modify transformers

   - after final object is constructed (with downloads metadata), call Snowflake service persist_analysis_report(report)
   - persist only after successful uploads or after marking statuses for failed uploads

5. Tests & CI
   - unit tests with mocked S3 and MySQL
   - integration tests using minio + dev MySQL
   - update `requirements.txt` (boto3, mysqlclient/pymysql, localstack or minio for tests)

## Minimal API / format expectations

When upload_to_s3=True, downloads in the final report should contain small metadata (not base64):

- download_id: UUID
- file_name
- format: xlsx|csv|json
- size_bytes
- s3_path
- presigned_url (optional, ephemeral)
- status: uploaded|upload_failed

Current TODOs

- add s3 service — not-started
- add mysql service — not-started
- modify downloads modules — not-started
- modify transformers — not-started
- add tests — not-started

## Notes

- Keep the same public API shape for consumers: only replace in-memory base64 payloads with small metadata objects when upload_to_s3=True; when False keep existing behavior for compatibility.
- Make DB writes idempotent so retry loops or repeated persisting from different workers won't produce duplicates.

If you'd like I can start implementing item 1 (S3 service) next — which would you prefer I start with?
