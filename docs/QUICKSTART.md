# QUICKSTART.md - Row-Level-Issues Implementation

**Quick Reference for Developers**  
**Version**: 1.0  
**Created**: November 19, 2025

---

## 📋 TL;DR - What You Need to Know

### What is Row-Level-Issues?

A new field in all agent responses that captures granular, row-by-row data quality issues. Think of it as **field-level issues but at the individual row level** with row indices and actual values.

### Why Add It?

Frontend has a `RowLevelIssuesSection.jsx` component ready to display this data. This connects backend data quality detection to user-facing row-level issue reports.

### How Long?

- **Per Agent**: 3-4 hours (14 agents = 46-56 hours)
- **Transformers**: 4-6 hours (2 files)
- **Testing**: 4-5 hours
- **Total**: 55-68 hours (~3-4 weeks with concurrent work)

---

## 🚀 5-Minute Setup

### 1. Read These (30 minutes)

```
docs/ROW_LEVEL_ISSUES_SCHEMA.md         → Understand schema
docs/ROW_LEVEL_ISSUES_IMPLEMENTATION_TEMPLATE.md  → See code examples
```

### 2. Copy This Template (5 minutes)

From `ROW_LEVEL_ISSUES_IMPLEMENTATION_TEMPLATE.md`, copy the **Generic Agent Template**

### 3. Customize for Your Agent (depends on agent)

- Replace `[agent_function_name]` with your function name
- Replace `[agent_name]` with your agent ID
- Customize the detection logic for your agent type

### 4. Test (30 minutes)

```bash
python -m py_compile agents/your_agent.py  # Syntax check
# Test with small CSV to verify output structure
```

### 5. Mark Complete in TASK.md

Update agent section to show ✅ COMPLETED

---

## 📦 Expected Output Structure

### Minimal Valid Response

```python
{
    "status": "success",
    "row_level_issues": [],  # Empty is OK if no issues
    "issue_summary": {
        "total_issues": 0,
        "by_type": {},
        "by_severity": {"critical": 0, "warning": 0, "info": 0},
        "affected_rows": 0,
        "affected_columns": []
    }
    # ... other fields unchanged
}
```

### With Issues

```python
{
    "status": "success",
    "row_level_issues": [
        {
            "row_index": 5,
            "column": "age",
            "issue_type": "outlier",
            "severity": "warning",
            "message": "Value 156 exceeds upper bound 100",
            "value": 156,
            "bounds": {"lower": 18, "upper": 100}
        },
        # ... more issues (max 200)
    ],
    "issue_summary": {
        "total_issues": 245,
        "by_type": {"outlier": 120, "null": 85, "type_mismatch": 40},
        "by_severity": {"critical": 45, "warning": 150, "info": 50},
        "affected_rows": 180,
        "affected_columns": ["age", "email", "salary"]
    }
    # ... other fields unchanged
}
```

---

## 🔧 Implementation Pattern

### Basic Loop Pattern (All Agents Use This)

```python
row_level_issues = []
affected_rows_set = set()
affected_columns_set = set()
issue_type_count = {}
severity_count = {"critical": 0, "warning": 0, "info": 0}

for idx, row in df.iterrows():
    # YOUR DETECTION LOGIC HERE
    if issue_detected:
        issue = {
            "row_index": idx,
            "column": "column_name",
            "issue_type": "issue_type",  # MUST be one of your agent's types
            "severity": "critical|warning|info",  # MUST be one of these
            "message": "Human readable description"
        }

        # Add optional fields as needed
        issue["value"] = row["column_name"]  # What triggered issue
        issue["bounds"] = {"lower": 0, "upper": 100}  # For outliers

        # Collect metrics
        row_level_issues.append(issue)
        affected_rows_set.add(idx)
        affected_columns_set.add("column_name")
        issue_type_count[issue["issue_type"]] = issue_type_count.get(...) + 1
        severity_count[issue["severity"]] += 1

        # Stop at 200
        if len(row_level_issues) >= 200:
            break

# Calculate summary
issue_summary = {
    "total_issues": len(row_level_issues),
    "by_type": issue_type_count,
    "by_severity": severity_count,
    "affected_rows": len(affected_rows_set),
    "affected_columns": sorted(list(affected_columns_set))
}

# Return as part of response
return {
    "status": "success",
    # ... other fields ...
    "row_level_issues": row_level_issues,
    "issue_summary": issue_summary
}
```

---

## ✅ Validation Checklist (Before Marking Done)

- [ ] Python syntax check passes: `python -m py_compile agents/your_agent.py`
- [ ] Returns both `row_level_issues` and `issue_summary`
- [ ] `row_level_issues` is a list (even if empty `[]`)
- [ ] Each issue has required fields: row_index, column, issue_type, severity, message
- [ ] Severity is one of: "critical", "warning", "info" (lowercase)
- [ ] Row indices are valid (exist in dataset)
- [ ] Column names match actual columns
- [ ] Total issues ≤ 200
- [ ] `issue_summary.total_issues` matches count of items in `row_level_issues`
- [ ] `issue_summary.by_severity` counts add up correctly
- [ ] Optional fields (value, bounds, etc.) are included where relevant
- [ ] No syntax errors when running

---

## 🎯 Agent-Specific Issue Types

### Quick Reference Table

| Agent                     | Issue Types                                                   | Example                                                                                                                  |
| ------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **unified_profiler**      | null, outlier, type_mismatch, distribution_anomaly            | `{row_index: 5, column: "age", issue_type: "outlier", severity: "warning", value: 156, bounds: {lower: 18, upper: 100}}` |
| **drift_detector**        | drift_detected, distribution_shift, value_range_change        | `{row_index: 10, column: "sales", issue_type: "drift_detected", severity: "high"}`                                       |
| **null_handler**          | null, null_pattern, missing_data_anomaly                      | `{row_index: 3, column: "email", issue_type: "null", severity: "info"}`                                                  |
| **outlier_remover**       | outlier, extreme_value, statistical_anomaly                   | `{row_index: 12, column: "age", issue_type: "extreme_value", severity: "critical", value: 999}`                          |
| **type_fixer**            | type_mismatch, format_violation, semantic_type_mismatch       | `{row_index: 8, column: "date", issue_type: "format_violation", severity: "critical"}`                                   |
| **field_standardization** | format_violation, inconsistent_format, standardization_needed | `{row_index: 15, column: "phone", issue_type: "inconsistent_format", severity: "warning"}`                               |
| **duplicate_resolver**    | duplicate_row, partial_duplicate, key_conflict                | `{row_index: 20, column: "id", issue_type: "key_conflict", severity: "critical"}`                                        |
| **governance_checker**    | policy_violation, compliance_issue, naming_violation          | `{row_index: 7, column: "ssn", issue_type: "policy_violation", severity: "critical"}`                                    |
| **score_risk**            | risk_high, pii_exposure, compliance_violation                 | `{row_index: 25, column: "email", issue_type: "pii_exposure", severity: "critical"}`                                     |
| **readiness_rater**       | readiness_low, validation_failed, quality_gate_failed         | `{row_index: 4, column: "status", issue_type: "quality_gate_failed", severity: "warning"}`                               |
| **test_coverage_agent**   | test_coverage_gap, validation_missing, edge_case_uncovered    | `{row_index: 11, column: "value", issue_type: "edge_case_uncovered", severity: "info"}`                                  |
| **cleanse_previewer**     | simulation_failed, unsafe_operation, high_impact_change       | `{row_index: 6, column: "salary", issue_type: "high_impact_change", severity: "warning"}`                                |
| **cleanse_writeback**     | writeback_failed, integrity_violation, rollback_needed        | `{row_index: 13, column: "status", issue_type: "writeback_failed", severity: "critical"}`                                |
| **quarantine_agent**      | quarantine_flagged, suspicious_row, data_anomaly              | `{row_index: 18, column: "transaction", issue_type: "suspicious_row", severity: "critical"}`                             |

---

## 🐛 Common Issues & Fixes

### ❌ "KeyError: 'issue_summary' in transformer"

**Cause**: Agent didn't return `issue_summary`  
**Fix**: Add to return statement:

```python
return {
    ...
    "row_level_issues": row_level_issues,
    "issue_summary": issue_summary  # ADD THIS
}
```

### ❌ "Severity 'HIGH' not recognized"

**Cause**: Used uppercase instead of lowercase  
**Fix**: Use lowercase only:

```python
"severity": "critical"  # ✅ Correct
"severity": "CRITICAL"  # ❌ Wrong
```

### ❌ "Row index 1000 doesn't exist"

**Cause**: DataFrame only has 500 rows, but using wrong index  
**Fix**: Check your iteration:

```python
for idx, row in df.iterrows():  # idx is 0-based, valid
```

### ❌ "bounds.lower > bounds.upper"

**Cause**: Swapped lower and upper  
**Fix**: Check logic:

```python
"bounds": {"lower": min_val, "upper": max_val}  # ✅ Correct
"bounds": {"lower": max_val, "upper": min_val}  # ❌ Wrong
```

### ❌ "1000 issues returned, frontend slow"

**Cause**: Didn't cap at 200  
**Fix**: Add check:

```python
if len(row_level_issues) >= 200:
    break
```

---

## 🔗 Key Files (Bookmark These!)

```
📄 TASK.md
   └─ Main project tracker, update as you complete agents

📂 docs/
   ├─ ROW_LEVEL_ISSUES_SCHEMA.md
   │  └─ Schema definition, examples, validation rules
   ├─ ROW_LEVEL_ISSUES_IMPLEMENTATION_TEMPLATE.md
   │  └─ Code templates, 5 agent examples, patterns
   ├─ README_ROW_LEVEL_ISSUES.md
   │  └─ Complete project overview
   └─ QUICKSTART.md (THIS FILE)
      └─ Quick reference, checklists, common issues

🐍 agents/
   ├─ [14 agent files to expand]
   └─ Each needs row_level_issues added

🔄 transformers/
   ├─ profile_my_data_transformer.py
   └─ clean_my_data_transformer.py
      └─ Both need consolidation logic
```

---

## 📊 Progress Tracking

### Update TASK.md After Each Agent

```markdown
### ✅ 1. `agents/unified_profiler.py` - COMPLETED

**Analysis Status**: ✅ ANALYZED  
**Implementation Status**: ✅ COMPLETED

**Row-Level Issues Types**: null, outlier, type_mismatch, distribution_anomaly

**Validation**: ✅ PASSED
```

### Running Checklist

1. [ ] Read schema docs (30 min)
2. [ ] Setup first agent (30 min)
3. [ ] Implement agents 1-4 (12-16 hours)
4. [ ] Implement agents 5-8 (12-16 hours)
5. [ ] Implement agents 9-12 (12-16 hours)
6. [ ] Implement agents 13-14 (6-8 hours)
7. [ ] Implement transformers (4-6 hours)
8. [ ] Final testing (4-5 hours)

---

## 💬 Quick FAQ

**Q: Can I skip an agent?**  
A: No, all 14 must be done before transformers work.

**Q: What's a realistic daily pace?**  
A: 1-2 agents per day if working full-time on this.

**Q: Do I need the bounds field?**  
A: Only for outlier detection agents. Optional for others.

**Q: Can I test without frontend?**  
A: Yes! Just validate Python syntax and JSON structure.

**Q: What if my agent finds 0 issues?**  
A: Still return empty arrays. That's valid.

---

## 🎬 Ready? Start Here

### Next 15 Minutes:

1. Open `docs/ROW_LEVEL_ISSUES_SCHEMA.md` → Understand schema
2. Open `docs/ROW_LEVEL_ISSUES_IMPLEMENTATION_TEMPLATE.md` → Copy template
3. Open `agents/unified_profiler.py` → Start implementation

### After Implementing First Agent:

1. Update `TASK.md` to mark completed
2. Move to Agent 2
3. Repeat

### After All14 Agents:

1. Implement transformers
2. Final validation
3. Deploy!

---

**Status**: Ready to begin Phase 1 agent implementation  
**First Agent Recommended**: `agents/unified_profiler.py` (most straightforward)  
**Estimated Time per Agent**: 3-4 hours  
**Total Estimated Project**: 55-68 hours (3-4 weeks concurrent)

**Let's go! 🚀**
