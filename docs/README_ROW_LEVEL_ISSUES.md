# Row-Level-Issues Implementation Project - Complete Package

**Version**: 2.0 (Row-Level-Issues Focus)  
**Created**: November 19, 2025  
**Status**: ✅ DOCUMENTATION COMPLETE - Ready to Begin Phase 1 Implementation

---

## 📦 What's Included in This Package

### 1. **TASK.md** (Main Project Document)

- **Location**: `TASK.md`
- **Purpose**: Comprehensive task tracking and progress management
- **Contents**:
  - Executive summary and objectives
  - Row-level-issues schema definition
  - Implementation workflow (3 phases)
  - Detailed breakdown of all 14 agents (Phase 1)
  - Transformer integration requirements (Phase 2)
  - Validation & testing phase (Phase 3)
  - Current progress tracking
  - Delivery checklist (23 items)
  - Performance guidelines and notes

**Key Sections**:

- Executive Summary & Success Criteria
- Row-Level-Issues Schema (with examples)
- Issue Types by Agent (comprehensive table)
- Implementation Workflow (3 phases)
- Current Progress (updated in real-time)
- Delivery Checklist (0/23 complete)

### 2. **ROW_LEVEL_ISSUES_SCHEMA.md** (Schema Reference)

- **Location**: `docs/ROW_LEVEL_ISSUES_SCHEMA.md`
- **Purpose**: Complete schema documentation and reference guide
- **Contents**:
  - Data structure definitions (JSON/Python format)
  - Complete row-level-issue object structure
  - Aggregated response structure
  - Severity levels explanation
  - Frontend component integration details
  - Issue types by agent (with examples)
  - Implementation checklist template
  - Performance guidelines
  - Common mistakes to avoid
  - Full working examples for each agent type

**Key Features**:

- Copy-paste ready data structures
- Severity color codes matching frontend
- Frontend component expectations
- 4 working examples by agent type
- Schema validation rules

### 3. **ROW_LEVEL_ISSUES_IMPLEMENTATION_TEMPLATE.md** (Code Templates)

- **Location**: `docs/ROW_LEVEL_ISSUES_IMPLEMENTATION_TEMPLATE.md`
- **Purpose**: Ready-to-use code templates and patterns
- **Contents**:
  - Generic agent template (copy and customize)
  - 5 agent-specific implementations:
    - unified_profiler.py (outlier detection)
    - outlier_remover.py (bounds extraction)
    - type_fixer.py (type mismatches)
    - duplicate_resolver.py (duplicate detection)
    - governance_checker.py (policy violations)
  - Transformer integration template
  - Quick reference checklist

**Key Features**:

- Production-ready code snippets
- Customizable for each agent
- Comments explaining each section
- Follows standardized schema exactly
- Transformer consolidation pattern

---

## 🎯 Project Scope

### Phase 1: Agent Expansion (14 agents)

Each agent needs to be enhanced with row-level-issues detection:

1. **unified_profiler.py** - Detect outliers, nulls, type mismatches, distribution anomalies
2. **drift_detector.py** - Detect drift, distribution shifts, range changes
3. **null_handler.py** - Detect nulls, null patterns, anomalies
4. **outlier_remover.py** - Detect outliers with bounds, extreme values
5. **type_fixer.py** - Detect type mismatches, format violations
6. **field_standardization.py** - Detect format violations, inconsistencies
7. **duplicate_resolver.py** - Detect duplicates, key conflicts
8. **governance_checker.py** - Detect policy violations, compliance issues
9. **score_risk.py** - Detect high-risk rows, PII exposure, compliance violations
10. **readiness_rater.py** - Detect low readiness scores, validation failures
11. **test_coverage_agent.py** - Detect coverage gaps, untested edge cases
12. **cleanse_previewer.py** - Detect simulation failures, unsafe operations
13. **cleanse_writeback.py** - Detect write failures, integrity violations
14. **quarantine_agent.py** - Detect quarantine flags, suspicious rows

**Estimated Effort**: 46-56 hours (3-4 hours each)

### Phase 2: Transformer Integration (2 transformers)

Consolidate row-level-issues from all agents:

1. **profile_my_data_transformer.py** - Aggregate profiling agent results
2. **clean_my_data_transformer.py** - Aggregate cleaning agent results

**Estimated Effort**: 4-6 hours total

### Phase 3: Validation & Testing

- Syntax validation for all 16 Python files
- Data structure validation
- Frontend integration testing

**Estimated Effort**: 4-5 hours total

**Total Project Effort**: 55-68 hours  
**Recommended Timeline**: 3-4 weeks with concurrent agent implementations

---

## 📋 Row-Level-Issues Schema (Quick Reference)

### Single Issue Structure

```python
{
    "row_index": int,              # Row number in dataset
    "column": str,                 # Column/field name
    "issue_type": str,             # Type of issue
    "severity": str,               # "critical" | "warning" | "info"
    "message": str,                # Human-readable description
    "value": Any,                  # Actual value (optional)
    "bounds": {                    # For outlier issues (optional)
        "lower": float,
        "upper": float
    }
}
```

### Response Structure

```python
{
    "row_level_issues": [...],     # Array of issues (max 200 per agent)
    "issue_summary": {
        "total_issues": int,
        "by_type": {...},
        "by_severity": {...},
        "affected_rows": int,
        "affected_columns": [...]
    }
}
```

### Severity Levels

- **critical** (Red #ef4444) - Data integrity risk
- **warning** (Orange #f59e0b) - Quality concern
- **info** (Blue #3b82f6) - Informational only

---

## 🚀 How to Get Started

### Step 1: Understand the Schema

1. Read `ROW_LEVEL_ISSUES_SCHEMA.md` completely
2. Review example structures for your agent type
3. Understand the frontend expectations

### Step 2: Pick Your First Agent

Start with **unified_profiler.py** as it's most straightforward:

1. Read the complete agent code
2. Understand how it detects outliers, nulls, type mismatches
3. Use templates from `ROW_LEVEL_ISSUES_IMPLEMENTATION_TEMPLATE.md`

### Step 3: Implement Row-Level Logic

1. Copy the generic template
2. Customize for your agent's detection methods
3. Follow the checklist in TASK.md for your agent
4. Iterate through dataset collecting issues

### Step 4: Calculate Summary

1. Count issues by type
2. Count issues by severity
3. Collect unique affected rows and columns
4. Return both arrays in response

### Step 5: Validate

1. Check Python syntax passes
2. Verify JSON schema matches expected structure
3. Ensure all required fields present
4. Cap at 200 issues per agent

### Step 6: Move to Next Agent

Repeat steps 2-5 for remaining 13 agents

### Step 7: Integrate Transformers

1. Consolidate row-level-issues from all agents
2. Calculate aggregated issue_summary
3. Include in response structure

### Step 8: Final Testing

1. Validate all files pass syntax check
2. Test response structure
3. Verify frontend integration

---

## 📊 Progress Tracking

### Update TASK.md as You Complete

For each agent, update:

```markdown
#### X. `agents/[AGENT_NAME].py` - ✅ COMPLETED

**Analysis Status**: ✅ ANALYZED  
**Implementation Status**: ✅ COMPLETED

**Row-Level Issues Detected**: [List issue types]

**Example Issue**:
{
"row_index": ...,
"column": "...",
...
}

**Key Metrics**:

- Total issues per test dataset: [number]
- Severity distribution: critical [X], warning [Y], info [Z]
- Affected rows: [number]
- Affected columns: [list]

**Validation**: ✅ PASSED
```

### Real-Time Checklist

- [x] Schema documentation created
- [ ] Agent 1 (unified_profiler.py) - Analyze
- [ ] Agent 1 - Implement
- [ ] Agent 1 - Validate
- [ ] Agents 2-14 (same workflow)
- [ ] Transformer 1 integration
- [ ] Transformer 2 integration
- [ ] Final validation & testing

---

## 🔗 File Dependencies

```
TASK.md (main tracker)
├── docs/ROW_LEVEL_ISSUES_SCHEMA.md (reference)
├── docs/ROW_LEVEL_ISSUES_IMPLEMENTATION_TEMPLATE.md (code patterns)
├── agents/[14 agent files] (Phase 1 - expand each)
├── transformers/profile_my_data_transformer.py (Phase 2)
├── transformers/clean_my_data_transformer.py (Phase 2)
└── docs/README_ROW_LEVEL_ISSUES.md (this file)
```

---

## ✅ Success Criteria

By project completion:

1. ✅ All 14 agents generate `row_level_issues` array
2. ✅ Each issue includes all required fields
3. ✅ Severity values are valid ("critical", "warning", "info")
4. ✅ Issue types match agent-specific definitions
5. ✅ Row indices are valid dataset indices
6. ✅ Bounds make logical sense (lower < upper)
7. ✅ Issues capped at 200 per agent
8. ✅ `issue_summary` includes all required fields
9. ✅ Transformers consolidate all agent issues
10. ✅ All Python files pass syntax validation
11. ✅ Response structures match frontend expectations
12. ✅ RowLevelIssuesSection.jsx component receives correct data

---

## 💡 Tips for Success

### Implementation Tips

1. **Start simple** - Begin with null and outlier detection
2. **Use templates** - Copy-paste code templates, customize
3. **Iterate incrementally** - 1-2 agents per day is realistic
4. **Test frequently** - Validate after each agent
5. **Track progress** - Update TASK.md after each agent

### Performance Tips

1. **Cap at 200 issues** - Prevent memory issues
2. **Use generators** - For large datasets
3. **Pre-calculate** - Summary stats in single pass
4. **Sort by relevance** - Critical issues first
5. **Cache results** - Avoid redundant calculations

### Debugging Tips

1. **Check row indices** - Must exist in dataset
2. **Validate column names** - Must match dataset
3. **Verify bounds** - lower < upper always
4. **Print first issue** - Verify structure correct
5. **Test with small dataset** - 100-1000 rows first

---

## 📞 Common Questions

### Q: How many row-level-issues per agent?

**A**: Typically 30-200 per agent depending on data quality. Cap at 200 for API performance.

### Q: What if my agent doesn't detect row-level issues?

**A**: Return empty `row_level_issues` array with `issue_summary` all zeros. This is valid.

### Q: Should row_index be 0-based or 1-based?

**A**: Match your dataset convention. Usually 0-based (pandas default).

### Q: How do I calculate affected_rows?

**A**: Count unique row_index values across all issues: `len(set([issue["row_index"] for issue in issues]))`

### Q: Can I include custom fields in issues?

**A**: Yes! Add agent-specific fields (e.g., `"confidence": 0.95`, `"detection_method": "iqr"`). Required fields are: row_index, column, issue_type, severity, message.

### Q: What if transformers crash?

**A**: Check that agent outputs include `row_level_issues` key. If missing, transformer will fail.

---

## 📚 Additional Resources

### Reference Files

- `docs/ROW_LEVEL_ISSUES_SCHEMA.md` - Full schema documentation
- `docs/ROW_LEVEL_ISSUES_IMPLEMENTATION_TEMPLATE.md` - Code templates
- `docs/ALERTS_ISSUES_RECOMMENDATIONS_STRUCTURE.md` - Existing schema reference

### Related Components

- `rough/RowLevelIssuesSection.jsx` - Frontend component (reference)
- `agents/*.py` - All 14 agent files (Phase 1 targets)
- `transformers/*.py` - Both transformer files (Phase 2 targets)

---

## 🎯 Next Action

**Ready to begin?**

1. ✅ Read `ROW_LEVEL_ISSUES_SCHEMA.md` (30 min)
2. ✅ Review `ROW_LEVEL_ISSUES_IMPLEMENTATION_TEMPLATE.md` (30 min)
3. ✅ Start with `agents/unified_profiler.py` (3-4 hours)
4. ✅ Update TASK.md with completion
5. ✅ Move to next agent

**Estimated project completion**: December 15-20, 2025 (with concurrent implementation)

---

**Project Package Created**: November 19, 2025  
**Status**: ✅ Documentation Complete - Implementation Ready  
**Next Phase**: Begin Agent 1 (unified_profiler.py) Analysis and Implementation
