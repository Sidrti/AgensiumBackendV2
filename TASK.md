# Task: Add Row-Level-Issues Field to All 14 Agents + Integrate into Transformers

**Version:** 2.0  
**Last Updated:** November 19, 2025  
**Status:** ⏳ INITIATED (0/16 agents - 0%)  
**Task Owner:** Agensium Backend V2  
**Priority:** HIGH

---

## Executive Summary

### Task Objective

Enhance all 14 agents in the `agents/` folder by adding a new **row-level-issues** field. This field captures granular, row-by-row data quality issues detected by each agent. Additionally, integrate row-level-issues into both transformers (`clean_my_data_transformer.py` and `profile_my_data_transformer.py`) to consolidate and expose this data through the API.

### Key Deliverables

1. ✅ **Row-Level-Issues Schema Documentation** - Define standardized structure (COMPLETED - See below)
2. 🔄 **Agent Expansion** - Add row-level-issues code to all 14 agents (IN PROGRESS - 0/14)
3. 🔄 **Transformer Integration** - Update transformers to consolidate row-level-issues (PENDING - 0/2)
4. 🔄 **Frontend Ready** - Ensure data flows through to RowLevelIssuesSection.jsx component (PENDING)

### Success Criteria

- ✅ All 14 agents generate row-level-issues array with proper schema
- ✅ Each issue includes: `row_index`, `column`, `issue_type`, `severity`, `message`, `value`, `bounds` (where applicable)
- ✅ Row-level-issues aggregated in transformers with `issueSummary` metadata
- ✅ Frontend component receives complete `rowLevelIssues` and `issueSummary` data
- ✅ All files pass Python syntax validation
- ✅ All JSON structures match schema exactly

---

## Row-Level-Issues Schema

### Single Issue Object Structure

```python
{
    "row_index": int,              # Row number in dataset (0-indexed or 1-indexed based on convention)
    "column": str,                 # Column/field name where issue detected
    "issue_type": str,             # Type: "outlier", "null", "type_mismatch", "duplicate", "format_violation", etc.
    "severity": str,               # Severity level: "critical", "warning", "info"
    "message": str,                # Human-readable issue description
    "value": Any,                  # Actual value that triggered the issue (optional)
    "bounds": {                    # For outlier issues (optional)
        "lower": float,            # Lower acceptable bound
        "upper": float             # Upper acceptable bound
    },
    # Agent-specific fields as needed (detection_method, confidence, etc.)
}
```

### Aggregated Response Structure

```python
{
    "row_level_issues": [
        # Array of issue objects (limit 100-200 per agent)
    ],
    "issue_summary": {
        "total_issues": int,
        "by_type": {
            "outlier": int,
            "null": int,
            "type_mismatch": int,
            # ...
        },
        "by_severity": {
            "critical": int,
            "warning": int,
            "info": int
        },
        "affected_rows": int,
        "affected_columns": list
    }
}
```

### Severity Levels

- **critical** - Data integrity risk, prevents processing
- **warning** - Quality concern, may need attention
- **info** - Informational, low priority

### Issue Types by Agent

| Agent                     | Issue Types                                                         | Example Detection                                               |
| ------------------------- | ------------------------------------------------------------------- | --------------------------------------------------------------- |
| **unified_profiler**      | `null`, `outlier`, `type_mismatch`, `distribution_anomaly`          | Null %, IQR outliers, type conflicts, bimodal distributions     |
| **drift_detector**        | `drift_detected`, `distribution_shift`, `value_range_change`        | Statistical drift, KL divergence, range shifts                  |
| **null_handler**          | `null`, `null_pattern`, `missing_data_anomaly`                      | > 50% nulls, patterns in missing, correlated nulls              |
| **outlier_remover**       | `outlier`, `extreme_value`, `statistical_anomaly`                   | IQR method, Z-score, MAD, isolation forest results              |
| **type_fixer**            | `type_mismatch`, `format_violation`, `type_conflict`                | String in numeric, date format issues, semantic type mismatches |
| **field_standardization** | `format_violation`, `inconsistent_format`, `standardization_needed` | Case inconsistency, separator issues, unit mismatches           |
| **duplicate_resolver**    | `duplicate_row`, `partial_duplicate`, `key_conflict`                | Exact duplicates, near-duplicates, conflicting keys             |
| **governance_checker**    | `policy_violation`, `compliance_issue`, `naming_violation`          | Column naming, retention, PII handling violations               |
| **score_risk**            | `risk_high`, `compliance_violation`, `remediation_needed`           | PII exposure, GDPR/HIPAA/CCPA violations                        |
| **readiness_rater**       | `readiness_low`, `validation_failed`, `quality_gate_failed`         | Low scores per field, validation failures                       |
| **test_coverage_agent**   | `test_coverage_gap`, `validation_missing`, `edge_case_uncovered`    | Untested ranges, format edge cases                              |
| **cleanse_previewer**     | `simulation_failed`, `unsafe_operation`, `high_impact_change`       | Simulation errors, unsafe preview results                       |
| **cleanse_writeback**     | `writeback_failed`, `integrity_violation`, `rollback_needed`        | Write errors, integrity check failures                          |
| **quarantine_agent**      | `quarantine_flagged`, `suspicious_row`, `data_anomaly`              | High anomaly score, multiple issues in row                      |

---

## Implementation Workflow

### Phase 1: Agent Analysis & Implementation (14 agents)

Each agent requires:

1. **Complete Code Analysis** - Understand detection logic and data structures
2. **Row-Level Issue Identification** - Map what issues the agent can detect at row level
3. **Code Implementation** - Add row-level-issues generation logic
4. **Schema Validation** - Ensure output matches standardized structure
5. **Syntax Validation** - Python syntax check + JSON structure validation

### Phase 2: Transformer Integration (2 transformers)

Each transformer requires:

1. **Consolidation Logic** - Aggregate row-level-issues from all agents
2. **Summary Generation** - Calculate `issueSummary` metadata
3. **Response Structure** - Include `rowLevelIssues` and `issueSummary` in response
4. **Frontend Compatibility** - Ensure data structure matches RowLevelIssuesSection.jsx expectations

### Phase 3: Validation & Testing

- Syntax validation for all agent files
- JSON structure validation for responses
- Frontend integration test with mock data

---

## Current Progress

### Files Completed ✅ (PHASE 1 - AGENT ANALYSIS)

#### ✅ SCHEMA DOCUMENTATION

- **Status**: COMPLETED
- **Documentation**: Row-level-issues schema defined (see above)
- **Impact**: Ready for implementation across all agents

---

## Agents - Phase 1 Implementation (14/14)

### ⏳ 1. `agents/unified_profiler.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- How does it detect outliers? (IQR method, Z-score, etc.)
- How does it identify null patterns and distributions?
- What type conflicts does it detect?
- Can it detect bimodal/multimodal distributions?

**Row-Level Issues to Detect**:

- `null` - Individual null/missing values
- `outlier` - Values outside statistical bounds (IQR, Z-score)
- `type_mismatch` - Type conflicts between declared and actual
- `distribution_anomaly` - Values in low-probability areas
- `high_cardinality_issue` - Unique values in high-cardinality fields

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Identify row-level issue detection points
- [ ] Add row-level-issues array generation after analysis
- [ ] Calculate issue_summary metadata
- [ ] Validate against schema
- [ ] Syntax validation ✅
- [ ] Document row-level issue types detected

**Estimated Effort**: 3-4 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 2. `agents/drift_detector.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- How does drift detection work? (Statistical tests, comparison methods)
- What constitutes a "drift" at row level?
- How are distribution shifts detected?
- What value range changes are flagged?

**Row-Level Issues to Detect**:

- `drift_detected` - Individual rows showing drift characteristics
- `distribution_shift` - Values inconsistent with baseline distribution
- `value_range_change` - Values outside historical range
- `statistical_anomaly` - Values with unusual statistical properties

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Understand drift detection methodology
- [ ] Map row-level drift indicators
- [ ] Add row-level-issues array generation
- [ ] Calculate issue_summary with drift metrics
- [ ] Syntax validation ✅

**Estimated Effort**: 3-4 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 3. `agents/null_handler.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- How are null values detected and categorized?
- Are there patterns in missing data?
- How are null handling strategies determined?

**Row-Level Issues to Detect**:

- `null` - Individual null values
- `null_pattern` - Suspicious null patterns (e.g., all nulls in specific columns)
- `missing_data_anomaly` - Correlated missing data
- `high_null_percentage` - Rows with high null count

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Identify null detection patterns
- [ ] Map null handling strategies to row issues
- [ ] Add row-level-issues generation
- [ ] Calculate null-specific issue_summary
- [ ] Syntax validation ✅

**Estimated Effort**: 2-3 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 4. `agents/outlier_remover.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- What outlier detection methods are used? (IQR, Z-score, MAD, Isolation Forest, etc.)
- How are outliers scored?
- What threshold defines an outlier?

**Row-Level Issues to Detect**:

- `outlier` - Individual outlier values with bounds
- `extreme_value` - Extremely unusual values
- `statistical_anomaly` - Values with high anomaly scores
- `potential_error` - Likely data entry errors

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Understand outlier detection algorithms
- [ ] Extract outlier bounds (lower/upper)
- [ ] Add row-level-issues with bounds information
- [ ] Calculate outlier-specific issue_summary
- [ ] Syntax validation ✅

**Estimated Effort**: 3-4 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 5. `agents/type_fixer.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- How are type conflicts detected?
- What type checking methods are used?
- How are format violations identified?

**Row-Level Issues to Detect**:

- `type_mismatch` - Values not matching declared type
- `format_violation` - Values violating expected format
- `type_conflict` - Conflicting type indicators
- `semantic_type_mismatch` - Semantic type conflicts

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Identify type checking logic
- [ ] Map format validation rules
- [ ] Add row-level-issues for type violations
- [ ] Calculate type-specific issue_summary
- [ ] Syntax validation ✅

**Estimated Effort**: 3-4 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 6. `agents/field_standardization.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- What standardization rules are applied?
- How are format violations detected?
- What constitutes "inconsistent format"?

**Row-Level Issues to Detect**:

- `format_violation` - Values not matching standard format
- `inconsistent_format` - Values with variations (case, separators, etc.)
- `standardization_needed` - Values needing standardization
- `unit_mismatch` - Inconsistent units

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Identify standardization rules
- [ ] Map format validation patterns
- [ ] Add row-level-issues for format violations
- [ ] Calculate standardization-specific issue_summary
- [ ] Syntax validation ✅

**Estimated Effort**: 3 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 7. `agents/duplicate_resolver.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- How are duplicates detected? (Exact, fuzzy, key-based)
- What similarity thresholds are used?
- How are conflicts identified?

**Row-Level Issues to Detect**:

- `duplicate_row` - Exact duplicate rows
- `partial_duplicate` - Rows with some matching fields
- `key_conflict` - Primary key conflicts
- `near_duplicate` - Fuzzy duplicates above threshold

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Understand duplicate detection methods
- [ ] Extract duplicate relationships (which rows match)
- [ ] Add row-level-issues for duplicates
- [ ] Calculate duplicate-specific issue_summary
- [ ] Syntax validation ✅

**Estimated Effort**: 3-4 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 8. `agents/governance_checker.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- What governance policies are checked?
- How are policy violations detected?
- What compliance rules are enforced?

**Row-Level Issues to Detect**:

- `policy_violation` - Row-level policy violations
- `compliance_issue` - Compliance violations
- `naming_violation` - Column naming violations (row impact)
- `data_retention_violation` - Retention rule violations

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Identify governance policies
- [ ] Map row-level policy impacts
- [ ] Add row-level-issues for violations
- [ ] Calculate governance-specific issue_summary
- [ ] Syntax validation ✅

**Estimated Effort**: 3-4 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 9. `agents/score_risk.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- How is risk scored at row level?
- What PII risks are detected?
- How are compliance violations assessed?

**Row-Level Issues to Detect**:

- `risk_high` - Rows with high risk scores
- `pii_exposure` - PII detected in row
- `compliance_violation` - Compliance violations (GDPR, HIPAA, CCPA)
- `remediation_needed` - Rows needing risk remediation

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Understand risk scoring methodology
- [ ] Identify PII detection patterns
- [ ] Add row-level-issues for high-risk rows
- [ ] Calculate risk-specific issue_summary
- [ ] Syntax validation ✅

**Estimated Effort**: 4-5 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 10. `agents/readiness_rater.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- How are readiness scores calculated at row level?
- What validation failures are detected?
- How are quality gates assessed?

**Row-Level Issues to Detect**:

- `readiness_low` - Rows with low readiness scores
- `validation_failed` - Rows failing validation
- `quality_gate_failed` - Quality gate failures
- `completeness_issue` - Incomplete rows

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Understand readiness scoring
- [ ] Map validation rules to row issues
- [ ] Add row-level-issues for readiness failures
- [ ] Calculate readiness-specific issue_summary
- [ ] Syntax validation ✅

**Estimated Effort**: 3-4 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 11. `agents/test_coverage_agent.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- What test coverage gaps are identified?
- How are edge cases detected?
- What validation rules are tested?

**Row-Level Issues to Detect**:

- `test_coverage_gap` - Values with insufficient test coverage
- `validation_missing` - Validation gaps
- `edge_case_uncovered` - Values hitting untested edge cases
- `format_edge_case` - Edge case format issues

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Understand coverage analysis
- [ ] Map test gaps to row-level values
- [ ] Add row-level-issues for coverage gaps
- [ ] Calculate coverage-specific issue_summary
- [ ] Syntax validation ✅

**Estimated Effort**: 3-4 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 12. `agents/cleanse_previewer.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- How are cleaning simulations performed?
- What safety checks are done?
- How are high-impact changes identified?

**Row-Level Issues to Detect**:

- `simulation_failed` - Rows where simulation failed
- `unsafe_operation` - Unsafe cleaning operations on row
- `high_impact_change` - Changes significantly impacting row
- `preview_issue` - Rows with preview problems

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Understand simulation logic
- [ ] Identify safety-critical rows
- [ ] Add row-level-issues for simulation issues
- [ ] Calculate preview-specific issue_summary
- [ ] Syntax validation ✅

**Estimated Effort**: 3-4 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 13. `agents/cleanse_writeback.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- How are write operations tracked?
- What integrity checks are performed?
- How are write failures handled?

**Row-Level Issues to Detect**:

- `writeback_failed` - Rows where writeback failed
- `integrity_violation` - Post-write integrity violations
- `rollback_needed` - Rows requiring rollback
- `write_conflict` - Write operation conflicts

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Understand writeback logic
- [ ] Identify integrity check patterns
- [ ] Add row-level-issues for write failures
- [ ] Calculate writeback-specific issue_summary
- [ ] Syntax validation ✅

**Estimated Effort**: 3-4 hours  
**Owner**: [TBD]  
**Priority**: P0

---

### ⏳ 14. `agents/quarantine_agent.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Implementation Status**: ⏳ NOT STARTED

**What to Analyze**:

- What quarantine criteria are used?
- How are suspicious rows flagged?
- What anomaly scoring is applied?

**Row-Level Issues to Detect**:

- `quarantine_flagged` - Rows flagged for quarantine
- `suspicious_row` - Suspicious activity detected
- `data_anomaly` - Multiple anomalies in row
- `high_risk_flag` - High-risk flagged

**Implementation Checklist**:

- [ ] Read and analyze complete agent code
- [ ] Understand quarantine criteria
- [ ] Map anomaly scoring to rows
- [ ] Add row-level-issues for quarantine flags
- [ ] Calculate quarantine-specific issue_summary
- [ ] Syntax validation ✅

**Estimated Effort**: 3-4 hours  
**Owner**: [TBD]  
**Priority**: P0

---

## Transformers - Phase 2 Integration (2/2)

### ⏳ Transformer 1: `transformers/profile_my_data_transformer.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Integration Status**: ⏳ NOT STARTED

**Current Consolidation**: Aggregates alerts, issues, recommendations, summaries from all agents

**What to Add**:

- Consolidate `row_level_issues` from all agent responses
- Generate aggregated `issueSummary` with:
  - `total_issues`: Total count across all agents and rows
  - `by_type`: Distribution by issue type
  - `by_severity`: Distribution by severity
  - `affected_rows`: Count of unique affected rows
  - `affected_columns`: List of affected column names
- Include in response structure: `"rowLevelIssues": []`, `"issueSummary": {}`

**Integration Checklist**:

- [ ] Analyze current transformer logic
- [ ] Add row-level-issues consolidation loop
- [ ] Implement issueSummary calculation
- [ ] Update response structure
- [ ] Add data validation
- [ ] Syntax validation ✅

**Estimated Effort**: 2-3 hours  
**Owner**: [TBD]  
**Priority**: P0  
**Depends On**: All 14 agents completed

---

### ⏳ Transformer 2: `transformers/clean_my_data_transformer.py` - PENDING

**Analysis Status**: ⏳ NOT ANALYZED  
**Integration Status**: ⏳ NOT STARTED

**Current Consolidation**: Aggregates alerts, issues, recommendations from cleaning agents

**What to Add**:

- Consolidate `row_level_issues` from cleaning-related agents
- Generate aggregated `issueSummary` with same structure as above
- Include in response structure: `"rowLevelIssues": []`, `"issueSummary": {}`

**Integration Checklist**:

- [ ] Analyze current transformer logic
- [ ] Add row-level-issues consolidation loop
- [ ] Implement issueSummary calculation
- [ ] Update response structure
- [ ] Add data validation
- [ ] Syntax validation ✅

**Estimated Effort**: 2-3 hours  
**Owner**: [TBD]  
**Priority**: P0  
**Depends On**: All 14 agents completed

---

## Validation & Testing - Phase 3

### ⏳ Syntax Validation

- [ ] All 14 agent Python files pass syntax check
- [ ] Both transformer files pass syntax check
- [ ] JSON responses validate against schema

**Estimated Effort**: 1 hour  
**Owner**: [TBD]

---

### ⏳ Data Structure Validation

- [ ] Mock row-level-issues data matches RowLevelIssuesSection.jsx schema
- [ ] issueSummary contains all required fields
- [ ] Response structure integrates correctly with existing fields

**Estimated Effort**: 1-2 hours  
**Owner**: [TBD]

---

### ⏳ Frontend Integration Test

- [ ] RowLevelIssuesSection.jsx receives data correctly
- [ ] Filters (by severity) work properly
- [ ] Charts render with row-level-issues data
- [ ] Table displays issues with expand/collapse functionality

**Estimated Effort**: 2 hours  
**Owner**: [TBD]

---

## Final Status Dashboard

### Completion Summary

| Phase       | Component            | Status             | Progress | Est. Hours      |
| ----------- | -------------------- | ------------------ | -------- | --------------- |
| **Phase 1** | Schema Documentation | ✅ DONE            | 1/1      | 1               |
| **Phase 1** | Agents (1-14)        | 🔄 PENDING         | 0/14     | 46-56           |
| **Phase 2** | Transformers (2)     | ⏳ PENDING         | 0/2      | 4-6             |
| **Phase 3** | Validation           | ⏳ PENDING         | 0/3      | 4-5             |
| **TOTAL**   | **ALL**              | 🔄 **IN PROGRESS** | **1/23** | **55-68 hours** |

### Delivery Checklist (0/23 COMPLETE)

- ✅ **1.** Row-Level-Issues Schema (COMPLETED)
- ⏳ **2.** unified_profiler.py row-level-issues
- ⏳ **3.** drift_detector.py row-level-issues
- ⏳ **4.** null_handler.py row-level-issues
- ⏳ **5.** outlier_remover.py row-level-issues
- ⏳ **6.** type_fixer.py row-level-issues
- ⏳ **7.** field_standardization.py row-level-issues
- ⏳ **8.** duplicate_resolver.py row-level-issues
- ⏳ **9.** governance_checker.py row-level-issues
- ⏳ **10.** score_risk.py row-level-issues
- ⏳ **11.** readiness_rater.py row-level-issues
- ⏳ **12.** test_coverage_agent.py row-level-issues
- ⏳ **13.** cleanse_previewer.py row-level-issues
- ⏳ **14.** cleanse_writeback.py row-level-issues
- ⏳ **15.** quarantine_agent.py row-level-issues
- ⏳ **16.** profile_my_data_transformer.py integration
- ⏳ **17.** clean_my_data_transformer.py integration
- ⏳ **18.** Syntax validation (all files)
- ⏳ **19.** Data structure validation
- ⏳ **20.** Frontend integration test

---

## Implementation Guidelines

### For Each Agent (Workflow)

1. **Read Agent Code** - Understand complete detection logic
2. **Identify Row Issues** - Map what issues occur at row level
3. **Extract Data** - Get row indices, values, bounds where applicable
4. **Build Issues Array** - Create row-level-issues list
5. **Calculate Summary** - Aggregate statistics for issueSummary
6. **Validate Schema** - Check against standardized structure
7. **Update Return** - Include both arrays in response
8. **Test Syntax** - Validate Python file syntax

### For Each Transformer (Workflow)

1. **Analyze Current Logic** - Understand how agents are called
2. **Add Consolidation Loop** - Iterate through agent results
3. **Extract row-level-issues** - Pull from each agent response
4. **Calculate issueSummary** - Aggregate across all agents
5. **Update Response** - Add new fields to return structure
6. **Validate Schema** - Match expected frontend structure
7. **Test Syntax** - Validate Python file syntax

### Schema Validation Tips

- Each issue must have: `row_index`, `column`, `issue_type`, `severity`, `message`
- Optional fields: `value`, `bounds`, detection-specific metadata
- Severity must be one of: "critical", "warning", "info"
- All lists should be capped at 200 items max per agent
- issueSummary must always include: `total_issues`, `by_type`, `by_severity`, `affected_rows`, `affected_columns`

---

## Notes & Important Details

### Sequence Requirements

- **All 14 agents MUST be completed before starting transformers**
- Transformers depend on row-level-issues being in all agent outputs
- Validation phase can start once transformers are integrated

### Performance Considerations

- Cap row-level-issues at 200 items per agent to prevent memory issues
- Use list comprehensions for efficient issue collection
- Pre-calculate summary statistics to avoid repeated iterations

### Frontend Expectations

- `rowLevelIssues` should be an array of issue objects
- `issueSummary` should contain aggregated statistics
- Component expects severity values: "critical", "warning", "info"
- Component expects issue_type to be string formatted (spaces, not underscores in display)

### Documentation Updates Needed (After Completion)

- Update API_SPECIFICATION.js with row-level-issues schema
- Add row-level-issues to agent documentation
- Document transformer consolidation logic
- Add row-level-issues to frontend component usage guide

---

## Next Steps (Ready to Start)

1. **Select Agent 1** - Start with `unified_profiler.py` (good foundation)
2. **Complete Agent Analysis** - Read and document detection methods
3. **Implement Row-Level Logic** - Add row-level-issues generation
4. **Validate** - Syntax check + schema validation
5. **Move to Agent 2** - Continue sequentially through all 14
6. **Integrate Transformers** - After all agents complete
7. **Final Testing** - Validation phase

**Ready to begin Phase 1, Agent 1 analysis? Proceed with `unified_profiler.py` next.**

---

**Created:** November 19, 2025  
**Task Version:** 2.0 (Row-Level-Issues Focus)  
**Total Estimated Effort:** 55-68 hours  
**Target Completion:** December 15-20, 2025 (estimate based on parallel work)
