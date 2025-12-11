# Agensium Parameters Reference

## Overview

This document provides a comprehensive list of all parameter types and configurations used across all Agensium tools and agents.

**Document Updated**: December 11, 2025 - Now includes `show` and `required` properties for each parameter.

---

## Parameter Properties Explained

### `show` Property

Determines if a parameter should be visible in the standard user interface.

- **`true`** (User-facing): Parameter should be shown to users in the UI.

  1. **User-defined Lists/Arrays**: `required_fields`, `target_columns`, `key_columns`, `email_columns`, etc.
  2. **Business Logic**: custom mappings, rules, constraints, contracts.
  3. **Core Strategies**: `detection_method`, `merge_strategy`, `global_strategy`, `case_strategy`.
  4. **Detection Toggles for Optional Features**: `unit_standardization`, `enable_fuzzy_matching`.

- **`false`** (Advanced/Auto): Parameter has good defaults and can be hidden in basic/standard view (shown only in advanced mode).
  1. **Weight Parameters**: All `*_weight` parameters (`accuracy_weight`, `safety_weight`, etc.).
  2. **Threshold Scores**: `excellent_threshold`, `good_threshold`.
  3. **Statistical Parameters**: `confidence_level`, `significance_level`, `outlier_iqr_multiplier`.
  4. **Detection Toggles that default to true**: `detect_missing_fields`, `auto_convert_numeric`, etc.
  5. **Advanced Settings**: `knn_neighbors`, `max_composite_key_columns`, etc.

### `required` Property

Determines if a parameter is mandatory for the agent to function.

- **`true`** (Mandatory): Parameter MUST be provided by user (critical for agent operation).

  1. **Critical Business Logic**: `match_key_columns` (in Golden Record Builder), `source_column`.
  2. **Empty defaults that need user input**: Arrays/objects with `[]` or `{}` defaults that define business logic.

- **`false`** (Optional): Parameter is optional (has working default values).
  1. **Most parameters** fall into this category as they have sensible defaults.

---

## Parameter Type Summary

### Core Data Types Used

1. **string** - Text values
2. **integer** - Whole numbers
3. **float** (number) - Decimal numbers
4. **boolean** - True/False values
5. **array** - Lists of items
6. **object** - Complex nested structures

### Parameter Visibility Statistics

- **Total Parameters**: 202
- **show: true** (User-facing): 87 (43.1%)
- **show: false** (Advanced/Auto): 115 (56.9%)
- **required: true** (Mandatory): 5 (2.5%)
- **required: false** (Optional): 197 (97.5%)

---

## Tools Overview

### 1. Clean My Data

**Tool ID:** `clean-my-data`

**Available Agents:** 8

#### Agents:

1. [Cleanse Previewer](#cleanse-previewer)
2. [Quarantine Agent](#quarantine-agent)
3. [Type Fixer](#type-fixer)
4. [Field Standardization](#field-standardization)
5. [Duplicate Resolver](#duplicate-resolver)
6. [Null Handler](#null-handler)
7. [Outlier Remover](#outlier-remover)
8. [Cleanse Writeback](#cleanse-writeback)

---

### 2. Master My Data

**Tool ID:** `master-my-data`

**Available Agents:** 6

#### Agents:

1. [Key Identifier](#key-identifier)
2. [Contract Enforcer](#contract-enforcer)
3. [Semantic Mapper](#semantic-mapper)
4. [Survivorship Resolver](#survivorship-resolver)
5. [Golden Record Builder](#golden-record-builder)
6. [Stewardship Flagger](#stewardship-flagger)

---

### 3. Profile My Data

**Tool ID:** `profile-my-data`

**Available Agents:** 6

#### Agents:

1. [Unified Profiler](#unified-profiler)
2. [Drift Detector](#drift-detector)
3. [Risk Scorer](#score-risk)
4. [Governance Checker](#governance-checker)
5. [Test Coverage Agent](#test-coverage-agent)
6. [Readiness Rater](#readiness-rater)

---

## Detailed Agent Parameters

### CLEAN MY DATA AGENTS

#### Cleanse Previewer

**ID:** `cleanse-previewer`

**Category:** Data Analysis & Preview

**Accuracy:** 97%

| Parameter Name            | Type    | Default | Range | Show | Required | Description                                                                                                                                                                                                |
| ------------------------- | ------- | ------- | ----- | ---- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `preview_rules`           | array   | []      | -     | ✓    | ✗        | List of cleaning rules to preview. Each rule specifies: {type, target_columns, description, ...}. Supported types: drop_nulls, impute_nulls, remove_outliers, drop_duplicates, drop_columns, convert_types |
| `impact_threshold_high`   | float   | 10      | -     | ✗    | ✗        | Percentage change threshold to classify as high impact                                                                                                                                                     |
| `impact_threshold_medium` | float   | 5       | -     | ✗    | ✗        | Percentage change threshold to classify as medium impact                                                                                                                                                   |
| `confidence_level`        | float   | 0.95    | -     | ✗    | ✗        | Statistical confidence level for analysis                                                                                                                                                                  |
| `calculate_distributions` | boolean | True    | -     | ✗    | ✗        | Calculate distribution metrics (skewness, kurtosis)                                                                                                                                                        |
| `compare_statistics`      | boolean | True    | -     | ✗    | ✗        | Compare statistical measures before/after                                                                                                                                                                  |
| `analyze_correlations`    | boolean | False   | -     | ✗    | ✗        | Analyze correlation changes                                                                                                                                                                                |
| `accuracy_weight`         | float   | 0.4     | -     | ✗    | ✗        | Weight for preview accuracy in scoring                                                                                                                                                                     |
| `safety_weight`           | float   | 0.3     | -     | ✗    | ✗        | Weight for operation safety in scoring                                                                                                                                                                     |
| `completeness_weight`     | float   | 0.3     | -     | ✗    | ✗        | Weight for analysis completeness in scoring                                                                                                                                                                |
| `excellent_threshold`     | integer | 90      | -     | ✗    | ✗        | Score threshold for excellent preview quality                                                                                                                                                              |
| `good_threshold`          | integer | 75      | -     | ✗    | ✗        | Score threshold for good preview quality                                                                                                                                                                   |

---

#### Quarantine Agent

**ID:** `quarantine-agent`

**Category:** Data Quality & Security

**Accuracy:** 98%

| Parameter Name                 | Type    | Default | Range | Show | Required | Description                                      |
| ------------------------------ | ------- | ------- | ----- | ---- | -------- | ------------------------------------------------ |
| `detect_missing_fields`        | boolean | True    | -     | ✗    | ✗        | Detect missing required fields                   |
| `detect_type_mismatches`       | boolean | True    | -     | ✗    | ✗        | Detect data type mismatches                      |
| `detect_out_of_range`          | boolean | True    | -     | ✗    | ✗        | Detect out-of-range numeric values               |
| `detect_invalid_formats`       | boolean | True    | -     | ✗    | ✗        | Detect invalid format values                     |
| `detect_broken_records`        | boolean | True    | -     | ✗    | ✗        | Detect corrupted or broken records               |
| `detect_schema_mismatches`     | boolean | True    | -     | ✗    | ✗        | Detect schema mismatches                         |
| `required_fields`              | array   | []      | -     | ✓    | ✗        | List of required field names                     |
| `range_constraints`            | object  | {}      | -     | ✓    | ✗        | Numeric range constraints (column -> {min, max}) |
| `format_constraints`           | object  | {}      | -     | ✓    | ✗        | Format constraints (column -> regex pattern)     |
| `expected_schema`              | object  | {}      | -     | ✗    | ✗        | Expected data types for columns (column -> type) |
| `quarantine_reduction_weight`  | float   | 0.5     | -     | ✗    | ✗        | Weight for quarantine effectiveness in scoring   |
| `data_integrity_weight`        | float   | 0.3     | -     | ✗    | ✗        | Weight for data integrity in scoring             |
| `processing_efficiency_weight` | float   | 0.2     | -     | ✗    | ✗        | Weight for processing efficiency in scoring      |
| `excellent_threshold`          | integer | 90      | -     | ✗    | ✗        | Score threshold for excellent quality            |
| `good_threshold`               | integer | 75      | -     | ✗    | ✗        | Score threshold for good quality                 |

---

#### Type Fixer

**ID:** `type-fixer`

**Category:** Data Cleaning

**Accuracy:** 96%

| Parameter Name            | Type    | Default | Range | Show | Required | Description                                |
| ------------------------- | ------- | ------- | ----- | ---- | -------- | ------------------------------------------ |
| `auto_convert_numeric`    | boolean | True    | -     | ✗    | ✗        | Automatically convert to numeric type      |
| `auto_convert_datetime`   | boolean | True    | -     | ✗    | ✗        | Automatically convert to datetime type     |
| `auto_convert_category`   | boolean | True    | -     | ✗    | ✗        | Automatically convert to category type     |
| `preserve_mixed_types`    | boolean | False   | -     | ✗    | ✗        | Keep columns with mixed types as object    |
| `type_reduction_weight`   | float   | 0.5     | -     | ✗    | ✗        | Weight for type issue reduction in scoring |
| `data_retention_weight`   | float   | 0.3     | -     | ✗    | ✗        | Weight for data retention in scoring       |
| `column_retention_weight` | float   | 0.2     | -     | ✗    | ✗        | Weight for column retention in scoring     |
| `excellent_threshold`     | integer | 90      | -     | ✗    | ✗        | Score threshold for excellent quality      |
| `good_threshold`          | integer | 75      | -     | ✗    | ✗        | Score threshold for good quality           |

---

#### Field Standardization

**ID:** `field-standardization`

**Category:** Data Cleaning

**Accuracy:** 98%

| Parameter Name                         | Type    | Default     | Range | Show | Required | Description                                                                                                                                                                        |
| -------------------------------------- | ------- | ----------- | ----- | ---- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `case_strategy`                        | string  | "lowercase" | -     | ✓    | ✗        | Case normalization strategy to apply                                                                                                                                               |
| `trim_whitespace`                      | boolean | True        | -     | ✗    | ✗        | Remove leading and trailing whitespace                                                                                                                                             |
| `normalize_internal_spacing`           | boolean | True        | -     | ✗    | ✗        | Normalize internal spacing (collapse multiple spaces to single space)                                                                                                              |
| `apply_synonyms`                       | boolean | True        | -     | ✗    | ✗        | Apply synonym replacement mappings                                                                                                                                                 |
| `synonym_mappings`                     | object  | {}          | -     | ✓    | ✗        | Column-specific synonym mappings (column -> {synonym -> standard_value}). Example: {'address': {'St.': 'Street', 'Ave.': 'Avenue', 'Rd.': 'Road'}}                                 |
| `unit_standardization`                 | boolean | False       | -     | ✗    | ✗        | Apply unit conversion and standardization                                                                                                                                          |
| `unit_mappings`                        | object  | {}          | -     | ✓    | ✗        | Column-specific unit conversion mappings (column -> {unit_pattern -> {factor: number, target_unit: string}}). Example: {'height': {'ft': {'factor': 12, 'target_unit': 'inches'}}} |
| `date_standardization`                 | boolean | True        | -     | ✗    | ✗        | Standardize date formats to a consistent target format                                                                                                                             |
| `target_date_format`                   | string  | "%Y-%m-%d"  | -     | ✓    | ✗        | Target format for date standardization (e.g., %Y-%m-%d)                                                                                                                            |
| `target_columns`                       | array   | []          | -     | ✓    | ✗        | Specific columns to standardize (all columns if empty)                                                                                                                             |
| `preserve_columns`                     | array   | []          | -     | ✓    | ✗        | Columns to exclude from standardization                                                                                                                                            |
| `standardization_effectiveness_weight` | float   | 0.5         | -     | ✗    | ✗        | Weight for standardization effectiveness in scoring                                                                                                                                |
| `data_retention_weight`                | float   | 0.3         | -     | ✗    | ✗        | Weight for data retention in scoring                                                                                                                                               |
| `column_retention_weight`              | float   | 0.2         | -     | ✗    | ✗        | Weight for column retention in scoring                                                                                                                                             |
| `excellent_threshold`                  | integer | 90          | -     | ✗    | ✗        | Score threshold for excellent quality                                                                                                                                              |
| `good_threshold`                       | integer | 75          | -     | ✗    | ✗        | Score threshold for good quality                                                                                                                                                   |

---

#### Duplicate Resolver

**ID:** `duplicate-resolver`

**Category:** Data Cleaning

**Accuracy:** 99%

| Parameter Name            | Type    | Default                                                                     | Range | Show | Required | Description                                                                                     |
| ------------------------- | ------- | --------------------------------------------------------------------------- | ----- | ---- | -------- | ----------------------------------------------------------------------------------------------- |
| `detection_types`         | array   | ["exact", "case_variations", "email_case", "missing_values", "conflicting"] | -     | ✗    | ✗        | Types of duplicates to detect (exact, case_variations, email_case, missing_values, conflicting) |
| `merge_strategy`          | string  | "remove_duplicates"                                                         | -     | ✓    | ✗        | Strategy for handling duplicates                                                                |
| `email_columns`           | array   | []                                                                          | -     | ✓    | ✗        | Column names containing email addresses (auto-detected if empty)                                |
| `key_columns`             | array   | []                                                                          | -     | ✓    | ✗        | Columns to use as deduplication key (all columns if empty)                                      |
| `null_handling`           | string  | "ignore_nulls"                                                              | -     | ✗    | ✗        | How to handle null values in duplicate detection                                                |
| `conflict_resolution`     | string  | "keep_first"                                                                | -     | ✗    | ✗        | Strategy for resolving conflicting duplicate values                                             |
| `dedup_reduction_weight`  | float   | 0.5                                                                         | -     | ✗    | ✗        | Weight for deduplication effectiveness in scoring                                               |
| `data_retention_weight`   | float   | 0.3                                                                         | -     | ✗    | ✗        | Weight for data retention in scoring                                                            |
| `column_retention_weight` | float   | 0.2                                                                         | -     | ✗    | ✗        | Weight for column retention in scoring                                                          |
| `excellent_threshold`     | integer | 90                                                                          | -     | ✗    | ✗        | Score threshold for excellent quality                                                           |
| `good_threshold`          | integer | 75                                                                          | -     | ✗    | ✗        | Score threshold for good quality                                                                |

---

#### Null Handler

**ID:** `null-handler`

**Category:** Data Cleaning

**Accuracy:** 98%

| Parameter Name            | Type    | Default           | Range | Show | Required | Description                                           |
| ------------------------- | ------- | ----------------- | ----- | ---- | -------- | ----------------------------------------------------- |
| `global_strategy`         | string  | "column_specific" | -     | ✓    | ✗        | Global strategy for handling nulls                    |
| `column_strategies`       | object  | {}                | -     | ✗    | ✗        | Per-column imputation strategies (column -> strategy) |
| `fill_values`             | object  | {}                | -     | ✗    | ✗        | Constant values for constant fill strategy            |
| `knn_neighbors`           | integer | 5                 | -     | ✗    | ✗        | Number of neighbors for KNN imputation                |
| `null_reduction_weight`   | float   | 0.5               | -     | ✗    | ✗        | Weight for null reduction in scoring                  |
| `data_retention_weight`   | float   | 0.3               | -     | ✗    | ✗        | Weight for data retention in scoring                  |
| `column_retention_weight` | float   | 0.2               | -     | ✗    | ✗        | Weight for column retention in scoring                |
| `excellent_threshold`     | integer | 90                | -     | ✗    | ✗        | Score threshold for excellent quality                 |
| `good_threshold`          | integer | 75                | -     | ✗    | ✗        | Score threshold for good quality                      |

---

#### Outlier Remover

**ID:** `outlier-remover`

**Category:** Data Cleaning

**Accuracy:** 97%

| Parameter Name             | Type    | Default  | Range | Show | Required | Description                             |
| -------------------------- | ------- | -------- | ----- | ---- | -------- | --------------------------------------- |
| `detection_method`         | string  | "iqr"    | -     | ✓    | ✗        | Outlier detection method                |
| `removal_strategy`         | string  | "remove" | -     | ✓    | ✗        | Strategy for handling detected outliers |
| `z_threshold`              | float   | 3.0      | -     | ✗    | ✗        | Z-score threshold for outlier detection |
| `iqr_multiplier`           | float   | 1.5      | -     | ✗    | ✗        | IQR multiplier for outlier bounds       |
| `lower_percentile`         | float   | 1.0      | -     | ✗    | ✗        | Lower percentile for percentile method  |
| `upper_percentile`         | float   | 99.0     | -     | ✗    | ✗        | Upper percentile for percentile method  |
| `outlier_reduction_weight` | float   | 0.5      | -     | ✗    | ✗        | Weight for outlier reduction in scoring |
| `data_retention_weight`    | float   | 0.3      | -     | ✗    | ✗        | Weight for data retention in scoring    |
| `column_retention_weight`  | float   | 0.2      | -     | ✗    | ✗        | Weight for column retention in scoring  |
| `excellent_threshold`      | integer | 90       | -     | ✗    | ✗        | Score threshold for excellent quality   |
| `good_threshold`           | integer | 75       | -     | ✗    | ✗        | Score threshold for good quality        |

---

#### Cleanse Writeback

**ID:** `cleanse-writeback`

**Category:** Data Quality Assurance

**Accuracy:** 99%

| Parameter Name                    | Type    | Default | Range | Show | Required | Description                                                        |
| --------------------------------- | ------- | ------- | ----- | ---- | -------- | ------------------------------------------------------------------ |
| `verify_numeric_types`            | boolean | True    | -     | ✗    | ✗        | Verify that numeric columns are truly numeric after cleaning       |
| `verify_datetime_types`           | boolean | True    | -     | ✗    | ✗        | Verify that datetime columns are properly formatted                |
| `verify_no_new_nulls`             | boolean | True    | -     | ✗    | ✗        | Verify that cleaning operations did not introduce new nulls        |
| `verify_no_duplicates`            | boolean | True    | -     | ✗    | ✗        | Verify that no duplicate rows were introduced during cleaning      |
| `verify_data_retention`           | boolean | True    | -     | ✗    | ✗        | Verify that data retention is within acceptable limits             |
| `generate_comprehensive_manifest` | boolean | True    | -     | ✗    | ✗        | Generate comprehensive cleansing manifest with all agent actions   |
| `include_transformation_summary`  | boolean | True    | -     | ✗    | ✗        | Include high-level transformation summary in manifest              |
| `agent_manifests`                 | object  | {}      | -     | ✗    | ✗        | Dictionary of agent_id -> agent output for manifest aggregation    |
| `original_row_count`              | integer | null    | -     | ✗    | ✗        | Original row count before cleaning (for retention verification)    |
| `original_column_count`           | integer | null    | -     | ✗    | ✗        | Original column count before cleaning (for retention verification) |
| `integrity_weight`                | float   | 0.4     | -     | ✗    | ✗        | Weight for integrity verification in scoring                       |
| `completeness_weight`             | float   | 0.3     | -     | ✗    | ✗        | Weight for manifest completeness in scoring                        |
| `auditability_weight`             | float   | 0.3     | -     | ✗    | ✗        | Weight for auditability in scoring                                 |
| `excellent_threshold`             | integer | 95      | -     | ✗    | ✗        | Score threshold for excellent quality                              |
| `good_threshold`                  | integer | 85      | -     | ✗    | ✗        | Score threshold for good quality                                   |

---

### MASTER MY DATA AGENTS

#### Key Identifier

**ID:** `key-identifier`

**Category:** Data Structure

**Accuracy:** 99%

| Parameter Name              | Type    | Default | Range | Show | Required | Description                                                                               |
| --------------------------- | ------- | ------- | ----- | ---- | -------- | ----------------------------------------------------------------------------------------- |
| `pk_uniqueness_threshold`   | float   | 99.0    | -     | ✗    | ✗        | Percentage of unique values required to consider a column a primary key candidate         |
| `pk_null_threshold`         | float   | 0.0     | -     | ✗    | ✗        | Maximum percentage of null values allowed for primary key candidates                      |
| `entity_key_uniqueness_min` | float   | 50.0    | -     | ✗    | ✗        | Minimum uniqueness percentage for entity key candidates                                   |
| `entity_key_uniqueness_max` | float   | 99.0    | -     | ✗    | ✗        | Maximum uniqueness percentage for entity key candidates (above this becomes PK candidate) |
| `fk_overlap_threshold`      | float   | 70.0    | -     | ✗    | ✗        | Percentage of overlap required to identify a column as foreign key                        |
| `reference_tables`          | object  | {}      | -     | ✓    | ✗        | Dictionary of reference tables for FK detection (table_name -> {column: [values]})        |
| `analyze_composite_keys`    | boolean | True    | -     | ✗    | ✗        | Whether to analyze composite key combinations when no single PK found                     |
| `max_composite_key_columns` | integer | 3       | -     | ✗    | ✗        | Maximum number of columns to consider for a composite key                                 |
| `uniqueness_weight`         | float   | 0.4     | -     | ✗    | ✗        | Weight for uniqueness score in key scoring                                                |
| `null_density_weight`       | float   | 0.3     | -     | ✗    | ✗        | Weight for null density score in key scoring                                              |
| `pattern_weight`            | float   | 0.3     | -     | ✗    | ✗        | Weight for pattern detection score in key scoring                                         |
| `excellent_threshold`       | integer | 90      | -     | ✗    | ✗        | Score threshold for excellent quality status                                              |
| `good_threshold`            | integer | 75      | -     | ✗    | ✗        | Score threshold for good quality status                                                   |

---

#### Contract Enforcer

**ID:** `contract-enforcer`

**Category:** Governance

**Accuracy:** 98%

| Parameter Name                  | Type    | Default | Range | Show | Required | Description                                                                                                                                 |
| ------------------------------- | ------- | ------- | ----- | ---- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `contract`                      | object  | {}      | -     | ✓    | ✓        | Contract definition containing required_columns, optional_columns, column_types, column_mappings, value_constraints, uniqueness_constraints |
| `auto_transform`                | boolean | True    | -     | ✗    | ✗        | Automatically apply transformations to achieve compliance                                                                                   |
| `strict_mode`                   | boolean | False   | -     | ✗    | ✗        | Fail immediately on first critical violation (stops workflow)                                                                               |
| `drop_extra_columns`            | boolean | True    | -     | ✗    | ✗        | Drop columns not specified in contract                                                                                                      |
| `rename_columns`                | boolean | True    | -     | ✗    | ✗        | Apply column name mappings from contract                                                                                                    |
| `cast_types`                    | boolean | True    | -     | ✗    | ✗        | Attempt to cast columns to required types                                                                                                   |
| `enforce_values`                | boolean | True    | -     | ✗    | ✗        | Enforce value constraints (allowed values, ranges, patterns)                                                                                |
| `default_value_strategy`        | string  | "null"  | -     | ✗    | ✗        | Strategy for handling invalid values: null, default, or drop                                                                                |
| `structural_compliance_weight`  | float   | 0.4     | -     | ✗    | ✗        | Weight for structural compliance in overall score                                                                                           |
| `value_compliance_weight`       | float   | 0.4     | -     | ✗    | ✗        | Weight for value compliance in overall score                                                                                                |
| `transformation_success_weight` | float   | 0.2     | -     | ✗    | ✗        | Weight for transformation success in overall score                                                                                          |
| `excellent_threshold`           | integer | 95      | -     | ✗    | ✗        | Score threshold for compliant status                                                                                                        |
| `good_threshold`                | integer | 80      | -     | ✗    | ✗        | Score threshold for partially compliant status                                                                                              |

---

#### Semantic Mapper

**ID:** `semantic-mapper`

**Category:** Data Standardization

**Accuracy:** 95%

| Parameter Name           | Type    | Default | Range | Show | Required | Description                                                               |
| ------------------------ | ------- | ------- | ----- | ---- | -------- | ------------------------------------------------------------------------- |
| `custom_column_mappings` | object  | {}      | -     | ✓    | ✗        | Custom column name mappings (raw_name -> standard_name)                   |
| `custom_value_mappings`  | object  | {}      | -     | ✓    | ✗        | Custom value mappings by column (column -> {raw_value -> standard_value}) |
| `confidence_threshold`   | float   | 0.7     | -     | ✗    | ✗        | Minimum confidence score for automatic mapping                            |
| `auto_detect_semantics`  | boolean | True    | -     | ✗    | ✗        | Enable auto-detection of semantic patterns                                |
| `apply_mappings`         | boolean | True    | -     | ✗    | ✗        | Apply mappings to transform the data                                      |
| `name_similarity_weight` | float   | 0.4     | -     | ✗    | ✗        | Weight for name similarity in scoring                                     |
| `pattern_match_weight`   | float   | 0.3     | -     | ✗    | ✗        | Weight for pattern matching in scoring                                    |
| `value_analysis_weight`  | float   | 0.3     | -     | ✗    | ✗        | Weight for value analysis in scoring                                      |
| `excellent_threshold`    | integer | 90      | -     | ✗    | ✗        | Score threshold for excellent quality status                              |
| `good_threshold`         | integer | 75      | -     | ✗    | ✗        | Score threshold for good quality status                                   |

---

#### Survivorship Resolver

**ID:** `survivorship-resolver`

**Category:** Conflict Resolution

**Accuracy:** 96%

| Parameter Name             | Type    | Default         | Range | Show | Required | Description                                                                                                                              |
| -------------------------- | ------- | --------------- | ----- | ---- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `match_key_columns`        | array   | []              | -     | ✓    | ✓        | Columns to use for identifying related records                                                                                           |
| `survivorship_rules`       | object  | {}              | -     | ✓    | ✗        | Column -> rule mapping (freshness, quality_score, completeness, source_priority, frequency, richness, validation, min, max, first, last) |
| `source_priority`          | object  | {}              | -     | ✓    | ✗        | Source -> priority mapping (lower = higher priority)                                                                                     |
| `source_column`            | string  | null            | -     | ✓    | ✓        | Column identifying the record source                                                                                                     |
| `timestamp_column`         | string  | null            | -     | ✓    | ✗        | Column for freshness-based resolution                                                                                                    |
| `default_rule`             | string  | "quality_score" | -     | ✗    | ✗        | Default rule when no specific rule is defined                                                                                            |
| `min_confidence_threshold` | float   | 0.5             | -     | ✗    | ✗        | Minimum confidence for considering a resolution successful                                                                               |
| `field_validation_rules`   | object  | {}              | -     | ✓    | ✗        | Field-specific validation rules (column -> {pattern, min_length, allowed_values})                                                        |
| `excellent_threshold`      | integer | 90              | -     | ✗    | ✗        | Score threshold for excellent quality status                                                                                             |
| `good_threshold`           | integer | 75              | -     | ✗    | ✗        | Score threshold for good quality status                                                                                                  |

---

#### Golden Record Builder

**ID:** `golden-record-builder`

**Category:** Master Data

**Accuracy:** 97%

| Parameter Name              | Type    | Default         | Range | Show | Required | Description                                                                                                |
| --------------------------- | ------- | --------------- | ----- | ---- | -------- | ---------------------------------------------------------------------------------------------------------- |
| `match_key_columns`         | array   | []              | -     | ✓    | ✓        | Columns to use for identifying related records                                                             |
| `survivorship_rules`        | object  | {}              | -     | ✓    | ✗        | Column -> rule mapping (most_complete, most_recent, source_priority, most_frequent, min, max, first, last) |
| `source_priority`           | object  | {}              | -     | ✓    | ✗        | Source -> priority mapping for source_priority rule                                                        |
| `source_column`             | string  | null            | -     | ✓    | ✓        | Column identifying the record source                                                                       |
| `timestamp_column`          | string  | null            | -     | ✓    | ✗        | Column for recency-based survivorship rules                                                                |
| `default_survivorship_rule` | string  | "most_complete" | -     | ✗    | ✗        | Default rule when no specific rule is defined                                                              |
| `min_trust_score`           | float   | 0.5             | -     | ✗    | ✗        | Minimum trust score threshold for flagging records                                                         |
| `enable_fuzzy_matching`     | boolean | False           | -     | ✗    | ✗        | Enable fuzzy matching for record clustering                                                                |
| `fuzzy_threshold`           | float   | 80.0            | -     | ✗    | ✗        | Similarity threshold (0-100) for fuzzy matching                                                            |
| `fuzzy_config`              | object  | {}              | -     | ✓    | ✗        | Configuration for fuzzy matching (columns -> {type, weight})                                               |
| `excellent_threshold`       | integer | 90              | -     | ✗    | ✗        | Score threshold for excellent quality status                                                               |
| `good_threshold`            | integer | 75              | -     | ✗    | ✗        | Score threshold for good quality status                                                                    |

---

#### Stewardship Flagger

**ID:** `stewardship-flagger`

**Category:** Governance

**Accuracy:** 95%

| Parameter Name           | Type    | Default                                                               | Range | Show | Required | Description                                                                            |
| ------------------------ | ------- | --------------------------------------------------------------------- | ----- | ---- | -------- | -------------------------------------------------------------------------------------- |
| `required_columns`       | array   | []                                                                    | -     | ✓    | ✗        | List of columns that must have values                                                  |
| `confidence_threshold`   | float   | 0.7                                                                   | -     | ✗    | ✗        | Minimum confidence score threshold                                                     |
| `confidence_columns`     | array   | []                                                                    | -     | ✓    | ✗        | Columns containing confidence scores to evaluate                                       |
| `field_validation_rules` | object  | {}                                                                    | -     | ✓    | ✗        | Field-specific validation rules (column -> {pattern, min_length, allowed_values})      |
| `outlier_thresholds`     | object  | {"age": {"min": 0, "max": 120}, "percentage": {"min": 0, "max": 100}} | -     | ✓    | ✗        | Field-specific outlier thresholds (field_type or column -> {min, max})                 |
| `duplicate_key_columns`  | array   | []                                                                    | -     | ✓    | ✗        | Columns to use for duplicate detection                                                 |
| `business_rules`         | array   | []                                                                    | -     | ✓    | ✗        | Custom business rules [{name, condition: {column, operator, value}, severity, action}] |
| `severity_weights`       | object  | {"critical": 4, "high": 3, "medium": 2, "low": 1}                     | -     | ✗    | ✗        | Weights for severity levels in scoring                                                 |
| `excellent_threshold`    | integer | 90                                                                    | -     | ✗    | ✗        | Score threshold for excellent quality status                                           |
| `good_threshold`         | integer | 75                                                                    | -     | ✗    | ✗        | Score threshold for good quality status                                                |

---

### PROFILE MY DATA AGENTS

#### Unified Profiler

**ID:** `unified-profiler`

**Category:** Data Analysis

**Accuracy:** 99%

| Parameter Name                | Type    | Default | Range | Show | Required | Description                               |
| ----------------------------- | ------- | ------- | ----- | ---- | -------- | ----------------------------------------- |
| `null_alert_threshold`        | integer | 50      | -     | ✗    | ✗        | Threshold for null value alerts (%)       |
| `categorical_threshold`       | integer | 20      | -     | ✗    | ✗        | Threshold for categorical field detection |
| `categorical_ratio_threshold` | float   | 0.05    | -     | ✗    | ✗        | Ratio threshold for categorical analysis  |
| `top_n_values`                | integer | 10      | -     | ✗    | ✗        | Number of top values to track             |
| `outlier_iqr_multiplier`      | float   | 1.5     | -     | ✗    | ✗        | IQR multiplier for outlier detection      |
| `outlier_alert_threshold`     | integer | 5       | -     | ✗    | ✗        | Threshold for outlier alerts (%)          |

---

#### Drift Detector

**ID:** `drift-detector`

**Category:** Comparison

**Accuracy:** 97%

| Parameter Name       | Type    | Default              | Range | Show | Required | Description                              |
| -------------------- | ------- | -------------------- | ----- | ---- | -------- | ---------------------------------------- |
| `statistical_test`   | string  | "kolmogorov_smirnov" | -     | ✗    | ✗        | Statistical test method                  |
| `significance_level` | float   | 0.05                 | -     | ✗    | ✗        | Significance level for statistical tests |
| `min_sample_size`    | integer | 100                  | -     | ✗    | ✗        | Minimum sample size for analysis         |

---

#### Risk Scorer

**ID:** `score-risk`

**Category:** Security

**Accuracy:** 96%

| Parameter Name                      | Type    | Default | Range | Show | Required | Description                                    |
| ----------------------------------- | ------- | ------- | ----- | ---- | -------- | ---------------------------------------------- |
| `pii_sample_size`                   | integer | 100     | -     | ✗    | ✗        | Sample size for PII detection                  |
| `high_risk_threshold`               | integer | 70      | -     | ✗    | ✗        | Score threshold for high risk classification   |
| `medium_risk_threshold`             | integer | 40      | -     | ✗    | ✗        | Score threshold for medium risk classification |
| `pii_detection_enabled`             | boolean | True    | -     | ✗    | ✗        | Enable PII detection                           |
| `sensitive_field_detection_enabled` | boolean | True    | -     | ✗    | ✗        | Enable sensitive field detection               |
| `governance_check_enabled`          | boolean | True    | -     | ✗    | ✗        | Enable governance checks                       |

---

#### Governance Checker

**ID:** `governance-checker`

**Category:** Governance

**Accuracy:** 95%

| Parameter Name                   | Type    | Default | Range | Show | Required | Description                             |
| -------------------------------- | ------- | ------- | ----- | ---- | -------- | --------------------------------------- |
| `lineage_weight`                 | float   | 0.3     | -     | ✗    | ✗        | Weight for lineage component            |
| `consent_weight`                 | float   | 0.4     | -     | ✗    | ✗        | Weight for consent component            |
| `classification_weight`          | float   | 0.3     | -     | ✗    | ✗        | Weight for classification component     |
| `compliance_threshold`           | integer | 80      | -     | ✗    | ✗        | Score threshold for compliant status    |
| `needs_review_threshold`         | integer | 60      | -     | ✗    | ✗        | Score threshold for needs review status |
| `required_lineage_fields`        | array   | []      | -     | ✓    | ✗        | List of required lineage fields         |
| `required_consent_fields`        | array   | []      | -     | ✓    | ✗        | List of required consent fields         |
| `required_classification_fields` | array   | []      | -     | ✓    | ✗        | List of required classification fields  |

---

#### Test Coverage Agent

**ID:** `test-coverage-agent`

**Category:** Testing

**Accuracy:** 97%

| Parameter Name        | Type    | Default | Range | Show | Required | Description                                                                  |
| --------------------- | ------- | ------- | ----- | ---- | -------- | ---------------------------------------------------------------------------- |
| `uniqueness_weight`   | float   | 0.4     | -     | ✗    | ✗        | Weight for uniqueness tests                                                  |
| `range_weight`        | float   | 0.3     | -     | ✗    | ✗        | Weight for range tests                                                       |
| `format_weight`       | float   | 0.3     | -     | ✗    | ✗        | Weight for format tests                                                      |
| `excellent_threshold` | integer | 90      | -     | ✗    | ✗        | Score threshold for excellent status                                         |
| `good_threshold`      | integer | 75      | -     | ✗    | ✗        | Score threshold for good status                                              |
| `unique_columns`      | array   | []      | -     | ✓    | ✗        | List of columns that should have unique values                               |
| `range_tests`         | object  | {}      | -     | ✓    | ✗        | Range constraints for numeric columns (column -> {min, max})                 |
| `format_tests`        | object  | {}      | -     | ✓    | ✗        | Format constraints for columns (column -> pattern or {pattern, description}) |

---

#### Readiness Rater

**ID:** `readiness-rater`

**Category:** Quality Assessment

**Accuracy:** 98%

| Parameter Name           | Type    | Default | Range | Show | Required | Description                                       |
| ------------------------ | ------- | ------- | ----- | ---- | -------- | ------------------------------------------------- |
| `ready_threshold`        | integer | 80      | -     | ✗    | ✗        | Score threshold for 'READY' status (0-100)        |
| `needs_review_threshold` | integer | 50      | -     | ✗    | ✗        | Score threshold for 'NEEDS_REVIEW' status (0-100) |
| `completeness_weight`    | float   | 0.3     | -     | ✗    | ✗        | Weight for completeness component                 |
| `consistency_weight`     | float   | 0.3     | -     | ✗    | ✗        | Weight for consistency component                  |
| `schema_health_weight`   | float   | 0.4     | -     | ✗    | ✗        | Weight for schema health component                |

---

## Parameter Type Frequency Analysis

### By Type Across All Agents:

| Type        | Count | Percentage |
| ----------- | ----- | ---------- |
| **array**   | 17    | 8.4%       |
| **float**   | 62    | 30.7%      |
| **boolean** | 38    | 18.8%      |
| **integer** | 46    | 22.8%      |
| **object**  | 23    | 11.4%      |
| **string**  | 16    | 7.9%       |

---

## Common Parameter Patterns

### Weight Parameters (0-1 range)

Used across all agents for scoring components:

- `accuracy_weight`
- `safety_weight`
- `completeness_weight`
- `data_retention_weight`
- `column_retention_weight`
- `structural_compliance_weight`
- `value_compliance_weight`
- `transformation_success_weight`
- `lineage_weight`
- `consent_weight`
- `classification_weight`
- And many more...

### Threshold Parameters (0-100 range)

Used for quality scoring and classification:

- `excellent_threshold`
- `good_threshold`
- `high_risk_threshold`
- `medium_risk_threshold`
- `compliance_threshold`
- `needs_review_threshold`
- `ready_threshold`

### Detection/Toggle Parameters (boolean)

Feature flags for enabling/disabling specific capabilities:

- `detect_*` parameters
- `auto_*` parameters
- `enable_*` parameters
- `*_enabled` parameters

### Mapping/Constraint Parameters (object)

Complex configurations for rule-based processing:

- `*_mappings` parameters
- `*_constraints` parameters
- `*_rules` parameters

### Column/Field List Parameters (array)

Lists of columns for specific operations:

- `required_columns`
- `target_columns`
- `preserve_columns`
- `unique_columns`
- `email_columns`
- `key_columns`

---

## Tools Summary Table

| Tool            | ID              | Agents | Total Parameters | Avg Per Agent |
| --------------- | --------------- | ------ | ---------------- | ------------- |
| Clean My Data   | clean-my-data   | 8      | 98               | 12.2          |
| Master My Data  | master-my-data  | 6      | 68               | 11.3          |
| Profile My Data | profile-my-data | 6      | 36               | 6.0           |

---

## Parameter Best Practices

### For Configuration:

1. **Threshold parameters** should be tuned based on your data characteristics
2. **Weight parameters** should sum to 1.0 for normalized scoring
3. **Array parameters** (columns, rules) should match your actual data schema
4. **Object parameters** (mappings, constraints) require specific structures

### Default Recommendations:

- **Low-risk operations**: Use default parameters
- **High-quality requirements**: Increase threshold values (80-95)
- **Large datasets**: Adjust `sample_size` and `top_n_values` accordingly
- **Custom rules**: Leverage `*_mappings` and `*_rules` parameters

---

## Version Information

- **Clean My Data**: v1.0.0
- **Master My Data**: v1.0.0
- **Profile My Data**: v2.0.0
- **Document Generated**: 2025-12-11

---

## Notes

- This document is auto-generated from tool configuration files
- Parameter ranges and defaults are as specified in official tool definitions
- For updates or changes, refer to individual tool JSON files
- Contact Data Governance team for parameter optimization guidance
