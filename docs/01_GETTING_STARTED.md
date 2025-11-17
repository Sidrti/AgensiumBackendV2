# Agensium Backend - Getting Started Guide

## Quick Start

### Prerequisites

- Python 3.8+
- pip package manager
- Virtual environment (recommended)

### Installation & Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server
python main.py
# Or use: python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Server will be available at http://localhost:8000
# Interactive API docs at http://localhost:8000/docs
# Alternative docs at http://localhost:8000/redoc
```

---

## Project Structure

```
backend/
├── agents/                    # Individual agent modules
│   ├── __init__.py
│   ├── unified_profiler.py   # Data profiling agent
│   ├── drift_detector.py     # Dataset drift detection
│   ├── score_risk.py         # PII & risk assessment
│   ├── readiness_rater.py    # Data readiness evaluation
│   ├── null_handler.py       # Missing value handling
│   ├── outlier_remover.py    # Outlier detection & removal
│   ├── type_fixer.py         # Type inconsistency fixing
│   ├── governance_checker.py # Governance compliance
│   └── test_coverage_agent.py # Test coverage validation
│
├── api/                       # API routes and endpoints
│   ├── __init__.py
│   ├── routes.py             # All API endpoints
│   └── dependencies.py       # API utilities
│
├── ai/                        # AI decision engines
│   ├── __init__.py
│   ├── analysis_summary_ai.py # OpenAI-based summaries
│   └── routing_decision_ai.py # Intelligent tool routing
│
├── transformers/             # Result aggregators
│   ├── __init__.py
│   ├── profile_my_data_transformer.py  # Profile tool aggregator
│   └── clean_my_data_transformer.py    # Clean tool aggregator
│
├── tools/                     # Tool definitions
│   ├── profile_my_data_tool.json       # Profile tool spec
│   └── clean_my_data_tool.json         # Clean tool spec
│
├── docs/                      # Documentation (this folder)
│   ├── 01_GETTING_STARTED.md           # This file
│   ├── 02_ARCHITECTURE.md              # System architecture
│   ├── 03_TOOLS_OVERVIEW.md            # Tools & agents
│   ├── 04_API_REFERENCE.md             # API endpoints
│   ├── 05_AGENT_DEVELOPMENT.md         # Creating agents
│   └── 06_DEPLOYMENT.md                # Deployment guide
│
├── main.py                   # FastAPI application entry point
├── requirements.txt          # Python dependencies
└── README.md                 # Project overview
```

---

## Key Concepts

### Tools

A **Tool** is a high-level analysis capability that orchestrates multiple agents. Currently available:

- **profile-my-data**: Comprehensive data profiling and analysis
- **clean-my-data**: Data cleaning and quality improvement

### Agents

An **Agent** is a specialized module that performs a specific analysis task. Each tool consists of multiple agents that can run independently or together.

### Transformers

A **Transformer** aggregates results from multiple agents and creates a unified response with alerts, issues, recommendations, and executive summaries.

### AI Routing

The **Routing Decision AI** analyzes current analysis results and intelligently recommends the next best tool to run for maximum data understanding.

---

## Available Tools

### 1. Profile My Data

Comprehensive data profiling, quality assessment, drift detection, risk scoring, and readiness evaluation.

**Agents:**

- `unified-profiler`: Statistical analysis and quality metrics
- `drift-detector`: Compare datasets for distribution changes
- `score-risk`: PII detection and compliance risk assessment
- `readiness-rater`: Data readiness evaluation
- `governance-checker`: Governance compliance validation
- `test-coverage-agent`: Test coverage assessment

**Use Cases:**

- First-time data exploration
- Data quality baseline establishment
- Dataset comparison and drift detection
- Risk and compliance assessment
- Production readiness evaluation

### 2. Clean My Data

Data cleaning and validation with null handling, outlier removal, type fixing, governance validation, and test coverage.

**Agents:**

- `null-handler`: Missing value detection and imputation
- `outlier-remover`: Outlier detection and handling
- `type-fixer`: Data type inconsistency fixing
- `governance-checker`: Governance compliance validation
- `test-coverage-agent`: Test coverage assessment

**Use Cases:**

- Remove null/missing values
- Detect and handle outliers
- Fix data type inconsistencies
- Validate governance requirements
- Improve data quality scores
- Prepare data for ML/analytics

---

## API Endpoints Overview

### Health & Information

- `GET /` - Service information
- `GET /health` - Health check

### Tools

- `GET /tools` - List all available tools
- `GET /tools/{tool_id}` - Get tool definition

### Analysis

- `POST /analyze` - Execute analysis (main endpoint)

### Chat

- `POST /chat` - Ask questions about analysis reports (NEW)

**Example Analysis Request:**

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "tool_id=profile-my-data" \
  -F "primary=@data.csv" \
  -F "agents=unified-profiler,drift-detector" \
  -F 'parameters_json={"unified-profiler":{"null_alert_threshold":40}}'
```

**Example Chat Request:**

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_report": {...analysis_report_json...},
    "user_question": "What are the main data quality issues?"
  }'
```

---

## Response Structure

All analysis responses follow a standardized format:

```json
{
  "analysis_id": "uuid",
  "tool": "tool-id",
  "status": "success",
  "timestamp": "2025-11-17T12:34:56.789Z",
  "execution_time_ms": 5000,
  "report": {
    "alerts": [
      {
        "alert_id": "unique_id",
        "severity": "high|medium|low",
        "category": "data_quality|governance|risk|drift",
        "message": "Human-readable message",
        "affected_fields_count": 5,
        "recommendation": "Suggested action"
      }
    ],
    "issues": [
      {
        "issue_id": "unique_id",
        "agent_id": "agent-name",
        "field_name": "column_name",
        "issue_type": "type_specific",
        "severity": "high|medium|warning",
        "message": "Detailed description"
      }
    ],
    "recommendations": [
      {
        "recommendation_id": "unique_id",
        "agent_id": "agent-name",
        "field_name": "column_name",
        "priority": "high|medium|low",
        "recommendation": "Specific action to take",
        "timeline": "1 week|2 weeks|etc"
      }
    ],
    "executiveSummary": [
      {
        "summary_id": "exec_quality",
        "title": "Metric name",
        "value": "75",
        "status": "excellent|good|fair|poor",
        "description": "Human-readable description"
      }
    ],
    "analysisSummary": {
      "status": "success|pending|error",
      "summary": "AI-generated executive summary",
      "execution_time_ms": 1500,
      "model_used": "gpt-4|fallback-rule-based"
    },
    "routing_decisions": [
      {
        "recommendation_id": "route_1",
        "next_tool": "tool-id",
        "confidence_score": 0.95,
        "reason": "Why this tool is recommended",
        "priority": 1,
        "path": "/results/tool-id",
        "required_files": {
          "primary": { "name": "file.csv", "available": true }
        },
        "expected_benefits": ["benefit1", "benefit2"],
        "estimated_time_minutes": 5,
        "execution_steps": ["step1", "step2"]
      }
    ],
    "downloads": [
      {
        "download_id": "report_id",
        "name": "Complete Analysis Report",
        "format": "xlsx",
        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "blob": "base64_encoded_data",
        "size_bytes": 25000
      }
    ]
  }
}
```

---

## Next Steps

1. **Understand Architecture**: Read [02_ARCHITECTURE.md](./02_ARCHITECTURE.md)
2. **Explore Tools & Agents**: Read [03_TOOLS_OVERVIEW.md](./03_TOOLS_OVERVIEW.md)
3. **Learn API Details**: Read [04_API_REFERENCE.md](./04_API_REFERENCE.md)
4. **Develop Custom Agents**: Read [05_AGENT_DEVELOPMENT.md](./05_AGENT_DEVELOPMENT.md)
5. **Deploy to Production**: Read [06_DEPLOYMENT.md](./06_DEPLOYMENT.md)

---

## Troubleshooting

### Issue: ModuleNotFoundError: No module named 'xxx'

**Solution**: Ensure all dependencies are installed: `pip install -r requirements.txt`

### Issue: Port 8000 already in use

**Solution**: Use a different port: `python main.py --port 8001`

### Issue: OPENAI_API_KEY not set

**Solution**: Set environment variable or it will use rule-based fallbacks:

```bash
export OPENAI_API_KEY="your_key_here"
```

### Issue: Analysis execution timeout

**Solution**: Large files may take longer. Check server logs for processing status.

---

## Support & Resources

- **API Documentation**: Visit http://localhost:8000/docs when server is running
- **GitHub**: VivekBansalBoxinall/Agensium-Backend2
- **Issues**: Report bugs in GitHub Issues
- **Contributing**: See CONTRIBUTING.md (if available)
