# Agensium Backend - Downloads & Chat Features

## Overview

This document describes the two major new features added to Agensium Backend:

1. **Comprehensive Downloads System** - Excel and JSON exports with complete analysis data
2. **Chat Agent** - Intelligent Q&A on analysis reports using LLM

---

## 📥 Downloads System

### Purpose

Provide clients with complete, comprehensive analysis exports in multiple formats for easy sharing, reporting, and further analysis.

### Architecture

```
Transformer Results
        ↓
├── CleanMyDataDownloads / ProfileMyDataDownloads
│   ├── _generate_excel_report()
│   │   ├── Create Workbook
│   │   ├── Add Summary Sheet
│   │   ├── Add Agent-Specific Sheets
│   │   ├── Add Alerts/Issues/Recommendations Sheet
│   │   └── Format & Style
│   │
│   └── _generate_json_report()
│       ├── Collect Metadata
│       ├── Build Summary Stats
│       ├── Include All Agent Results
│       └── Include Aggregated Findings
│
└── API Response (Base64 Encoded)
    ├── Excel File
    └── JSON File
```

### Modules

#### **`/backend/downloads/clean_my_data_downloads.py`**

**Class**: `CleanMyDataDownloads`

**Purpose**: Generate comprehensive downloads for clean-my-data tool

**Main Method**:

```python
def generate_downloads(
    agent_results,      # Dict of all agent outputs
    analysis_id,        # Unique analysis ID
    execution_time_ms,  # Total execution time
    alerts,             # Aggregated alerts
    issues,             # Aggregated issues
    recommendations     # Aggregated recommendations
) -> list
```

**Returns**: `[excel_dict, json_dict]` - Two download items

**Excel Sheets** (9 total):

1. **Summary** - Metadata, analysis ID, timestamp, execution time, statistics
2. **Null Handler** - Null detection, handling methods, null percentages, recommendations
3. **Outlier Remover** - Outlier counts, detection methods, thresholds, confidence scores
4. **Type Fixer** - Current types, suggested types, conversion status, issues
5. **Governance** - Compliance scores, governance issues, remediation
6. **Test Coverage** - Test scores, coverage status, missing tests
7. **Alerts** - All alerts with severity, category, message, recommendations
8. **Issues** - All issues with field names, types, severity, descriptions
9. **Recommendations** - All recommendations with priority, timeline, actions

**JSON Structure**:

```json
{
  "metadata": {
    "analysis_id": "...",
    "tool": "clean-my-data",
    "timestamp": "2025-11-17T...",
    "execution_time_ms": 5000,
    "report_version": "2.0"
  },
  "summary": {
    "total_alerts": 5,
    "total_issues": 12,
    "total_recommendations": 8
  },
  "alerts": [...],
  "issues": [...],
  "recommendations": [...],
  "agent_results": {
    "null-handler": {...},
    "outlier-remover": {...},
    "type-fixer": {...},
    "governance-checker": {...},
    "test-coverage-agent": {...}
  }
}
```

#### **`/backend/downloads/profile_my_data_downloads.py`**

**Class**: `ProfileMyDataDownloads`

**Purpose**: Generate comprehensive downloads for profile-my-data tool

**Main Method**: Same signature as CleanMyDataDownloads

**Excel Sheets** (10 total):

1. **Summary** - Executive summary, metadata, key statistics
2. **Profiler** - Quality scores, field-level analysis, data types, completeness
3. **Drift Detection** - Distribution changes, PSI scores, KL divergence, stability
4. **Risk Assessment** - Risk scores, PII detection, compliance impacts, risk factors
5. **Readiness** - Readiness score, component assessment, deductions, status
6. **Governance** - Compliance scores, governance issues, framework impacts
7. **Test Coverage** - Test scores, coverage status, failing tests
8. **Alerts** - Cross-agent alert summary
9. **Issues** - Cross-agent issues summary
10. **Recommendations** - Cross-agent recommendations with prioritization

**JSON Structure**:

```json
{
  "metadata": {...},
  "executive_summary": {
    "quality_score": 75.5,
    "readiness_status": "needs_review",
    "governance_compliance": "compliant",
    "test_coverage": "good",
    "risk_level": "medium",
    "drift_status": "stable"
  },
  "summary": {...},
  "alerts": [...],
  "issues": [...],
  "recommendations": [...],
  "agent_results": {
    "unified-profiler": {...},
    "drift-detector": {...},
    "score-risk": {...},
    "readiness-rater": {...},
    "governance-checker": {...},
    "test-coverage-agent": {...}
  }
}
```

### Key Features

✅ **Comprehensive Data** - 100% of agent outputs included (not filtered)
✅ **Professional Styling** - Color-coded headers, formatted tables, wrapped text
✅ **Base64 Encoding** - Both formats encoded for API transmission
✅ **Field-Level Details** - Each agent's field-specific findings included
✅ **Metadata** - Analysis ID, timestamp, execution time for audit trail
✅ **Aggregated Insights** - Cross-agent findings in consolidated views

### Usage in Transformers

**Clean My Data Transformer**:

```python
from downloads.clean_my_data_downloads import CleanMyDataDownloads

downloader = CleanMyDataDownloads()
downloads = downloader.generate_downloads(
    agent_results=agent_results,
    analysis_id=analysis_id,
    execution_time_ms=execution_time_ms,
    alerts=all_alerts,
    issues=all_issues,
    recommendations=all_recommendations
)

# downloads = [excel_dict, json_dict]
response['report']['downloads'] = downloads
```

**Profile My Data Transformer**:

```python
from downloads.profile_my_data_downloads import ProfileMyDataDownloads

downloader = ProfileMyDataDownloads()
downloads = downloader.generate_downloads(
    agent_results=agent_results,
    analysis_id=analysis_id,
    execution_time_ms=execution_time_ms,
    alerts=all_alerts,
    issues=all_issues,
    recommendations=all_recommendations,
    executive_summary=executive_summary
)

response['report']['downloads'] = downloads
```

### Example Response

```json
{
  "downloads": [
    {
      "download_id": "excel_export_001",
      "name": "Data Analysis - Complete Report.xlsx",
      "format": "xlsx",
      "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "blob": "UEsDBBQACAAIAL...[base64 encoded Excel file]...AQ==",
      "size_bytes": 125000
    },
    {
      "download_id": "json_export_001",
      "name": "Data Analysis - Complete Report.json",
      "format": "json",
      "mimeType": "application/json",
      "blob": "eyJtZXRhZGF0YSI6e...[base64 encoded JSON]...fX0==",
      "size_bytes": 45000
    }
  ]
}
```

### Client-Side Usage

**JavaScript/Frontend**:

```javascript
// Assume response is the API response object
const downloads = response.report.downloads;

// Find Excel download
const excelDownload = downloads.find((d) => d.format === "xlsx");
if (excelDownload) {
  const blob = new Blob([atob(excelDownload.blob)], {
    type: excelDownload.mimeType,
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = excelDownload.name;
  a.click();
}

// Find JSON download
const jsonDownload = downloads.find((d) => d.format === "json");
if (jsonDownload) {
  const jsonData = JSON.parse(atob(jsonDownload.blob));
  console.log("Analysis Data:", jsonData);
}
```

### Configuration & Customization

Both download modules use professional styling:

```python
# Header styling (in __init__)
self.header_fill = "1F4E78"        # Dark blue
self.header_font = "FFFFFF"        # White text
self.subheader_fill = "D9E1F2"     # Light blue
self.borders = True                 # All cells have borders
self.wrapped_text = True            # Text wrapping enabled
```

To customize, modify the styling constants in the respective download modules.

---

## 💬 Chat Agent

### Purpose

Allow users to ask natural language questions about analysis reports and receive intelligent, context-aware answers powered by LLM (Large Language Model).

### Architecture

```
User Question + Report JSON
        ↓
┌─────────────────────────────┐
│  ChatAgent                  │
│  (in /backend/rough/)       │
│                             │
│  answer_question_on_report()│
│                             │
│  System Prompt:             │
│  - Expert data analyst      │
│  - Base answers only on     │
│    provided report          │
│  - Don't make up data       │
│  - Answer concisely         │
└────────────┬────────────────┘
             ↓
    ┌─────────────────────┐
    │  OpenAI API         │
    │  GPT-4o-mini        │
    │  (or fallback)      │
    └────────────┬────────┘
             ↓
    Context-aware Answer
```

### Module: `/backend/rough/chat_agent.py`

**Function**: `answer_question_on_report()`

**Parameters**:

```python
def answer_question_on_report(
    agent_report: dict,      # Analysis report JSON
    user_question: str,      # User's question
    history: list = None     # Previous messages (for context)
) -> dict
```

**Returns**:

```json
{
  "agent": "ChatAgent",
  "results": {
    "status": "success",
    "user_question": "What are the main data quality issues?",
    "answer": "Based on the analysis report, the main data quality issues are: 1) 15% null values in the customer_id field, 2) Type inconsistencies in the age field, 3) 8 outliers detected in the revenue field..."
  }
}
```

**Error Handling**:

```json
{
  "agent": "ChatAgent",
  "results": {
    "status": "error",
    "user_question": "...",
    "error": "Failed to get response from OpenAI. Error: API key not configured."
  }
}
```

### Features

✅ **Report-Based** - Answers only use information in provided report
✅ **No Hallucination** - Refuses to make up data not in report
✅ **Context Aware** - Understands chat history for follow-up questions
✅ **Natural Language** - Understands complex analytical questions
✅ **Professional Tone** - Maintains expert analyst voice

### System Prompt

The chat agent uses this system prompt to guide responses:

```
You are 'Agensium Co-Pilot', a world-class AI data analyst.
Your sole purpose is to answer questions about a data analysis report
provided in JSON format.

You must adhere to the following rules:
1. Base your answers *exclusively* on the information within the
   provided JSON report.
2. Do not make up information, guess, or infer data that isn't present.
3. If the answer cannot be found in the report, you must state
   that clearly.
4. Answer concisely and directly in a helpful, professional tone.
5. Use the provided chat history to understand the context of
   follow-up questions.
```

### API Endpoint: `/chat`

**Method**: `POST`

**Request**:

```json
{
  "agent_report": {
    "alerts": [...],
    "issues": [...],
    "recommendations": [...],
    "executive_summary": [...],
    "unified-profiler": {...}
  },
  "user_question": "What are the main quality issues?",
  "history": [
    {"role": "user", "content": "Tell me about data quality"},
    {"role": "assistant", "content": "The overall quality score is..."}
  ]
}
```

**Response**:

```json
{
  "agent": "ChatAgent",
  "results": {
    "status": "success",
    "user_question": "What are the main quality issues?",
    "answer": "Based on the analysis, the main quality issues are: ..."
  }
}
```

### Implementation in Routes

```python
# In api/routes.py
from rough.chat_agent import answer_question_on_report

@app.post("/chat")
async def chat_endpoint(
    agent_report: dict,
    user_question: str,
    history: list = None
):
    try:
        result = answer_question_on_report(
            agent_report=agent_report,
            user_question=user_question,
            history=history
        )
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

### Usage Examples

#### Example 1: Understanding Quality Issues

```
User: "What are the main data quality issues?"
Chat Agent: "Based on the analysis report, there are 5 critical
quality issues: 1) Customer ID field has 12% null values, 2) Age
field has type inconsistencies (mixed integers and strings), 3)
Revenue field has 8 outliers detected, 4) Email field has invalid
format in 3 records, 5) Duplicate customer records found in 2.5%
of data."
```

#### Example 2: Follow-up Question with Context

```
User: "What's causing the type inconsistencies in the age field?"
Chat Agent: "The age field has type inconsistencies because: values
are stored as both integers (e.g., 25) and strings (e.g., "25").
The Type Fixer agent recommends converting all values to integers.
Conversion success rate is estimated at 98%."
```

#### Example 3: Compliance Question

```
User: "Are we GDPR compliant?"
Chat Agent: "According to the governance checker results, your
compliance status is 'needs_review'. Specific issues: 1) PII data
not encrypted (customer names and email addresses), 2) Data
retention policy not documented, 3) 3 fields flagged as potentially
sensitive require access control policies."
```

#### Example 4: Unknown Information

```
User: "What's the security score of the database?"
Chat Agent: "I cannot find information about a 'security score'
in the provided analysis report. The report includes quality scores,
risk assessment, governance compliance, and readiness evaluation,
but not a specific database security score."
```

### Configuration

**Environment Variable**:

```bash
# .env file

```

**Model Used**:

```python
MODEL_NAME = 'gpt-4o-mini'  # Powerful and cost-effective
```

**API Key Loading**:

```python
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")
```

### Error Handling

**Graceful Fallback**:

- If OpenAI API fails, returns error status with message
- Errors include: missing API key, network issues, rate limiting, invalid request

**Common Errors**:

```
"OPENAI_API_KEY environment variable is not set"
→ Solution: Add API key to .env file

"Failed to get response from OpenAI. Rate limit exceeded."
→ Solution: Wait before making more requests

"The model 'gpt-4o-mini' does not exist"
→ Solution: Verify OpenAI subscription includes this model
```

### Performance Considerations

**Response Times**:

- Average: 1-3 seconds
- Best case: <1 second (simple questions)
- Worst case: 5+ seconds (complex analyses with large reports)

**Cost**:

- gpt-4o-mini is cost-effective (~0.15 cents per 1K tokens)
- Average question: 150-300 input tokens, 50-200 output tokens

**Optimization Tips**:

- Use specific questions (faster than vague queries)
- Provide chat history for context (reduces token usage)
- Filter large reports to relevant sections before sending

---

## Integration Example

### Complete Workflow

```python
# Step 1: Run analysis
response = requests.post(
    'http://localhost:8000/analyze',
    files={'primary': open('data.csv', 'rb')},
    data={'tool_id': 'profile-my-data'}
)
analysis_report = response.json()['report']

# Step 2: Get downloads
downloads = analysis_report['downloads']
excel = downloads[0]  # Excel export
json_export = downloads[1]  # JSON export

# Step 3: Download files
excel_blob = base64.b64decode(excel['blob'])
with open('analysis_report.xlsx', 'wb') as f:
    f.write(excel_blob)

# Step 4: Ask questions about the report
chat_history = []
questions = [
    "What are the main data quality issues?",
    "How can we improve the readiness score?",
    "Are there any PII concerns?"
]

for question in questions:
    chat_response = requests.post(
        'http://localhost:8000/chat',
        json={
            'agent_report': analysis_report,
            'user_question': question,
            'history': chat_history
        }
    )

    answer = chat_response.json()['results']['answer']
    print(f"Q: {question}\nA: {answer}\n")

    # Add to history for context
    chat_history.append({"role": "user", "content": question})
    chat_history.append({"role": "assistant", "content": answer})
```

---

## Future Enhancements

### Planned Features

1. **Multi-Report Analysis**

   - Ask questions comparing multiple reports
   - Trend analysis across reports

2. **Custom Export Templates**

   - User-defined Excel sheet layouts
   - Branding/logo insertion

3. **Chat History Persistence**

   - Save conversation threads
   - Resume previous analysis discussions

4. **Advanced Chat Features**

   - Follow-up recommendations ("What's next?")
   - Automated insight generation
   - Report summarization
   - Actionable step-by-step guides

5. **Export Customization**
   - Filter by severity level
   - Custom field selection
   - Multi-language support

---

## Troubleshooting

### Downloads Not Showing

**Issue**: `downloads` field is empty in response

- Check that transformers are calling `CleanMyDataDownloads()` or `ProfileMyDataDownloads()`
- Verify agent results are being passed correctly
- Check for errors in download module

### Chat Returns Error

**Issue**: Chat endpoint returns 500 error

- Verify `OPENAI_API_KEY` environment variable is set
- Check OpenAI API account has available balance
- Verify `gpt-4o-mini` model is available in your account
- Check network connectivity to OpenAI API

### Base64 Decoding Issues

**Issue**: Error decoding base64 from downloads

- Ensure blob is properly base64 encoded (no line breaks)
- Use standard `base64` library for decoding
- Verify MIME type matches file format

---

## Best Practices

### For Downloads

✅ Always include both Excel and JSON formats
✅ Use descriptive file names with timestamps
✅ Validate base64 encoding before transmission
✅ Include metadata for audit trails
✅ Test exports with real data before deployment

### For Chat

✅ Include full report for comprehensive answers
✅ Ask specific questions (not vague queries)
✅ Maintain chat history for follow-ups
✅ Monitor token usage for cost optimization
✅ Handle errors gracefully with user-friendly messages

---

## Support & Resources

- **Downloads Module**: `/backend/downloads/`
- **Chat Agent**: `/backend/rough/chat_agent.py`
- **API Integration**: See `04_API_REFERENCE.md`
- **Example Response**: See `01_GETTING_STARTED.md`

---

**Version**: 2.0.0  
**Status**: Production Ready ✅  
**Last Updated**: November 2025
