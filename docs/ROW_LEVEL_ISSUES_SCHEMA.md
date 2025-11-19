"""
ROW_LEVEL_ISSUES_SCHEMA.md

Comprehensive documentation for row-level-issues field implementation.
Reference: RowLevelIssuesSection.jsx component from frontend project
"""

# Row-Level-Issues Implementation Guide

## Overview

The `row_level_issues` field is a new requirement for all 14 agents in AgensiumBackendV2. It captures granular, row-by-row data quality issues that complement the existing field-level alerts, field-level issues, and recommendations.

## Data Structure

### Complete Row-Level-Issue Object

```python
{
    # REQUIRED FIELDS
    "row_index": int,                          # Row number (0-based index)
    "column": str,                             # Column/field name
    "issue_type": str,                         # Type of issue detected
    "severity": str,                           # "critical" | "warning" | "info"
    "message": str,                            # Human-readable description

    # OPTIONAL FIELDS (context-dependent)
    "value": Any,                              # Actual value causing issue
    "bounds": {                                # For outlier/range issues
        "lower": float,                        # Lower acceptable bound
        "upper": float                         # Upper acceptable bound
    },

    # AGENT-SPECIFIC OPTIONAL FIELDS
    "confidence": float,                       # 0-1 confidence score
    "remediation_priority": str,               # "immediate" | "high" | "medium" | "low"
    "detection_method": str,                   # How it was detected
    "timestamp": str,                          # Detection timestamp (ISO 8601)
}
```

### Aggregated Response Structure

```python
{
    # ... existing agent response fields ...

    "row_level_issues": [
        # Array of issue objects (max 200 items per agent)
        {
            "row_index": 0,
            "column": "age",
            "issue_type": "outlier",
            "severity": "warning",
            "message": "Value 156 is outside normal range",
            "value": 156,
            "bounds": {"lower": 18, "upper": 100}
        },
        # ... more issues ...
    ],

    "issue_summary": {
        "total_issues": 245,                   # Total count across all rows
        "by_type": {                           # Distribution by type
            "outlier": 120,
            "null": 85,
            "type_mismatch": 30,
            "duplicate": 10
        },
        "by_severity": {                       # Distribution by severity
            "critical": 45,
            "warning": 150,
            "info": 50
        },
        "affected_rows": 180,                  # Count of unique rows with issues
        "affected_columns": ["age", "email", "salary", "phone"]  # Columns with issues
    }
}
```

## Severity Levels

### Critical (Red - #ef4444)

- **Meaning**: Data integrity risk, prevents processing
- **Action**: Must be resolved before pipeline continuation
- **Examples**: Type mismatches, integrity violations, critical compliance breaches
- **Expected Count**: 10-50 per agent (varies by agent type)

### Warning (Orange - #f59e0b)

- **Meaning**: Quality concern, should be reviewed
- **Action**: Recommend resolution but not blocking
- **Examples**: Outliers, high null percentages, minor type conflicts
- **Expected Count**: 50-150 per agent

### Info (Blue - #3b82f6)

- **Meaning**: Informational, low priority
- **Action**: Informational only, no action required
- **Examples**: High cardinality fields, low anomaly scores, edge case detection
- **Expected Count**: 50-100 per agent

## Issue Types by Agent

### unified_profiler.py

- `null` - Individual null/missing values
- `outlier` - Values outside statistical bounds (IQR 1.5x)
- `type_mismatch` - Type conflicts between declared and actual
- `distribution_anomaly` - Values in low-probability areas
- `high_cardinality_issue` - Unique value concerns
- **Example**: Row 42, column "salary", issue_type: "outlier", severity: "warning", value: 450000, bounds: {lower: 25000, upper: 200000}

### drift_detector.py

- `drift_detected` - Individual rows showing drift
- `distribution_shift` - Values inconsistent with baseline
- `value_range_change` - Values outside historical range
- `statistical_anomaly` - Unusual statistical properties
- **Example**: Row 156, column "purchase_amount", issue_type: "drift_detected", severity: "high", message: "Value 5000 shows significant drift from baseline distribution"

### null_handler.py

- `null` - Null/missing values
- `null_pattern` - Suspicious null patterns
- `missing_data_anomaly` - Correlated nulls
- `high_null_percentage` - Rows with many nulls
- **Example**: Row 89, column "phone", issue_type: "null", severity: "info", message: "Missing value (NULL)"

### outlier_remover.py

- `outlier` - Values outside bounds
- `extreme_value` - Extremely unusual values
- `statistical_anomaly` - High anomaly score
- `potential_error` - Likely data entry error
- **Example**: Row 12, column "age", issue_type: "extreme_value", severity: "critical", value: 999, bounds: {lower: 0, upper: 120}

### type_fixer.py

- `type_mismatch` - Type conflicts
- `format_violation` - Format invalid
- `type_conflict` - Conflicting types
- `semantic_type_mismatch` - Semantic issues
- **Example**: Row 34, column "date", issue_type: "format_violation", severity: "critical", message: "Expected YYYY-MM-DD, got 'Jan 2024'"

### field_standardization.py

- `format_violation` - Incorrect format
- `inconsistent_format` - Inconsistent variants
- `standardization_needed` - Needs standardization
- `unit_mismatch` - Unit inconsistencies
- **Example**: Row 67, column "phone", issue_type: "inconsistent_format", severity: "warning", message: "Phone format (123-456-7890) differs from standard (123.456.7890)"

### duplicate_resolver.py

- `duplicate_row` - Exact duplicate
- `partial_duplicate` - Some fields match
- `key_conflict` - Primary key conflict
- `near_duplicate` - Fuzzy duplicate (>95% match)
- **Example**: Row 45, column "id", issue_type: "key_conflict", severity: "critical", message: "Primary key 'user_id' 12345 conflicts with row 23"

### governance_checker.py

- `policy_violation` - Policy breach
- `compliance_issue` - Compliance breach
- `naming_violation` - Naming convention issue
- `data_retention_violation` - Retention rule breach
- **Example**: Row 101, column "ssn", issue_type: "policy_violation", severity: "critical", message: "PII field detected in non-secure column"

### score_risk.py

- `risk_high` - High risk score
- `pii_exposure` - PII exposed
- `compliance_violation` - GDPR/HIPAA/CCPA breach
- `remediation_needed` - Needs remediation
- **Example**: Row 78, column "email", issue_type: "pii_exposure", severity: "critical", message: "Email exposed: Risk score 0.95 (GDPR violation)"

### readiness_rater.py

- `readiness_low` - Low readiness score
- `validation_failed` - Validation failed
- `quality_gate_failed` - Quality gate breach
- `completeness_issue` - Incomplete data
- **Example**: Row 99, column "dataset", issue_type: "quality_gate_failed", severity: "warning", message: "Readiness score 0.42 below threshold 0.60"

### test_coverage_agent.py

- `test_coverage_gap` - Coverage gap
- `validation_missing` - Validation missing
- `edge_case_uncovered` - Edge case not covered
- `format_edge_case` - Format edge case
- **Example**: Row 55, column "age", issue_type: "edge_case_uncovered", severity: "info", message: "Value -1 hits edge case not covered by tests"

### cleanse_previewer.py

- `simulation_failed` - Simulation error
- `unsafe_operation` - Unsafe cleaning
- `high_impact_change` - Major impact
- `preview_issue` - Preview problem
- **Example**: Row 20, column "salary", issue_type: "high_impact_change", severity: "warning", message: "Cleaning would reduce salary by 60%"

### cleanse_writeback.py

- `writeback_failed` - Write failed
- `integrity_violation` - Integrity broken
- `rollback_needed` - Needs rollback
- `write_conflict` - Conflict detected
- **Example**: Row 11, column "status", issue_type: "writeback_failed", severity: "critical", message: "Write failed: Foreign key constraint violation"

### quarantine_agent.py

- `quarantine_flagged` - Flagged for quarantine
- `suspicious_row` - Suspicious activity
- `data_anomaly` - Multiple anomalies
- `high_risk_flag` - High risk
- **Example**: Row 88, column "transaction", issue_type: "suspicious_row", severity: "critical", message: "Anomaly score 0.92: Multiple fraud indicators detected"

## Frontend Component Integration

### RowLevelIssuesSection.jsx Expectations

The frontend component expects this data structure:

```javascript
unifiedData = {
  rowLevelIssues: [
    {
      row_index: 0,
      column: "age",
      issue_type: "outlier",
      severity: "critical", // Must match filter logic
      message: "...",
      value: 156,
      bounds: { lower: 18, upper: 100 },
    },
    // ... more issues
  ],
  issueSummary: {
    total_issues: 245,
    by_type: {
      outlier: 120,
      null: 85,
      // ...
    },
    by_severity: {
      critical: 45,
      warning: 150,
      info: 50,
    },
  },
};
```

### Component Features Supported

1. **Filtering** - By severity (all, critical, warning, info)
2. **Statistics** - Total issues, by-type counts, severity distribution
3. **Charts** - Pie charts showing distribution by type and severity
4. **Table** - Sortable table with expand/collapse for details
5. **Details Panel** - Shows value, bounds, and all metadata on expand
6. **Empty State** - Shows when no issues for selected filter

## Implementation Checklist Template

For each agent file, follow this checklist:

```python
# AGENT ANALYSIS
# [ ] Read complete agent code (understand detection logic)
# [ ] Identify row-level issue types this agent detects
# [ ] Map row indices to detected issues
# [ ] Extract values and bounds where applicable

# IMPLEMENTATION
# [ ] Define row_level_issues array initialization
# [ ] Implement issue detection logic with row iteration
# [ ] Populate required fields: row_index, column, issue_type, severity, message
# [ ] Add optional fields: value, bounds, detection_method
# [ ] Implement issue_summary calculation:
#     - total_issues count
#     - by_type distribution
#     - by_severity distribution
#     - affected_rows set/count
#     - affected_columns list
# [ ] Add to return statement: "row_level_issues": row_level_issues, "issue_summary": issue_summary

# VALIDATION
# [ ] Check JSON schema matches expected structure
# [ ] Verify severity values are: critical | warning | info
# [ ] Verify all required fields present
# [ ] Cap issues at 200 max per agent
# [ ] Python syntax validation passes
```

## Performance Guidelines

### Memory Management

- Cap row-level-issues at 200 items per agent
- Use generators for large datasets if needed
- Pre-allocate lists when size known

### Computational Efficiency

- Calculate issue_summary in single pass through issues
- Use Counter for by_type/by_severity aggregation
- Use set for affected_rows deduplication

### Data Quality

- Validate row_index is within dataset bounds
- Ensure column name matches actual column
- Verify bounds make logical sense (lower < upper)

## Testing Checklist

Before marking agent complete:

1. **Unit Test** - Does agent generate row-level-issues?
2. **Schema Test** - Does output match JSON schema?
3. **Range Test** - Are counts reasonable (not 0, not >1000)?
4. **Severity Test** - Are severity levels valid?
5. **Row Index Test** - Do row indices exist in dataset?
6. **Summary Test** - Does summary math match actual issues?
7. **Syntax Test** - Does file pass Python syntax check?

## Common Mistakes to Avoid

❌ **Wrong**: Using 1-based indexing when dataset uses 0-based  
✅ **Right**: Match dataset's row indexing convention

❌ **Wrong**: Including all 50,000 issues when > 200  
✅ **Right**: Cap at 200, sort by severity/relevance

❌ **Wrong**: Severity values "HIGH" (wrong case)  
✅ **Right**: Use lowercase: "critical", "warning", "info"

❌ **Wrong**: Missing issue_summary field  
✅ **Right**: Always include summary with all required sub-fields

❌ **Wrong**: Bounds where lower > upper  
✅ **Right**: Validate bounds: lower < value < upper

❌ **Wrong**: Non-existent column names  
✅ **Right**: Use exact column names from dataset

## Examples by Agent Type

### Example 1: unified_profiler.py (Numeric Outlier)

```python
{
    "row_index": 42,
    "column": "salary",
    "issue_type": "outlier",
    "severity": "warning",
    "message": "Value 450000 exceeds upper bound of 200000 (IQR 1.5x method)",
    "value": 450000,
    "bounds": {"lower": 25000, "upper": 200000},
    "detection_method": "iqr_1.5x",
    "confidence": 0.95
}
```

### Example 2: duplicate_resolver.py (Key Conflict)

```python
{
    "row_index": 45,
    "column": "user_id",
    "issue_type": "key_conflict",
    "severity": "critical",
    "message": "Primary key 'user_id' 12345 also found at row 23 (exact match)",
    "value": 12345,
    "remediation_priority": "immediate",
    "detection_method": "exact_duplicate_key"
}
```

### Example 3: type_fixer.py (Format Violation)

```python
{
    "row_index": 34,
    "column": "birth_date",
    "issue_type": "format_violation",
    "severity": "critical",
    "message": "Expected format YYYY-MM-DD, got 'Jan 15, 2024'",
    "value": "Jan 15, 2024",
    "detection_method": "regex_format_check",
    "remediation_priority": "high"
}
```

### Example 4: null_handler.py (Null Value)

```python
{
    "row_index": 89,
    "column": "phone_number",
    "issue_type": "null",
    "severity": "info",
    "message": "Missing value (NULL)",
    "value": None,
    "detection_method": "null_check",
    "remediation_priority": "medium"
}
```

## Schema Validation Rules

```python
# REQUIRED FIELDS - Must always be present
assert isinstance(issue["row_index"], int)
assert isinstance(issue["column"], str)
assert isinstance(issue["issue_type"], str)
assert issue["severity"] in ["critical", "warning", "info"]
assert isinstance(issue["message"], str)

# OPTIONAL FIELDS - Include as relevant
assert "value" not in issue or issue["value"] is not None
assert "bounds" not in issue or (
    isinstance(issue["bounds"], dict) and
    "lower" in issue["bounds"] and
    "upper" in issue["bounds"]
)

# SUMMARY FIELDS
assert isinstance(summary["total_issues"], int)
assert isinstance(summary["by_type"], dict)
assert isinstance(summary["by_severity"], dict)
assert isinstance(summary["affected_rows"], int)
assert isinstance(summary["affected_columns"], list)
```

## Next Steps

1. **Start with unified_profiler.py** - Most straightforward for outliers/nulls
2. **Move to outlier_remover.py** - Add bounds extraction
3. **Continue with type_fixer.py** - Format violations
4. **Progress to domain-specific agents** - governance_checker, score_risk
5. **Finish with transformers** - Consolidation logic
6. **Validation phase** - Schema, syntax, data structure checks

---

**Created**: November 19, 2025  
**Version**: 1.0  
**Reference Component**: RowLevelIssuesSection.jsx  
**Target Completion**: December 15-20, 2025
