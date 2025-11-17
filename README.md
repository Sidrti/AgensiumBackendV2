# Agensium Backend

**Comprehensive Data Analysis Platform** - Combining multiple specialized agents to deliver actionable data insights, risk assessment, and readiness validation.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 Overview

Agensium Backend is a modular, agent-based platform for comprehensive data analysis. It combines multiple specialized analysis agents into a unified API that returns:

- **Actionable Alerts** - Critical issues requiring immediate attention
- **Detailed Issues** - Field-level problems with context
- **Recommendations** - Prioritized action items with timelines
- **Executive Summary** - KPIs at a glance
- **Visualizations** - Graph-ready charts for dashboard integration
- **Complete Agent Data** - Raw outputs for deep analysis
- **Comprehensive Downloads** - Full analysis in Excel and JSON formats
- **Chat Agent** - Ask questions about your analysis reports

### Available Agents

**Profile My Data Tool** (6 agents):

1. **Unified Profiler** - Field-level quality & statistics
2. **Drift Detector** - Distribution change detection
3. **Risk Scorer** - PII & compliance assessment
4. **Readiness Rater** - Production readiness validation
5. **Governance Checker** - Compliance validation
6. **Test Coverage Agent** - Test coverage assessment

**Clean My Data Tool** (5 agents):

1. **Null Handler** - Missing value handling
2. **Outlier Remover** - Outlier detection & removal
3. **Type Fixer** - Data type inconsistency fixing
4. **Governance Checker** - Compliance validation
5. **Test Coverage Agent** - Test coverage assessment

---

## 🚀 Quick Start

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run Server

```bash
python main.py
# Server runs on http://localhost:8000
```

**Visit API Docs**: http://localhost:8000/docs

### First Analysis

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "tool_id=profile-my-data" \
  -F "primary=@data.csv"
```

---

## 📚 Documentation

Read in this order:

1. **PROJECT_ARCHITECTURE.md** - Complete system design & data flow
2. **API_GUIDE.md** - Endpoints, parameters, examples
3. **AGENT_DEVELOPMENT_GUIDE.md** - Creating new agents
4. **Testing_guide.md** - Testing procedures

---

## 🏗️ Architecture

```
FastAPI Server (main.py)
    ├── Tool Loader (JSON definitions)
    └── Route Handler (/analyze endpoint)
         └── Agent Executor
              ├── Unified Profiler
              ├── Drift Detector
              ├── Risk Scorer
              └── Readiness Rater
                   └── Transformer
                        ├── Alerts
                        ├── Issues
                        ├── Recommendations
                        ├── Executive Summary
                        ├── Visualizations
                        └── Downloads
```

---

## 📤 Response Structure

Every analysis returns:

```json
{
  "status": "success",
  "timestamp": "2024-11-14T...",
  "execution_time_ms": 4500,
  "report": {
    "alerts": [...],              // High-level warnings
    "issues": [...],              // Field-level problems
    "recommendations": [...],     // Action items
    "executiveSummary": [...],    // Key metrics
    "visualizations": [...],      // Charts
    "unified-profiler": {...},    // Agent outputs
    "drift-detector": {...},
    "score-risk": {...},
    "readiness-rater": {...},
    "downloads": [...]            // Full analysis
  }
}
```

### Alert Example

```json
{
  "alert_id": "alert_pii_001",
  "severity": "critical",
  "category": "pii_detected",
  "message": "3 PII field(s) detected",
  "affected_fields_count": 3,
  "recommendation": "Implement encryption..."
}
```

---

## 🔧 API Endpoints

| Endpoint           | Method | Purpose                    |
| ------------------ | ------ | -------------------------- |
| `/`                | GET    | Service info               |
| `/health`          | GET    | Health check               |
| `/tools`           | GET    | List tools                 |
| `/tools/{tool_id}` | GET    | Tool details               |
| `/analyze`         | POST   | **Main analysis endpoint** |
| `/chat`            | POST   | **Chat agent endpoint**    |

### POST /analyze

**Parameters**:

- `tool_id` (required) - "profile-my-data" or "clean-my-data"
- `primary` (required) - Data file (CSV/JSON/XLSX)
- `baseline` (optional) - Reference file for comparison
- `agents` (optional) - Agent IDs (comma-separated)
- `parameters_json` (optional) - Custom agent parameters

### POST /chat

**Parameters**:

- `agent_report` (required) - The analysis report JSON (from /analyze response)
- `user_question` (required) - Question about the report
- `history` (optional) - Chat history for context

**Example**:

```python
response = requests.post(
    'http://localhost:8000/chat',
    json={
        'agent_report': analysis_result['report'],
        'user_question': 'What are the main data quality issues?',
        'history': []
    }
)
print(response.json())
```

**Example**:

```python
import requests

response = requests.post(
    'http://localhost:8000/analyze',
    files={
        'primary': open('data.csv', 'rb'),
        'baseline': open('baseline.csv', 'rb')
    },
    data={
        'tool_id': 'profile-my-data',
        'agents': 'unified-profiler,drift-detector,score-risk,readiness-rater'
    }
)

print(response.json())
```

See **API_GUIDE.md** for complete endpoint documentation.

---

## 📥 Downloads System

Both tools now provide **comprehensive exports** in Excel and JSON formats containing **all agent data**.

### Excel Export

**Profile My Data**: 10-sheet workbook with complete profiling analysis

- Summary (metadata, executive summary)
- Profiler (quality scores, field analysis)
- Drift Detection (distribution changes)
- Risk Assessment (PII detection, compliance)
- Readiness (production readiness)
- Governance (compliance validation)
- Test Coverage (test assessment)
- Alerts, Issues, Recommendations (cross-agent tables)

**Clean My Data**: 9-sheet workbook with complete cleaning analysis

- Summary (metadata)
- Null Handler (null detection, handling methods)
- Outlier Remover (outlier detection, thresholds)
- Type Fixer (type inconsistencies, conversions)
- Governance (compliance issues)
- Test Coverage (test assessment)
- Alerts, Issues, Recommendations (cross-agent tables)

### JSON Export

Complete hierarchical export with:

- Metadata and timestamps
- Executive summary
- All alerts, issues, recommendations
- Complete agent results for each agent executed
- Field-level details and metrics

**Base64 Encoded**: Both formats are base64 encoded for API response transmission.

---

## 💬 Chat Agent

Ask intelligent questions about your analysis reports using the **Chat Agent**. Powered by GPT-4, it provides context-aware answers based on your analysis data.

**Features**:

- Analyze complex report data
- Ask follow-up questions with context awareness
- Get natural language explanations of findings
- Understand recommended actions

**Example Usage**:

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_report": {...analysis_report_json...},
    "user_question": "What are the main data quality issues?"
  }'
```

---

### Unified Profiler

Comprehensive field-level quality analysis.

- Quality scores per field
- Data type detection
- Null/missing analysis
- Outlier identification
- Distribution statistics

**Input**: Primary file  
**Output**: Quality metrics, statistics

### Drift Detector

Distribution change detection between files.

- PSI (Population Stability Index) scores
- Statistical test results
- Field-level drift assessment
- Stability classification

**Input**: Primary + baseline files  
**Output**: Drift analysis, stability assessment

### Risk Scorer

PII and compliance risk assessment.

- PII type detection (email, phone, SSN, etc.)
- Risk scores (0-100)
- Compliance framework impacts (GDPR, CCPA, HIPAA)
- Field-level risk categorization

**Input**: Primary file  
**Output**: Risk scores, PII detection, compliance mapping

### Readiness Rater

Production readiness evaluation.

- Readiness score (0-100)
- Component-based breakdown
- Status classification (ready/needs_review/not_ready)
- Issue deductions with remediation

**Input**: Primary file  
**Output**: Readiness assessment, component scores

### Governance Checker

Compliance and governance validation.

- Compliance framework checks (GDPR, CCPA, HIPAA)
- Data governance scoring
- Compliance issue identification
- Remediation recommendations

**Input**: Primary file  
**Output**: Governance scores, compliance status, issues

### Test Coverage Agent

Data quality test coverage assessment.

- Test coverage scoring
- Missing test identification
- Test failure detection
- Coverage recommendations

**Input**: Primary file  
**Output**: Test scores, coverage status, recommendations

---

## 🧹 Clean My Data Tool Agents

### Null Handler

Missing value handling and detection.

- Null percentage analysis
- Null patterns identification
- Imputation method recommendations
- Quality impact assessment

**Input**: Primary file  
**Output**: Null analysis, handling strategies

### Outlier Remover

Outlier detection and removal strategies.

- Statistical outlier detection (IQR, Z-score)
- Outlier handling methods
- Threshold configuration
- Data quality impact

**Input**: Primary file  
**Output**: Outlier detection results, removal recommendations

### Type Fixer

Data type inconsistency fixing.

- Current vs. expected type detection
- Type conversion recommendations
- Conversion success rates
- Issue identification

**Input**: Primary file  
**Output**: Type analysis, conversion recommendations

---

## 🛠️ Development

### Creating a New Agent

1. Create `agents/my_agent.py` with standard function
2. Add agent definition to `tools/profile_my_data_tool.json`
3. Add execution logic to `api/routes.py`
4. Update transformer if needed

See **AGENT_DEVELOPMENT_GUIDE.md** for detailed instructions.

### Project Structure

```
agensium-backend/
├── main.py                              # FastAPI application
├── requirements.txt                     # Dependencies
├── api/
│   ├── routes.py                       # API endpoints
│   └── dependencies.py                 # Utilities
├── agents/                              # Analysis agents
│   ├── unified_profiler.py
│   ├── drift_detector.py
│   ├── score_risk.py
│   ├── readiness_rater.py
│   ├── null_handler.py
│   ├── outlier_remover.py
│   ├── type_fixer.py
│   ├── governance_checker.py
│   └── test_coverage_agent.py
├── ai/                                  # AI decision engines
│   ├── analysis_summary_ai.py           # OpenAI-powered summaries
│   └── routing_decision_ai.py           # Intelligent tool routing
├── transformers/                        # Result aggregators
│   ├── profile_my_data_transformer.py   # Profile tool aggregator
│   └── clean_my_data_transformer.py     # Clean tool aggregator
├── downloads/                           # Download generators (NEW)
│   ├── clean_my_data_downloads.py       # Excel + JSON exports
│   ├── profile_my_data_downloads.py     # Excel + JSON exports
│   └── __init__.py
├── rough/                               # Utilities & examples
│   └── chat_agent.py                    # Chat Q&A engine (NEW)
├── tools/
│   ├── profile_my_data_tool.json        # Profile tool definition
│   └── clean_my_data_tool.json          # Clean tool definition
└── docs/
    ├── 00_INDEX.md                      # Documentation index
    ├── 01_GETTING_STARTED.md            # Quick start guide
    ├── 02_ARCHITECTURE.md               # System architecture
    ├── 03_TOOLS_OVERVIEW.md             # Tools & agents
    ├── 04_API_REFERENCE.md              # API endpoints
    ├── 05_AGENT_DEVELOPMENT.md          # Creating agents
    └── 06_DEPLOYMENT.md                 # Production deployment
```

---

## 📋 Requirements

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pandas==2.1.3
numpy==1.26.2
scipy==1.11.4
python-multipart==0.0.6
python-dotenv==1.0.0
openpyxl==3.1.2
```

**Python**: 3.8+

---

## 📊 Example Usage

### Quality Check Only

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "tool_id=profile-my-data" \
  -F "primary=@data.csv" \
  -F "agents=unified-profiler,readiness-rater"
```

### Complete Analysis

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "tool_id=profile-my-data" \
  -F "primary=@sales_data.csv" \
  -F "baseline=@baseline_sales.csv"
```

### Custom Parameters

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "tool_id=profile-my-data" \
  -F "primary=@data.csv" \
  -F 'parameters_json={"unified-profiler":{"null_alert_threshold":30}}'
```

---

## 🎯 Use Cases

### Quality Gates

```
unified-profiler + readiness-rater
→ Validate before data ingestion
```

### Model Monitoring

```
drift-detector
→ Alert on distribution changes
→ Trigger retraining
```

### Compliance Audit

```
score-risk
→ Identify PII
→ Generate remediation tasks
```

### Pre-Production Validation

```
All agents
→ Comprehensive health check
→ Release if readiness > 80
```

---

## 🚦 Status Codes

| Code | Meaning          |
| ---- | ---------------- |
| 200  | Success          |
| 400  | Validation error |
| 404  | Not found        |
| 500  | Server error     |

---

## ⚙️ Configuration

### Environment Variables

Optional `.env` file:

```
AGENSIUM_DEBUG=false
AGENSIUM_MAX_FILE_SIZE=1000000000
AGENSIUM_TIMEOUT=30
```

### Running with uvicorn

```bash
# Development
python -m uvicorn main:app --reload

# Production
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### AI & OpenAI Configuration

To enable AI-powered features (analysis summary and routing recommender), install the OpenAI Python SDK and set an OpenAI API key in your environment:

1. Install SDK:

```bash
pip install openai
```

2. Create a `.env` file in the `backend/` folder using `backend/.env.sample` and set `OPENAI_API_KEY`.

Note: Without `OPENAI_API_KEY` configured, the backend will use rule-based fallbacks for generation and routing recommendations.

---

## 🔐 Security Notes

**Current**: No authentication

**For Production**, add:

- JWT or API key authentication
- Restrict CORS origins
- Input validation & sanitization
- Rate limiting
- HTTPS/TLS

---

## 📈 Performance

- **Typical**: 4-6 seconds for 10K rows × 20 columns
- **File handling**: In-memory (< 1GB recommended)
- **Agent execution**: Sequential (parallelizable)
- **Visualizations**: ~200ms per chart

---

## 🐛 Troubleshooting

**Server won't start**:

```bash
python --version  # Must be 3.8+
pip install -r requirements.txt
```

**File upload issues**:

- Check file format (CSV, JSON, XLSX)
- Verify file size
- Ensure valid content

**Agent errors**:

- Check agent requirements
- Verify file format
- Validate parameters JSON

---

## 📝 Next Steps

1. Read **PROJECT_ARCHITECTURE.md**
2. Test API at http://localhost:8000/docs
3. Review **EXAMPLE_AGENT_OUTPUTS.json**
4. Try examples from **API_GUIDE.md**
5. Create custom agents per **AGENT_DEVELOPMENT_GUIDE.md**

---

## 💡 Key Principles

✅ **Modular** - Independent agents  
✅ **Uniform** - Standard output format  
✅ **Flexible** - Run any agent combination  
✅ **Simple** - Single function per agent  
✅ **Scalable** - Easy to extend  
✅ **Debuggable** - Full outputs included  
✅ **Frontend-Ready** - Graph-ready visualizations

---

**Version**: 2.0.0  
**Status**: Production Ready ✅  
**License**: MIT

**Recent Updates**:

- ✅ Comprehensive Downloads (Excel + JSON) for all tools
- ✅ Chat Agent for intelligent Q&A on reports
- ✅ Enhanced data quality agents
- ✅ Governance and test coverage assessment

**Documentation**: See `/docs` folder  
**API Docs**: http://localhost:8000/docs  
**Last Updated**: November 2025
