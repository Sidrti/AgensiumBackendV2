# Agensium Backend - System Architecture

## Overview

Agensium Backend uses a **modular, agent-based architecture** where specialized agents work independently or together to analyze data comprehensively. The system intelligently routes users between tools based on analysis findings.

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          FastAPI Server                         │
│                         (main.py)                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   ┌────────────┐  ┌──────────┐  ┌──────────────┐
   │ /tools     │  │/analyze  │  │/health       │
   │(GET)       │  │(POST)    │  │(GET)         │
   │List tools  │  │Run tools │  │Status check  │
   └────────────┘  └──────────┘  └──────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
   ┌─────────────────────────┐  ┌──────────────────┐
   │ Tool Definitions        │  │ Flexible File    │
   │ (tools/*.json)          │  │ Handler          │
   │ - profile-my-data       │  │ (Validates files)│
   │ - clean-my-data         │  └──────────────────┘
   └──────────┬──────────────┘
              │
              ▼
   ┌─────────────────────────────────────────┐
   │ execute_agent_flexible()                │
   │ (Route each agent to executor)          │
   └──────────┬──────────────────────────────┘
              │
    ┌─────────┼─────────┬─────────┬─────────┬──────────┐
    │         │         │         │         │          │
    ▼         ▼         ▼         ▼         ▼          ▼
 ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐
 │Agent │ │Agent │ │Agent │ │Agent │ │Agent │ │ Agent   │
 │  1   │ │  2   │ │  3   │ │  4   │ │  5   │ │   N     │
 └─┬────┘ └─┬────┘ └─┬────┘ └─┬────┘ └─┬────┘ └────┬─────┘
   │        │        │        │        │            │
   │        └────────┼────────┼────────┼────────────┘
   │                 │        │        │
   └─────────────────┼────────┼────────┘
                     │        │
                     ▼        ▼
        ┌─────────────────────────────────┐
        │ Agent Results Dictionary        │
        │ {                               │
        │   "agent-1": {...},            │
        │   "agent-2": {...},            │
        │   ...                          │
        │ }                              │
        └────────────────┬────────────────┘
                         │
                         ▼
        ┌─────────────────────────────────┐
        │ Transformer                     │
        │ (aggregates results)            │
        │ - profile_my_data_transformer   │
        │ - clean_my_data_transformer     │
        └────────────────┬────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌────────┐      ┌──────────┐  ┌───────────┐
    │ Alerts │      │ Issues   │  │Recommend- │
    │ (Cross │      │(Field-   │  │ations     │
    │ agent) │      │ level)   │  │(Actional) │
    │        │      │          │  │           │
    └────────┘      └──────────┘  └───────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐   ┌──────────┐
    │Excel     │    │AI        │   │Routing   │
    │Report    │    │Summary   │   │Decisions │
    │(Base64)  │    │(OpenAI)  │   │(Next     │
    │          │    │          │   │tool rec) │
    └──────────┘    └──────────┘   └──────────┘
                         │
                         ▼
        ┌─────────────────────────────────┐
        │ Final API Response              │
        │ (Standardized Format)           │
        └─────────────────────────────────┘
```

---

## Request Flow Detailed

### Step 1: API Request

```
POST /analyze
├── tool_id: "profile-my-data" or "clean-my-data"
├── primary: File object (CSV/JSON/XLSX)
├── baseline: Optional file for drift detection
├── agents: Optional comma-separated agent list
└── parameters_json: Optional agent-specific parameters
```

### Step 2: Validation

- File format validation
- File size check (max 500MB)
- Agent availability check
- Parameter validation against tool definition

### Step 3: Agent Execution

```
For each requested agent:
1. Extract agent-specific file requirements
2. Build agent input dictionary
3. Call execute_agent_flexible() with agent_id and input
4. Receive standardized agent output
5. Store in agent_results dictionary
```

### Step 4: Result Aggregation

```
Transformer processes all agent results:
1. Extract findings from each agent
2. Create cross-agent alerts and issues
3. Generate unified recommendations
4. Compile executive summary
5. Generate AI-powered analysis summary
6. Create Excel report
7. Determine routing recommendations
```

### Step 5: Response Generation

```
Final response includes:
- analysis_id and metadata
- All aggregated findings
- Excel report (base64 encoded)
- AI-generated summary
- Recommended next tools
```

---

## Agent Execution Architecture

### Standardized Agent Interface

Every agent follows this pattern:

```python
def execute_XXX_agent(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Agent execution function.

    Returns:
    {
        "status": "success" | "error",
        "agent_id": "agent-name",
        "agent_name": "Human Readable Name",
        "execution_time_ms": integer,
        "summary_metrics": {
            "metric1": value,
            "metric2": value
        },
        "data": {
            "analysis_result": {...},
            "summary": "string"
        }
    }
    """
```

### Agent Categories

#### Profile Tool Agents (tool_id="profile-my-data")

1. **Unified Profiler**

   - Role: Comprehensive data statistics
   - Input: Primary file
   - Output: Quality metrics, field statistics, distribution analysis

2. **Drift Detector**

   - Role: Compare datasets for changes
   - Input: Primary + Baseline files
   - Output: PSI scores, drift percentages, distribution changes

3. **Score Risk**

   - Role: PII and compliance risk assessment
   - Input: Primary file
   - Output: Risk scores, PII detection, compliance gaps

4. **Readiness Rater**

   - Role: Production readiness evaluation
   - Input: Primary file
   - Output: Readiness score, component scores, deductions

5. **Governance Checker**

   - Role: Compliance validation
   - Input: Primary file
   - Output: Governance scores, compliance status, issues

6. **Test Coverage Agent**
   - Role: Test coverage validation
   - Input: Primary file
   - Output: Coverage scores, validation results

#### Clean Tool Agents (tool_id="clean-my-data")

1. **Null Handler**

   - Role: Missing value handling
   - Input: Primary file
   - Output: Cleaning score, imputation log, recommendations

2. **Outlier Remover**

   - Role: Outlier detection and removal
   - Input: Primary file
   - Output: Outlier score, detection method results, handling log

3. **Type Fixer** ✨ NEW

   - Role: Data type inconsistency fixing
   - Input: Primary file
   - Output: Fixing score, type analysis, conversion recommendations

4. **Governance Checker**

   - Role: Compliance validation
   - Input: Primary file
   - Output: Governance scores, compliance status

5. **Test Coverage Agent**
   - Role: Test coverage validation
   - Input: Primary file
   - Output: Coverage scores, validation results

---

## Transformer Architecture

### Profile My Data Transformer

**Location**: `transformers/profile_my_data_transformer.py`

**Processes:**

- Unified Profiler → Quality metrics
- Drift Detector → Drift alerts
- Score Risk → Risk alerts
- Readiness Rater → Readiness issues
- Governance Checker → Governance alerts
- Test Coverage → Test coverage alerts

**Generates:**

- Cross-agent alerts (high-level warnings)
- Field-level issues (specific problems)
- Actionable recommendations (prioritized)
- Executive summary (KPI overview)
- AI-powered summary (OpenAI)
- Excel report (multi-sheet)
- Routing decisions (next tool recommendations)

### Clean My Data Transformer

**Location**: `transformers/clean_my_data_transformer.py`

**Processes:**

- Null Handler → Quality improvements
- Outlier Remover → Outlier handling
- Type Fixer → Type conversions
- Governance Checker → Compliance
- Test Coverage → Coverage improvements

**Generates:**

- Data quality alerts
- Cleaning issue details
- Improvement recommendations
- Executive summary
- AI-powered analysis
- Excel report
- Routing decisions

---

## AI Decision Engines

### Analysis Summary AI

**Location**: `ai/analysis_summary_ai.py`

**Purpose**: Generate human-readable executive summaries using OpenAI GPT

**Process:**

1. Collect analysis text from alerts, issues, recommendations
2. Build comprehensive analysis context
3. Call OpenAI API with detailed prompt
4. Generate concise executive summary
5. Fallback to rule-based summary if API unavailable

### Routing Decision AI

**Location**: `ai/routing_decision_ai.py`

**Purpose**: Intelligently recommend next tool based on current analysis

**Algorithm:**

1. Analyze current tool results
2. Extract key findings and metrics
3. Use OpenAI to score tool recommendations
4. Fallback to rule-based recommendations
5. Format routing decisions with file info and parameters

**Routing Logic:**

- If profile quality < 70: Recommend clean-my-data
- If clean completed: Recommend profile-my-data for verification
- If type mismatches detected: Recommend type-fixer
- If governance issues: Recommend appropriate tool
- Priority: Type consistency → Quality → Governance → Risk

---

## Data Flow Example

### Scenario: Profile My Data Analysis

```
1. User uploads data.csv
   ↓
2. API Validation
   - Check CSV format ✓
   - Check file size < 500MB ✓
   - Check agents available ✓
   ↓
3. Agent Execution (parallel)
   ├─ unified-profiler
   │  └─ Output: quality_score=72, issues=15
   ├─ drift-detector
   │  └─ Output: drift_pct=5.2, status="stable"
   ├─ score-risk
   │  └─ Output: risk_score=45, pii_found=["SSN", "Email"]
   ├─ readiness-rater
   │  └─ Output: readiness_score=68, status="not_ready"
   ├─ governance-checker
   │  └─ Output: compliance="needs_review", issues=3
   └─ test-coverage-agent
      └─ Output: coverage_score=65, gaps=5
   ↓
4. Transformer Aggregation
   - Extract quality concerns (score=72 < 80)
   - Extract readiness issues (not_ready)
   - Extract governance gaps
   - Extract test coverage gaps
   - Create quality alert
   - Create readiness alert
   - Create governance alert
   ↓
5. AI Summary Generation
   - Analyze all findings
   - Generate: "Data quality is acceptable but requires
     attention to readiness. Three governance gaps and
     five test coverage gaps identified. Type consistency
     and null value handling recommended."
   ↓
6. Routing Decision
   - Analysis: readiness_score=68, quality_score=72
   - Decision: Recommend clean-my-data
   - Reason: "Run Clean My Data to improve readiness
     and quality scores through null handling and
     type fixing"
   ↓
7. Response Sent
   {
     "analysis_id": "uuid-123",
     "status": "success",
     "report": {
       "alerts": [quality_alert, readiness_alert, ...],
       "issues": [field_issues],
       "recommendations": [actions],
       "executiveSummary": [metrics],
       "analysisSummary": {summary},
       "routing_decisions": [next_tool_recommendation],
       "downloads": [excel_report]
     }
   }
```

---

## Performance Considerations

### Agent Execution

- Agents run **sequentially** (not parallel) to manage resource usage
- Large files (>100MB) may take 30-60 seconds per agent
- Maximum file size: 500MB

### Result Aggregation

- Transformer processes all agent results: ~2-5 seconds
- AI summary generation: ~5-10 seconds (depends on OpenAI API)
- Excel report generation: ~1-2 seconds

### Total Expected Times

- Small file (<10MB), 6 agents: 15-30 seconds
- Medium file (50MB), 6 agents: 60-120 seconds
- Large file (200MB), 6 agents: 300+ seconds

---

## Technology Stack

| Component           | Technology          | Purpose             |
| ------------------- | ------------------- | ------------------- |
| **Server**          | FastAPI             | REST API framework  |
| **Data Processing** | Pandas, NumPy       | Data analysis       |
| **Statistical**     | SciPy, Scikit-learn | Advanced statistics |
| **Excel**           | openpyxl            | Report generation   |
| **AI/LLM**          | OpenAI API          | Summary generation  |
| **Encoding**        | Base64              | File transfer       |
| **Concurrency**     | asyncio             | Async operations    |
| **Validation**      | Pydantic            | Request validation  |

---

## Error Handling

### Request Validation Errors (400)

```json
{
  "detail": "Invalid request: missing required parameter 'tool_id'"
}
```

### Agent Execution Errors (500)

```json
{
  "detail": "Agent 'unified-profiler' failed: ValueError in analysis"
}
```

### System Errors (500)

```json
{
  "detail": "System error: Unable to process file"
}
```

---

## Next Steps

- Read [03_TOOLS_OVERVIEW.md](./03_TOOLS_OVERVIEW.md) for agent details
- Read [04_API_REFERENCE.md](./04_API_REFERENCE.md) for endpoint details
- Read [05_AGENT_DEVELOPMENT.md](./05_AGENT_DEVELOPMENT.md) for creating agents
