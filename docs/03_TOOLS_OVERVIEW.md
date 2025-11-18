# Agensium Backend - Tools & Agents Overview

## Tools Summary

| Tool                | Purpose                | Agents   | Files                       | Use Case                                                  |
| ------------------- | ---------------------- | -------- | --------------------------- | --------------------------------------------------------- |
| **Profile My Data** | Comprehensive analysis | 6 agents | Primary + Optional Baseline | First-time exploration, quality baseline, risk assessment |
| **Clean My Data**   | Data improvement       | 6 agents | Primary only                | Fix quality issues, remove duplicates, prepare for ML     |

---

## 📥 Downloads Available

Both tools provide comprehensive downloads with every analysis:

- **Excel Report**: Professional multi-sheet workbook with all findings

  - Profile My Data: 10 sheets (profiling, drift, risk, readiness, governance, test coverage, alerts, issues, recommendations)
  - Clean My Data: 10 sheets (null handling, outliers, type fixing, duplicates, governance, test coverage, alerts, issues, recommendations)

- **JSON Export**: Complete hierarchical data with all agent results
  - All agent outputs included
  - Metadata and timestamps for audit trail
  - Base64 encoded for API transmission

See [07_DOWNLOADS_AND_CHAT.md](./07_DOWNLOADS_AND_CHAT.md) for download integration details.

---

## Tool 1: Profile My Data

### Overview

Comprehensive data profiling tool that analyzes data quality, detects patterns, identifies risks, and assesses production readiness.

### Tool ID

```
profile-my-data
```

### Available Agents

#### 1. Unified Profiler

**ID**: `unified-profiler`

**Purpose**: Comprehensive data quality and statistical analysis

**What It Does**:

- Field-level statistics (mean, median, std dev, min, max)
- Data completeness analysis (null detection)
- Uniqueness analysis (cardinality)
- Distribution analysis (skewness, kurtosis)
- Outlier detection via IQR method
- Data type classification

**Parameters**:

```json
{
  "null_alert_threshold": 50, // Alert if nulls > this %
  "categorical_threshold": 20, // Min unique values for categorical
  "categorical_ratio_threshold": 0.05, // Unique/total ratio
  "top_n_values": 10, // Show top N categories
  "outlier_iqr_multiplier": 1.5, // IQR multiplier for outliers
  "outlier_alert_threshold": 5 // Alert if outliers > this %
}
```

**Output**:

- Overall quality score (0-100)
- Per-field quality metrics
- Null value summary
- Distribution analysis
- Top categories for categorical fields
- Outlier detection results

**Quality Score Components**:

- Completeness (null %): 40%
- Consistency (unique patterns): 30%
- Validity (data types): 30%

---

#### 2. Drift Detector

**ID**: `drift-detector`

**Purpose**: Detect distribution changes between datasets

**What It Does**:

- Compares primary dataset against baseline
- Uses statistical tests (Kolmogorov-Smirnov, Chi-square, Wasserstein)
- Calculates PSI (Population Stability Index)
- Identifies significant distribution shifts
- Reports field-level drift severity

**Required Files**:

- `primary`: Current dataset
- `baseline`: Reference dataset

**Parameters**:

```json
{
  "statistical_test": "kolmogorov_smirnov", // or chi2, wasserstein
  "significance_level": 0.05, // Statistical significance
  "min_sample_size": 100 // Min rows to test
}
```

**Output**:

- Overall drift percentage (0-100%)
- Per-field drift score via PSI
- Statistical test p-values
- Stable vs unstable fields
- Distribution change visualizations

**Drift Severity**:

- PSI < 0.1: No significant drift
- PSI 0.1-0.25: Small shift detected
- PSI > 0.25: Significant drift

---

#### 3. Score Risk

**ID**: `score-risk`

**Purpose**: PII detection and compliance risk assessment

**What It Does**:

- Scans columns for PII patterns (email, phone, SSN, credit card, etc.)
- Detects sensitive data exposure
- Assesses compliance requirements (GDPR, CCPA, HIPAA)
- Calculates overall risk score
- Identifies governance gaps

**Detected PII Types**:

- Email addresses
- Phone numbers
- Social Security Numbers
- Credit card numbers
- Driver's license numbers
- IP addresses
- Street addresses

**Parameters**:

```json
{
  "include_custom_patterns": false, // Use custom regex patterns
  "frameworks": ["GDPR", "CCPA", "HIPAA"] // Compliance frameworks
}
```

**Output**:

- Overall risk score (0-100)
- Per-field risk level
- PII types detected
- Compliance gaps
- Governance recommendations

**Risk Score Interpretation**:

- 0-30: Low risk
- 30-70: Medium risk (review recommended)
- 70-100: High risk (immediate action needed)

---

#### 4. Readiness Rater

**ID**: `readiness-rater`

**Purpose**: Evaluate data production readiness

**What It Does**:

- Assesses data completeness
- Evaluates consistency standards
- Checks schema validity
- Reviews governance requirements
- Calculates readiness score
- Identifies blocking issues

**Assessment Criteria**:

- Completeness: >= 95% non-null rows
- Consistency: Uniform data types
- Validity: Correct formats and ranges
- Governance: Compliance with standards
- Documentation: Metadata availability

**Parameters**:

```json
{
  "ready_threshold": 75, // Score >= this = ready
  "quality_weight": 0.4, // Quality component weight
  "completeness_weight": 0.3, // Completeness weight
  "governance_weight": 0.3 // Governance weight
}
```

**Output**:

- Readiness score (0-100)
- Readiness status: Ready / Needs Work / Not Ready
- Component scores (quality, completeness, governance)
- Blocking issues list
- Recommendations for readiness

**Status Interpretation**:

- Score >= 75: Production Ready
- Score 50-75: Needs Work
- Score < 50: Not Ready

---

#### 5. Governance Checker

**ID**: `governance-checker`

**Purpose**: Validate data governance compliance

**What It Does**:

- Validates lineage tracking requirements
- Checks consent documentation
- Verifies data classification
- Assesses compliance status
- Identifies governance gaps

**Validation Areas**:

- Data Lineage: Know data origin and transformations
- Consent: Verify user consent is documented
- Classification: Ensure data is properly classified
- Access Control: Check access restrictions
- Retention: Validate retention policies

**Parameters**:

```json
{
  "lineage_weight": 0.3, // Lineage importance
  "consent_weight": 0.4, // Consent importance
  "classification_weight": 0.3, // Classification importance
  "compliance_threshold": 80, // Compliance score >= this
  "needs_review_threshold": 60, // Review score range
  "required_lineage_fields": [], // Must have lineage
  "required_consent_fields": [], // Must have consent
  "required_classification_fields": [] // Must have classification
}
```

**Output**:

- Governance score (0-100)
- Compliance status: Compliant / Needs Review / Non-Compliant
- Per-component scores
- Governance issues
- Remediation recommendations

---

#### 6. Test Coverage Agent

**ID**: `test-coverage-agent`

**Purpose**: Validate test coverage requirements

**What It Does**:

- Validates uniqueness constraints
- Checks value ranges
- Verifies format patterns
- Assesses coverage completeness
- Identifies untested scenarios

**Test Types**:

- Uniqueness: Verify key uniqueness
- Range: Check numeric bounds
- Format: Validate patterns (email, date, etc.)
- Presence: Ensure required fields
- Type: Validate data types

**Parameters**:

```json
{
  "uniqueness_weight": 0.4, // Uniqueness importance
  "range_weight": 0.3, // Range importance
  "format_weight": 0.3, // Format importance
  "excellent_threshold": 90, // Excellent score >= this
  "good_threshold": 75, // Good score >= this
  "unique_columns": ["id", "email"], // Should be unique
  "range_tests": {
    // Numeric ranges
    "age": { "min": 0, "max": 150 }
  },
  "format_tests": {
    // Format patterns
    "email": { "pattern": ".*@.*\\..*" }
  }
}
```

**Output**:

- Coverage score (0-100)
- Coverage status: Excellent / Good / Fair / Poor
- Per-test results
- Coverage gaps
- Testing recommendations

---

## Tool 2: Clean My Data

### Overview

Data cleaning and validation tool that improves data quality through systematic issue resolution.

### Tool ID

```
clean-my-data
```

### Available Agents

#### 1. Null Handler

**ID**: `null-handler`

**Purpose**: Detect and handle missing values

**What It Does**:

- Analyzes null patterns
- Identifies null concentration by column
- Applies configurable imputation strategies
- Tracks imputation operations
- Calculates cleaning effectiveness

**Imputation Strategies**:

- `drop_rows`: Remove rows with nulls
- `mean`: Fill numeric nulls with column mean
- `median`: Fill numeric nulls with column median
- `mode`: Fill with most frequent value
- `forward_fill`: Carry forward last valid value
- `backward_fill`: Carry backward next valid value
- `knn`: K-nearest neighbors imputation
- `constant`: Fill with user-specified value

**Parameters**:

```json
{
  "global_strategy": "column_specific", // drop_rows or column_specific
  "column_strategies": {
    // Per-column strategy
    "age": "median",
    "city": "mode"
  },
  "fill_values": {
    // Constants for fill
    "status": "unknown"
  },
  "knn_neighbors": 5, // KNN neighbors count
  "null_reduction_weight": 0.5, // Null reduction importance
  "data_retention_weight": 0.3, // Data retention importance
  "column_retention_weight": 0.2, // Column retention importance
  "excellent_threshold": 90, // Excellent score >= this
  "good_threshold": 75 // Good score >= this
}
```

**Output**:

- Cleaning score (0-100)
- Quality status: Excellent / Good / Needs Improvement
- Per-column null summary
- Imputation log (what was done)
- Row-level issues
- Recommendations

**Quality Metrics**:

- Nulls handled count
- Rows processed
- Columns affected
- Data retention %
- Column retention %

---

#### 2. Outlier Remover

**ID**: `outlier-remover`

**Purpose**: Detect and handle outliers

**What It Does**:

- Analyzes numeric columns for outliers
- Uses configurable detection methods
- Applies removal or imputation strategies
- Tracks outlier handling
- Calculates effectiveness

**Detection Methods**:

- `z_score`: Standard deviation based (default: 3.0)
- `iqr`: Interquartile range based (default: 1.5x)
- `percentile`: Percentile based (default: 1st-99th)

**Handling Strategies**:

- `remove`: Delete outlier rows
- `impute_mean`: Replace with column mean
- `impute_median`: Replace with column median

**Parameters**:

```json
{
  "detection_method": "iqr", // z_score, iqr, or percentile
  "removal_strategy": "impute_median", // remove or impute
  "z_threshold": 3.0, // Z-score threshold
  "iqr_multiplier": 1.5, // IQR multiplier
  "lower_percentile": 1.0, // Lower bound %
  "upper_percentile": 99.0, // Upper bound %
  "outlier_reduction_weight": 0.5, // Importance in score
  "data_retention_weight": 0.3,
  "column_retention_weight": 0.2,
  "excellent_threshold": 90,
  "good_threshold": 75
}
```

**Output**:

- Outlier score (0-100)
- Quality status
- Per-column outlier summary
- Detection method used
- Outlier handling log
- Row-level issues
- Recommendations

---

#### 3. Type Fixer ✨

**ID**: `type-fixer`

**Purpose**: Fix data type inconsistencies

**What It Does**:

- Detects type mismatches in columns
- Identifies object columns with numeric/date values
- Identifies float columns with only integers
- Applies configurable type conversions
- Tracks conversion results

**Type Conversions**:

- To `numeric`: Parse as float
- To `integer`: Parse as int64
- To `datetime`: Parse as datetime
- To `string`: Convert to string
- To `category`: Convert to category

**Detection Logic**:

- Object columns: Sample 100 values
- If >70% are numeric: Suggest numeric conversion
- If >70% are dates: Suggest datetime conversion
- Float columns: Check if all are integers

**Parameters**:

```json
{
  "auto_convert_numeric": true, // Auto convert to numeric
  "auto_convert_datetime": true, // Auto convert to datetime
  "auto_convert_category": true, // Auto convert to category
  "preserve_mixed_types": false, // Keep mixed type columns
  "type_reduction_weight": 0.5, // Type fix importance
  "data_retention_weight": 0.3, // Data retention importance
  "column_retention_weight": 0.2, // Column retention importance
  "excellent_threshold": 90, // Excellent score >= this
  "good_threshold": 75 // Good score >= this
}
```

**Output**:

- Fixing score (0-100)
- Quality status
- Type analysis (current vs suggested)
- Per-column type recommendations
- Conversion log
- Row-level issues
- Recommendations

**Quality Metrics**:

- Type issues fixed count
- Original issues count
- Remaining issues count
- Data retention %
- Column retention %

---

#### 4. Duplicate Resolver ✨ NEW

**ID**: `duplicate-resolver`

**Purpose**: Detect and resolve duplicate records with comprehensive duplicate detection strategies

**What It Does**:

- Detects exact duplicate records
- Identifies duplicates with case/whitespace variations
- Handles email case-insensitivity
- Finds duplicates that differ only in missing values
- Detects conflicting duplicates (same key, different values)
- Applies configurable merge/removal strategies
- Tracks deduplication operations
- Calculates deduplication effectiveness

**Duplicate Detection Types** (all 5 methods by default):

1. **Exact Duplicates**: Identical values across all columns
2. **Case Variations**: Same data with different casing (e.g., "John" vs "john") or extra whitespace
3. **Email Case-Insensitivity**: Same records where only email differs in case
4. **Missing Value Duplicates**: Identical records except for null placement
5. **Conflicting Duplicates**: Same key columns but conflicting values in other columns

**Merge Strategies**:

- `remove_duplicates`: Keep first occurrence, remove subsequent duplicates
- `merge_smart`: Intelligently merge rows by key columns, using conflict resolution strategy

**Conflict Resolution Strategies**:

- `keep_first`: Keep first occurrence's values
- `keep_last`: Keep last occurrence's values
- `merge_smart`: Attempt to merge non-conflicting values intelligently

**Parameters**:

```json
{
  "detection_types": [
    "exact",
    "case_variations",
    "email_case",
    "missing_values",
    "conflicting"
  ],
  "merge_strategy": "remove_duplicates", // remove_duplicates or merge_smart
  "email_columns": [], // Auto-detected if empty (e.g., ["email", "contact_email"])
  "key_columns": [], // Columns for dedup key (all columns if empty)
  "null_handling": "ignore_nulls", // ignore_nulls or match_nulls
  "conflict_resolution": "keep_first", // keep_first, keep_last, merge_smart
  "dedup_reduction_weight": 0.5, // Dedup effectiveness importance
  "data_retention_weight": 0.3, // Data retention importance
  "column_retention_weight": 0.2, // Column retention importance
  "excellent_threshold": 90, // Excellent score >= this
  "good_threshold": 75 // Good score >= this
}
```

**Output**:

- Deduplication score (0-100)
- Quality status: Excellent / Good / Needs Improvement
- Per-detection-method summary
- Duplicates detected per method
- Resolution log (what was done)
- Row-level duplicate issues
- Recommendations

**Quality Metrics**:

- Total duplicates detected
- Duplicates resolved
- Remaining rows
- Rows removed
- Duplicate percentage before/after
- Data retention %
- Column retention %

**Example Usage Scenarios**:

- Clean customer database before CRM migration
- Merge data from multiple sources with format variations
- Ensure unique user records in application databases
- Prepare data for deduplication before machine learning
- Comply with data governance: one record per entity

---

#### 5. Governance Checker

**ID**: `governance-checker`

**Purpose**: Validate governance compliance (same as profile tool)

See Profile Tool section above.

---

#### 5. Test Coverage Agent

**ID**: `test-coverage-agent`

**Purpose**: Validate test coverage requirements (same as profile tool)

See Profile Tool section above.

---

## Agent Selection Guide

### Scenario: New Dataset Exploration

**Use**: Profile My Data with all agents

```
- unified-profiler: Understand data structure
- drift-detector: Check for anomalies (no baseline needed)
- score-risk: Identify PII
- readiness-rater: Check readiness
- governance-checker: Check compliance
- test-coverage-agent: Check coverage
```

### Scenario: Data Quality Issues

**Use**: Clean My Data with quality agents

```
- null-handler: Fix missing values
- outlier-remover: Remove outliers
- type-fixer: Fix type mismatches
- duplicate-resolver: Remove duplicate records
- governance-checker: Ensure compliance
- test-coverage-agent: Verify coverage
```

### Scenario: Merge Data From Multiple Sources

**Use**: Clean My Data with duplicate focus

```
- duplicate-resolver: Handle format variations and duplicates
- null-handler: Fix any remaining null values
- type-fixer: Standardize data types
```

### Scenario: Compare Two Datasets

**Use**: Profile My Data with drift focus

```
- unified-profiler: Profile current data
- drift-detector: Compare with baseline
```

### Scenario: Verify Cleaning Results

**Use**: Profile My Data after cleaning

```
- Run all agents to verify improvements
- Compare metrics before/after cleaning
```

---

## Parameter Configuration Best Practices

### Default Parameters

Most agents work well with defaults. Override only when:

1. You know your data characteristics
2. You want stricter/looser quality standards
3. You have specific business requirements

### Quality Thresholds

Adjust for your use case:

- ML training data: 90+ score (strict)
- Analytics: 75+ score (moderate)
- Reporting: 60+ score (lenient)

### Detection Methods

Choose based on your data:

- `z_score`: Normally distributed data
- `iqr`: Non-normal, robust to outliers
- `percentile`: When you know bounds

### Imputation Strategies

Consider data patterns:

- `mean/median`: Numeric columns
- `mode`: Categorical columns
- `knn`: Complex patterns
- `forward_fill`: Time series data

---

## Next Steps

- Read [04_API_REFERENCE.md](./04_API_REFERENCE.md) for endpoint details
- Read [07_DOWNLOADS_AND_CHAT.md](./07_DOWNLOADS_AND_CHAT.md) for downloads and chat features
- Read [05_AGENT_DEVELOPMENT.md](./05_AGENT_DEVELOPMENT.md) for creating agents
- Read [02_ARCHITECTURE.md](./02_ARCHITECTURE.md) for system flow
