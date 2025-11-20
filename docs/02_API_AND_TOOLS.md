# API & Tools Reference

## API Endpoints

### General

- `GET /`: Service info.
- `GET /health`: Health check.

### Tools

- `GET /tools`: List all available tools.
- `GET /tools/{tool_id}`: Get detailed definition of a specific tool (agents, file requirements).

### Analysis

- `POST /analyze`: Main entry point for processing data.
  - **Form Data**:
    - `tool_id`: (Required) e.g., `profile-my-data`, `clean-my-data`.
    - `primary`: (Required) Main data file (CSV, Excel, JSON).
    - `baseline`: (Optional) Reference file for drift detection.
    - `agents`: (Optional) Comma-separated list of agent IDs to run.
    - `parameters_json`: (Optional) JSON string for agent configuration.

### Chat

- `POST /chat`: Ask questions about an analysis report.
  - **Form Data**:
    - `question`: User's question.
    - `report_json`: The full JSON response from `/analyze`.
    - `conversation_history_json`: Previous chat messages.

## Available Tools

### 1. Profile My Data (`profile-my-data`)

**Purpose**: Comprehensive data profiling, quality assessment, and risk evaluation.
**Key Features**:

- Statistical profiling.
- Drift detection (requires baseline file).
- PII and Risk scoring.
- Readiness rating for production.

### 2. Clean My Data (`clean-my-data`)

**Purpose**: Data cleaning, validation, and standardization.
**Key Features**:

- Null value handling.
- Outlier removal.
- Type fixing.
- Duplicate resolution.
- Field standardization.
- "What-if" preview of cleaning operations.
