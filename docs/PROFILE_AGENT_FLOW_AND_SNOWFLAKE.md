# Profile-my-data: end-to-end flow + Snowflake integration

This document describes the runtime flow for the "profile-my-data" path in the Agensium backend (API → agent → transformer → downloads) using the `unified_profiler` agent as an example, plus concrete recommendations and code snippets for using Snowflake for structured results and artifact metadata.

Quick overview

- Entry point: POST /analyze (backend/api/routes.py)
- Agent: `agents/unified_profiler.py::profile_data()` — CSV in memory → Polars profiling → structured JSON report
- Transformer: `transformers/profile_my_data_transformer.py::transform_profile_my_data_response()` — aggregates agent outputs, AI analysis, routing, builds downloads
- Downloads: `downloads/profile_my_data_downloads.py` + `downloads/downloads_utils.py` — Excel and JSON report generation (in-memory, base64 encoded)

Why this doc

- The codebase currently does in-memory processing and returns large base64 encoded report artifacts.
- For scale, durability, and analytics we recommend persisting analysis metadata and JSON reports to Snowflake while keeping large binaries in object storage (S3/Blob).

Runtime flow (detailed)

1. API receives files and parameters (POST /analyze).

   - `routes.analyze()` validates, converts non-CSV to CSV (Excel / JSON → CSV), reads files into `files_map` as bytes.

2. Sequence of agents executed (by `execute_agent_flexible()`):

   - Each agent takes primary file bytes + optional baseline and parameters.
   - `unified_profiler.profile_data()` reads CSV bytes using Polars, performs profiling (field-level statistics, alerts, row-level issues capped at 1000), returns a rich JSON report.

3. Transformer consolidation

   - `profile_my_data_transformer` aggregates all agent outputs, builds executive summary, requests AI summary (AnalysisSummaryAI) and routing decisions.
   - Transformer collects alerts, issues, recommendations, and prepares `downloads` by invoking `ProfileMyDataDownloads.generate_downloads()`.

4. Downloads
   - `ProfileMyDataDownloads` creates an Excel workbook (multiple sheets) and a JSON report; both are serialised to bytes and base64-encoded before being included in the API response.

Key constraints & risks

- Large in-memory structures for big files → risk of OOM / large response payloads.
- Binary artifacts are embedded (base64) instead of stored externally which increases latency and size of responses.
- Long-running processing should be moved to background workers (see V2_ARCHITECTURE_PLAN.md) and results persisted.

Snowflake integration patterns (recommended)

1. Store raw/large files: use S3 or Azure Blob.

   - Keep raw file bytes and large download artifacts in object storage.
   - Snowflake external stage can reference these objects for ingestion.

2. Persist structured results & metadata into Snowflake (primary use-case)

   - Use VARIANT for JSON reports and standard columns for metadata (analysis_id, tool, timestamps, primary_file_path, execution_time_ms, status).
   - Benefits: SQL queries over historical analyses, dashboarding, cross-analysis reporting, and cheaper storage compared to embedding in responses.

3. Persist generated downloads (metadata only) in Snowflake
   - Save S3 path, file name, format, size and creation date in a `downloads` table. UI can later fetch the artifact via S3 URL.

Suggested Snowflake table designs

analysis_metadata

- analysis_id STRING PRIMARY KEY
- tool STRING
- user_id STRING
- timestamp TIMESTAMP_LTZ
- execution_time_ms INTEGER
- primary_file_path STRING
- baseline_file_path STRING
- status STRING

analysis_reports

- analysis_id STRING
- tool STRING
- report VARIANT
- created_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP

downloads

- download_id STRING
- analysis_id STRING
- file_name STRING
- s3_path STRING
- format STRING
- size_bytes INTEGER
- created_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP

Where to write: worker vs API

- Prefer writing to Snowflake from the background worker (worker task does the heavy lifting):
  1. Worker downloads the raw file from S3 (or reads the uploaded bytes if small)
  2. Worker runs the agent logic
  3. Worker writes the JSON report to `analysis_reports` (PARSE_JSON into VARIANT) and metadata to `analysis_metadata`
  4. Worker uploads generated downloads to S3 and writes rows to `downloads` table with S3 paths

Python integration pattern

1. Add a new service: `services/snowflake_storage.py` (uses snowflake-connector-python)
2. Use it from worker tasks or route handlers when appropriate (worker preferred)

Example (conceptual):

```python
from snowflake import connector
import json, os

def get_sf_conn():
    return connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        private_key=os.getenv("SNOWFLAKE_PRIVATE_KEY"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        role=os.getenv("SNOWFLAKE_ROLE")
    )

def save_report(analysis_id, tool, report_json):
    conn = get_sf_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO analysis_reports (analysis_id, tool, report) VALUES (%s, %s, PARSE_JSON(%s))",
            (analysis_id, tool, json.dumps(report_json))
        )
    finally:
        cur.close(); conn.close()
```

Operational & security notes

- Use key-pair or OAuth for Snowflake auth; never check secrets into repo. Use a secrets store (Vault, AWS Secrets Manager, or environment via CI/CD).
- Use separate warehouses for ingestion and analytics to control costs.
- Compress or chunk very large JSON or avoid storing large binary content in Snowflake; keep binaries in S3 and record their path in Snowflake.
- Use Snowpipe or COPY INTO for automatic ingestion when datasets should be imported into tables for analysis.

Next steps (implementation options I can help with)

- Create `services/snowflake_storage.py` and integration tests, and add dependency to `requirements.txt`.
- Update a worker task (Celery) to persist reports and upload downloads to S3 then write metadata to Snowflake.
- Replace base64 payloads in transformer/downloads with S3 URLs and add a small signed-url helper for secure downloads.

If you want, I can implement one of the above next — which would you prefer?
