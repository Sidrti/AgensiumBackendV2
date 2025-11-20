# System Architecture

## Overview

Agensium Backend V2 is a modular, FastAPI-based platform for data analysis and mastering. It uses a "Tool" and "Agent" architecture to provide extensible data processing capabilities.

## Core Components

### 1. Tools (`tools/*.json`)

High-level capabilities defined in JSON. A Tool is a collection of Agents.

- **Profile My Data**: For understanding data (profiling, drift, risk).
- **Clean My Data**: For fixing data (cleaning, standardization, deduplication).

### 2. Agents (`agents/*.py`)

Independent processing units that perform specific tasks.

- **Input**: Dataframes/Files + Parameters.
- **Output**: JSON Result + Optional Cleaned File.
- **Examples**: `unified-profiler`, `null-handler`, `drift-detector`.

### 3. Transformers (`transformers/*.py`)

Aggregators that take raw Agent results and transform them into a unified frontend-friendly response format (Alerts, Issues, Recommendations, Visualizations).

### 4. AI Engine (`ai/*.py`)

- **RoutingDecisionAI**: Analyzes results to recommend the next best tool.
- **ChatAgent**: RAG-based system for answering user questions about analysis reports.

## Data Flow

1.  **Request**: User POSTs to `/analyze` with file(s) and `tool_id`.
2.  **Validation**: API validates files against Tool definition.
3.  **Execution**:
    - Files are converted to CSV/DataFrame.
    - Selected Agents are executed in sequence.
    - For `clean-my-data`, the output of one agent (cleaned file) can be passed to the next.
4.  **Transformation**: Agent results are aggregated by the Tool's Transformer.
5.  **Response**: Unified JSON response returned to client.

## Directory Structure

- `api/`: FastAPI routes and dependencies.
- `agents/`: Individual agent logic.
- `tools/`: JSON definitions of Tools.
- `transformers/`: Response formatting logic.
- `ai/`: AI and LLM integration.
- `db/`: Database models (SQLAlchemy).
- `auth/`: Authentication logic.
