# Agensium Backend V2

**Agensium Backend V2** is a modular, agent-based platform for comprehensive data analysis, cleaning, and mastering. It provides a unified API to profile data quality, detect risks, and automatically clean datasets using specialized agents.

## 🚀 Key Features

- **Tool-Based Architecture**: Extensible system where capabilities are grouped into "Tools" (e.g., _Profile My Data_, _Clean My Data_).
- **Specialized Agents**: Modular units of work that perform specific tasks like null handling, drift detection, PII scanning, and outlier removal.
- **AI Integration**:
  - **Routing AI**: Intelligently recommends the next best tool/agent based on analysis results.
  - **Chat Agent**: RAG-based system allowing users to ask natural language questions about their data reports.
- **Flexible File Handling**: Supports CSV, Excel, and JSON formats with automatic conversion.
- **Comprehensive Reporting**: Generates detailed JSON reports including alerts, field-level issues, recommendations, and visualizations.

## 🛠️ Tools & Agents

### 📊 Profile My Data

_Comprehensive data profiling and risk assessment._

- **Unified Profiler**: Statistics, quality scores, distribution analysis.
- **Drift Detector**: Detects statistical drift against a baseline.
- **Risk Scorer**: Identifies PII and compliance risks.
- **Readiness Rater**: Evaluates production readiness.
- **Governance Checker**: Validates lineage and consent.
- **Test Coverage Agent**: Checks validation rule coverage.

### 🧹 Clean My Data

_Data cleaning, validation, and standardization._

- **Cleanse Previewer**: "What-if" simulation of cleaning impact.
- **Quarantine Agent**: Isolates invalid records.
- **Null Handler**: Smart imputation or removal of missing values.
- **Outlier Remover**: Statistical outlier detection and handling.
- **Type Fixer**: Fixes data type inconsistencies.
- **Duplicate Resolver**: Merges or removes duplicates.
- **Field Standardization**: Normalizes formats (case, whitespace).
- **Cleanse Writeback**: Finalizes and exports cleaned data.

## 💻 Quick Start

### Prerequisites

- Python 3.9+
- `pip`

### Installation

1.  **Clone the repository**
2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure Environment**:
    Create a `.env` file in the root directory:
    ```env
    OPENAI_API_KEY=your_key_here  # Required for AI features
    FRONTEND_URL=http://localhost:5173
    PORT=8000
    ```

### Running the Server

```bash
# Using Python directly
python main.py

# Or using Uvicorn (for development with reload)
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.
Interactive API docs: `http://localhost:8000/docs`.

## 📚 Documentation

Detailed documentation is available in the `docs/` directory:

1.  [**Architecture**](docs/01_ARCHITECTURE.md) - System design and data flow.
2.  [**API & Tools**](docs/02_API_AND_TOOLS.md) - API endpoints and tool definitions.
3.  [**Agents**](docs/03_AGENTS.md) - Detailed descriptions of all agents.

## 🔌 API Usage Example

**Analyze a file with Profile My Data:**

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "tool_id=profile-my-data" \
  -F "primary=@./data.csv"
```

**Chat with your report:**

```bash
curl -X POST "http://localhost:8000/chat" \
  -F "question=What are the main quality issues?" \
  -F "report_json={...json_response_from_analyze...}"
```

## 🏗️ Project Structure

```
AgensiumBackendV2/
├── main.py              # App entry point & tool loader
├── api/                 # API routes
├── agents/              # Agent implementations
├── tools/               # JSON tool definitions
├── transformers/        # Response formatters
├── ai/                  # AI/LLM logic
├── docs/                # Documentation
└── requirements.txt     # Dependencies
```
