"""
ROW_LEVEL_ISSUES_IMPLEMENTATION_TEMPLATE.md

Code templates and patterns for implementing row-level-issues in agents.
Copy, adapt, and customize for each agent.
"""

# Row-Level-Issues Implementation Template

## Generic Agent Template

Use this template as a starting point for each agent. Customize the detection logic specific to your agent.

```python
"""
[AGENT_NAME] Agent

Description of what agent does...
Expanded to include row-level-issues field.

Row-Level-Issues: Detects [issue types] at individual row level
"""

import pandas as pd
import numpy as np
import io
import time
from typing import Dict, Any, Optional, List


def [agent_function_name](
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    [Agent description]

    Args:
        file_contents: File bytes
        filename: Original filename
        parameters: Agent parameters

    Returns:
        Standardized response with alerts, issues, recommendations, AND row-level-issues
    """

    start_time = time.time()
    parameters = parameters or {}

    try:
        # Read file
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_contents))
        elif filename.endswith('.json'):
            df = pd.read_json(io.BytesIO(file_contents))
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(file_contents))
        else:
            return {
                "status": "error",
                "error": f"Unsupported file format: {filename}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # ==================== AGENT ANALYSIS LOGIC ====================
        # [CUSTOMIZE THIS SECTION FOR YOUR AGENT]
        # Your detection logic goes here
        # ...

        # ==================== ROW-LEVEL-ISSUES GENERATION ====================
        # Initialize row-level-issues collection
        row_level_issues: List[Dict[str, Any]] = []
        affected_rows_set = set()
        affected_columns_set = set()
        issue_type_count = {}
        severity_count = {"critical": 0, "warning": 0, "info": 0}

        # [CUSTOMIZE THIS SECTION - ADD DETECTION LOGIC]
        # Example pattern for detecting row-level issues:
        for idx, row in df.iterrows():
            # Detect issues in this row
            # ...

            # When issue found:
            issue = {
                "row_index": idx,
                "column": "column_name",
                "issue_type": "issue_type",
                "severity": "critical|warning|info",
                "message": "Human-readable message"
            }

            # Add optional fields as needed:
            issue["value"] = row["column_name"]  # Optional
            issue["bounds"] = {"lower": 0, "upper": 100}  # Optional (for outliers)

            row_level_issues.append(issue)
            affected_rows_set.add(idx)
            affected_columns_set.add("column_name")

            # Track counts for summary
            issue_type = issue["issue_type"]
            issue_type_count[issue_type] = issue_type_count.get(issue_type, 0) + 1
            severity_count[issue["severity"]] += 1

            # Cap at 200 issues for performance
            if len(row_level_issues) >= 200:
                break

        # ==================== BUILD ISSUE SUMMARY ====================
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": issue_type_count,
            "by_severity": severity_count,
            "affected_rows": len(affected_rows_set),
            "affected_columns": sorted(list(affected_columns_set))
        }

        # ==================== BUILD ALERTS ====================
        # [Use existing alert generation logic]
        alerts = []
        # ... existing alert code ...

        # ==================== BUILD ISSUES ====================
        # [Use existing field-level issue generation logic]
        issues = []
        # ... existing issue code ...

        # ==================== BUILD RECOMMENDATIONS ====================
        # [Use existing recommendation generation logic]
        recommendations = []
        # ... existing recommendation code ...

        # ==================== RETURN UNIFIED RESPONSE ====================
        return {
            "status": "success",
            "agent_id": "[AGENT_ID]",
            "timestamp": datetime.now().isoformat(),
            "file_name": filename,
            "execution_time_ms": int((time.time() - start_time) * 1000),

            # Original fields (keep as-is)
            "alerts": alerts,
            "issues": issues,
            "recommendations": recommendations,

            # NEW FIELDS FOR ROW-LEVEL DETAILS
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }
```

---

## Agent-Specific Implementation Guides

### 1. unified_profiler.py - OUTLIER DETECTION

```python
# ==================== ROW-LEVEL-ISSUES GENERATION ====================
row_level_issues = []
affected_rows_set = set()
affected_columns_set = set()
issue_type_count = {}
severity_count = {"critical": 0, "warning": 0, "info": 0}

# Iterate through each column for outlier detection
for col in df.columns:
    col_data = df[col].dropna()

    # Only numeric columns
    if not pd.api.types.is_numeric_dtype(col_data):
        continue

    # Calculate IQR bounds
    Q1 = col_data.quantile(0.25)
    Q3 = col_data.quantile(0.75)
    IQR = Q3 - Q1
    outlier_iqr_multiplier = parameters.get("outlier_iqr_multiplier", 1.5)
    lower_bound = Q1 - (outlier_iqr_multiplier * IQR)
    upper_bound = Q3 + (outlier_iqr_multiplier * IQR)

    # Detect outliers
    for idx, row in df.iterrows():
        value = row[col]

        # Check for outliers
        if pd.notna(value):
            if value < lower_bound or value > upper_bound:
                severity = "warning" if abs(value - Q2) < 3 * IQR else "critical"

                issue = {
                    "row_index": idx,
                    "column": col,
                    "issue_type": "outlier",
                    "severity": severity,
                    "message": f"Value {value} is outside normal range [{lower_bound:.2f}, {upper_bound:.2f}]",
                    "value": value,
                    "bounds": {"lower": float(lower_bound), "upper": float(upper_bound)}
                }

                row_level_issues.append(issue)
                affected_rows_set.add(idx)
                affected_columns_set.add(col)
                issue_type_count["outlier"] = issue_type_count.get("outlier", 0) + 1
                severity_count[severity] += 1

        # Check for nulls
        elif pd.isna(value):
            issue = {
                "row_index": idx,
                "column": col,
                "issue_type": "null",
                "severity": "info",
                "message": "Missing value (NULL)",
                "value": None
            }

            row_level_issues.append(issue)
            affected_rows_set.add(idx)
            affected_columns_set.add(col)
            issue_type_count["null"] = issue_type_count.get("null", 0) + 1
            severity_count["info"] += 1

        # Cap issues
        if len(row_level_issues) >= 200:
            break

    if len(row_level_issues) >= 200:
        break
```

### 2. outlier_remover.py - OUTLIER WITH BOUNDS

```python
# ==================== ROW-LEVEL-ISSUES GENERATION ====================
row_level_issues = []
affected_rows_set = set()
affected_columns_set = set()
issue_type_count = {}
severity_count = {"critical": 0, "warning": 0, "info": 0}

# Use isolation forest for multi-dimensional outlier detection
from sklearn.ensemble import IsolationForest

# Prepare numeric data
numeric_cols = df.select_dtypes(include=[np.number]).columns
X = df[numeric_cols].fillna(df[numeric_cols].mean())

# Detect outliers
if len(numeric_cols) > 0 and len(X) > 0:
    iso_forest = IsolationForest(contamination=0.1, random_state=42)
    outlier_labels = iso_forest.fit_predict(X)
    outlier_scores = iso_forest.score_samples(X)

    # Collect outlier rows
    for idx, (label, score) in enumerate(zip(outlier_labels, outlier_scores)):
        if label == -1:  # Outlier detected
            severity = "critical" if score < -0.5 else "warning"

            # Find which columns contributed to outlier
            for col in numeric_cols:
                value = df.loc[idx, col]
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - 1.5 * IQR
                upper = Q3 + 1.5 * IQR

                if value < lower or value > upper:
                    issue = {
                        "row_index": idx,
                        "column": col,
                        "issue_type": "outlier",
                        "severity": severity,
                        "message": f"Outlier detected: {value} outside [{lower:.2f}, {upper:.2f}]",
                        "value": value,
                        "bounds": {"lower": float(lower), "upper": float(upper)},
                        "anomaly_score": float(score)
                    }

                    row_level_issues.append(issue)
                    affected_rows_set.add(idx)
                    affected_columns_set.add(col)
                    issue_type_count["outlier"] = issue_type_count.get("outlier", 0) + 1
                    severity_count[severity] += 1

                    if len(row_level_issues) >= 200:
                        break

        if len(row_level_issues) >= 200:
            break
```

### 3. type_fixer.py - TYPE MISMATCHES

```python
# ==================== ROW-LEVEL-ISSUES GENERATION ====================
row_level_issues = []
affected_rows_set = set()
affected_columns_set = set()
issue_type_count = {}
severity_count = {"critical": 0, "warning": 0, "info": 0}

# Define expected types by column
expected_types = parameters.get("expected_types", {})  # e.g., {"age": "int", "email": "email"}

for col, expected_type in expected_types.items():
    if col not in df.columns:
        continue

    for idx, value in df[col].items():
        if pd.isna(value):
            continue

        # Validate type
        is_valid = False
        issue = None

        if expected_type == "int":
            try:
                int(value)
                is_valid = True
            except (ValueError, TypeError):
                issue = {
                    "row_index": idx,
                    "column": col,
                    "issue_type": "type_mismatch",
                    "severity": "critical",
                    "message": f"Expected integer, got '{value}' ({type(value).__name__})",
                    "value": value
                }

        elif expected_type == "float":
            try:
                float(value)
                is_valid = True
            except (ValueError, TypeError):
                issue = {
                    "row_index": idx,
                    "column": col,
                    "issue_type": "type_mismatch",
                    "severity": "critical",
                    "message": f"Expected float, got '{value}'",
                    "value": value
                }

        elif expected_type == "email":
            import re
            email_pattern = r'^[^@]+@[^@]+\.[^@]+$'
            if not re.match(email_pattern, str(value)):
                issue = {
                    "row_index": idx,
                    "column": col,
                    "issue_type": "format_violation",
                    "severity": "warning",
                    "message": f"Invalid email format: '{value}'",
                    "value": value
                }

        elif expected_type == "date":
            try:
                pd.to_datetime(value)
                is_valid = True
            except:
                issue = {
                    "row_index": idx,
                    "column": col,
                    "issue_type": "format_violation",
                    "severity": "warning",
                    "message": f"Invalid date format: '{value}'",
                    "value": value
                }

        if issue:
            row_level_issues.append(issue)
            affected_rows_set.add(idx)
            affected_columns_set.add(col)
            issue_type_count[issue["issue_type"]] = issue_type_count.get(issue["issue_type"], 0) + 1
            severity_count[issue["severity"]] += 1

            if len(row_level_issues) >= 200:
                break

    if len(row_level_issues) >= 200:
        break
```

### 4. duplicate_resolver.py - DUPLICATES

```python
# ==================== ROW-LEVEL-ISSUES GENERATION ====================
row_level_issues = []
affected_rows_set = set()
affected_columns_set = set()
issue_type_count = {}
severity_count = {"critical": 0, "warning": 0, "info": 0}

# Detect exact duplicates
duplicates = df[df.duplicated(keep=False)]

for idx, row in duplicates.iterrows():
    # Find which other rows it duplicates
    duplicate_mask = (df == row).all(axis=1)
    duplicate_indices = df[duplicate_mask].index.tolist()
    duplicate_indices = [i for i in duplicate_indices if i != idx]

    if duplicate_indices:
        first_dup = duplicate_indices[0]
        issue = {
            "row_index": idx,
            "column": "ALL",
            "issue_type": "duplicate_row",
            "severity": "critical",
            "message": f"Exact duplicate found at row {first_dup}",
            "matched_rows": duplicate_indices
        }

        row_level_issues.append(issue)
        affected_rows_set.add(idx)
        for col in df.columns:
            affected_columns_set.add(col)

        issue_type_count["duplicate_row"] = issue_type_count.get("duplicate_row", 0) + 1
        severity_count["critical"] += 1

        if len(row_level_issues) >= 200:
            break

# Detect key conflicts (if primary key defined)
primary_key = parameters.get("primary_key")
if primary_key and primary_key in df.columns:
    key_groups = df.groupby(primary_key).size()
    for key_val, count in key_groups[key_groups > 1].items():
        conflict_rows = df[df[primary_key] == key_val].index.tolist()

        for idx in conflict_rows[1:]:  # Report all but first
            issue = {
                "row_index": idx,
                "column": primary_key,
                "issue_type": "key_conflict",
                "severity": "critical",
                "message": f"Primary key '{primary_key}' {key_val} conflicts with row {conflict_rows[0]}",
                "value": key_val,
                "conflicting_row": conflict_rows[0]
            }

            row_level_issues.append(issue)
            affected_rows_set.add(idx)
            affected_columns_set.add(primary_key)
            issue_type_count["key_conflict"] = issue_type_count.get("key_conflict", 0) + 1
            severity_count["critical"] += 1

            if len(row_level_issues) >= 200:
                break

    if len(row_level_issues) >= 200:
        break
```

### 5. governance_checker.py - POLICY VIOLATIONS

```python
# ==================== ROW-LEVEL-ISSUES GENERATION ====================
row_level_issues = []
affected_rows_set = set()
affected_columns_set = set()
issue_type_count = {}
severity_count = {"critical": 0, "warning": 0, "info": 0}

# Get governance policies
pii_fields = parameters.get("pii_fields", [])
restricted_fields = parameters.get("restricted_fields", [])
required_fields = parameters.get("required_fields", [])

# Check for PII in wrong columns
for col in pii_fields:
    if col in df.columns:
        for idx, value in df[col].items():
            if pd.notna(value):
                issue = {
                    "row_index": idx,
                    "column": col,
                    "issue_type": "policy_violation",
                    "severity": "critical",
                    "message": f"PII field '{col}' contains sensitive data: {str(value)[:20]}...",
                    "value": str(value)[:50],
                    "policy": "PII Protection"
                }

                row_level_issues.append(issue)
                affected_rows_set.add(idx)
                affected_columns_set.add(col)
                issue_type_count["policy_violation"] = issue_type_count.get("policy_violation", 0) + 1
                severity_count["critical"] += 1

                if len(row_level_issues) >= 200:
                    break

    if len(row_level_issues) >= 200:
        break

# Check for missing required fields
for col in required_fields:
    if col in df.columns:
        for idx, value in df[col].items():
            if pd.isna(value):
                issue = {
                    "row_index": idx,
                    "column": col,
                    "issue_type": "policy_violation",
                    "severity": "critical",
                    "message": f"Required field '{col}' is missing",
                    "policy": "Required Fields"
                }

                row_level_issues.append(issue)
                affected_rows_set.add(idx)
                affected_columns_set.add(col)
                issue_type_count["policy_violation"] = issue_type_count.get("policy_violation", 0) + 1
                severity_count["critical"] += 1

                if len(row_level_issues) >= 200:
                    break

    if len(row_level_issues) >= 200:
        break
```

---

## Transformer Integration Template

### profile_my_data_transformer.py Integration

```python
def transform_profile_my_data_response(
    agent_results: Dict[str, Any],
    execution_time_ms: int,
    analysis_id: str
) -> Dict[str, Any]:
    """Consolidate agent outputs including row-level-issues."""

    # ==================== CONSOLIDATE ALL OUTPUTS ====================

    all_alerts = []
    all_issues = []
    all_recommendations = []
    all_row_level_issues = []  # NEW
    agent_executive_summaries = []
    agent_ai_analysis_texts = []

    # Track summary stats
    issue_type_count = {}
    severity_count = {"critical": 0, "warning": 0, "info": 0}
    affected_rows_set = set()
    affected_columns_set = set()

    for agent_id, agent_output in agent_results.items():
        if agent_output.get("status") == "success":
            all_alerts.extend(agent_output.get("alerts", []))
            all_issues.extend(agent_output.get("issues", []))
            all_recommendations.extend(agent_output.get("recommendations", []))

            # NEW: Consolidate row-level-issues
            row_level_issues = agent_output.get("row_level_issues", [])
            all_row_level_issues.extend(row_level_issues)

            # Aggregate summary stats
            for issue in row_level_issues:
                issue_type = issue.get("issue_type", "unknown")
                issue_type_count[issue_type] = issue_type_count.get(issue_type, 0) + 1
                severity_count[issue.get("severity", "info")] += 1
                affected_rows_set.add(issue.get("row_index"))
                affected_columns_set.add(issue.get("column"))

            agent_executive_summaries.extend(agent_output.get("executive_summary", []))

            agent_ai_text = agent_output.get("ai_analysis_text", "")
            if agent_ai_text:
                agent_ai_analysis_texts.append(agent_ai_text)

    # ==================== CALCULATE ISSUE SUMMARY ====================
    aggregated_issue_summary = {
        "total_issues": len(all_row_level_issues),
        "by_type": issue_type_count,
        "by_severity": severity_count,
        "affected_rows": len(affected_rows_set),
        "affected_columns": sorted(list(affected_columns_set))
    }

    # Cap row-level-issues at reasonable limit for API response
    MAX_ISSUES = 500
    if len(all_row_level_issues) > MAX_ISSUES:
        # Sort by severity (critical first) then by row index
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        all_row_level_issues.sort(
            key=lambda x: (
                severity_order.get(x.get("severity"), 3),
                x.get("row_index", float('inf'))
            )
        )
        all_row_level_issues = all_row_level_issues[:MAX_ISSUES]

    # ==================== BUILD EXECUTIVE SUMMARY ====================
    executive_summary = []

    # ... existing executive summary code ...

    # NEW: Add row-level-issues summary
    executive_summary.append({
        "summary_id": "exec_row_level_issues",
        "title": "Row-Level Issues Detected",
        "value": f"{len(all_row_level_issues)}",
        "status": "success" if len(all_row_level_issues) == 0 else "warning" if len(all_row_level_issues) < 50 else "critical",
        "description": f"{len(all_row_level_issues)} data quality issues detected at individual row level"
    })

    # ==================== RETURN UNIFIED RESPONSE ====================

    return {
        "status": "success",
        "analysis_id": analysis_id,
        "timestamp": datetime.now().isoformat(),
        "execution_time_ms": execution_time_ms,

        # Original fields
        "alerts": all_alerts,
        "issues": all_issues,
        "recommendations": all_recommendations,
        "executive_summary": executive_summary,
        "ai_analysis_text": " ".join(agent_ai_analysis_texts),

        # NEW: Row-level details
        "row_level_issues": all_row_level_issues,
        "issue_summary": aggregated_issue_summary,

        # Downloads
        "downloads": ProfileMyDataDownloads.generate_downloads(
            alerts=all_alerts,
            issues=all_issues,
            recommendations=all_recommendations,
            row_level_issues=all_row_level_issues,  # NEW
            executive_summary=executive_summary,
            analysis_id=analysis_id
        )
    }
```

---

## Quick Reference Checklist

### Per Agent Implementation

- [ ] **Analysis Phase**

  - [ ] Read complete agent code
  - [ ] Understand detection mechanisms
  - [ ] Identify row-level issues the agent can detect

- [ ] **Implementation Phase**

  - [ ] Add row_level_issues list initialization
  - [ ] Add issue detection loop(s)
  - [ ] Populate required fields (row_index, column, issue_type, severity, message)
  - [ ] Add optional fields (value, bounds, etc.) where relevant
  - [ ] Calculate issue_summary metadata
  - [ ] Add row_level_issues to return statement

- [ ] **Validation Phase**
  - [ ] Syntax check passes
  - [ ] Row indices are valid
  - [ ] Severity values are correct
  - [ ] Issue types match expected types
  - [ ] Bounds make logical sense
  - [ ] Total issues <= 200

### Per Transformer Implementation

- [ ] **Analysis Phase**

  - [ ] Understand current agent aggregation logic
  - [ ] Identify consolidation patterns

- [ ] **Implementation Phase**

  - [ ] Add row_level_issues extraction from agent results
  - [ ] Add issue_summary calculation logic
  - [ ] Update response structure with new fields

- [ ] **Validation Phase**
  - [ ] Syntax check passes
  - [ ] Issue summary calculations correct
  - [ ] Response includes both row_level_issues and issue_summary

---

**Version**: 1.0  
**Created**: November 19, 2025  
**Templates Updated**: Ready for implementation
