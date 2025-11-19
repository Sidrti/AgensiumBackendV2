# Alerts, Issues, and Recommendations Structure

**Documentation Version:** 1.0  
**Last Updated:** November 18, 2025  
**Purpose:** Complete structure and patterns for Alerts, Issues, and Recommendations across all agents

---

## Table of Contents

1. [Overview](#overview)
2. [Alerts Structure](#alerts-structure)
3. [Issues Structure](#issues-structure)
4. [Recommendations Structure](#recommendations-structure)
5. [Agent-Specific Patterns](#agent-specific-patterns)
6. [Best Practices](#best-practices)

---

## Overview

All agents in the AgensiumBackendV2 system generate three critical types of output:

- **Alerts**: High-level notifications about data quality problems requiring immediate attention
- **Issues**: Granular field/row-level problems discovered during analysis
- **Recommendations**: Actionable guidance for improving data quality

### Common Design Principles

1. **Severity Levels**: `critical` > `high` > `medium` > `low`
2. **Structured Format**: All three follow consistent JSON schemas
3. **Actionability**: Each item includes specific remediation guidance
4. **Traceability**: Links to affected fields/rows for investigation
5. **Prioritization**: Ordered by severity and impact

---

## Alerts Structure

### Schema Definition

```python
{
    "alert_id": str,              # Unique identifier (e.g., "alert_nulls_high_volume")
    "severity": str,               # "critical", "high", "medium", "low"
    "category": str,               # Classification (e.g., "missing_data", "data_quality")
    "message": str,                # Human-readable alert message
    "affected_fields_count": int,  # Number of fields/records impacted
    "recommendation": str          # Immediate remediation guidance
}
```

### Severity Guidelines

| Severity     | Description                                   | Example Scenarios                                    |
| ------------ | --------------------------------------------- | ---------------------------------------------------- |
| **Critical** | Data is unusable or violates compliance       | >50% nulls, PII without encryption, schema collapse  |
| **High**     | Significant quality issues affecting analysis | >30% outliers, high duplicate rate, type mismatches  |
| **Medium**   | Moderate issues requiring attention           | 10-30% data quality problems, format inconsistencies |
| **Low**      | Minor issues, best practice violations        | <10% issues, optimization opportunities              |

### Category Taxonomy

```
Data Quality Categories:
├── missing_data
├── data_quality
├── data_distribution
├── data_retention
├── data_integrity
├── column_quality
├── field_consistency
└── duplicate_rows

Risk & Compliance:
├── pii_detected
├── sensitive_data
├── risk_compliance
├── governance_compliance
└── compliance

Performance & Technical:
├── quality_score
├── effectiveness
├── execution_safety
└── processing_efficiency
```

### Alert Generation Patterns by Agent

#### 1. **Null Handler Agent**

```python
# High null volume alert
if null_percentage > 30:
    alerts.append({
        "alert_id": "alert_nulls_high_volume",
        "severity": "critical",
        "category": "missing_data",
        "message": f"High null volume: {null_count} null values ({null_percentage:.1f}%)",
        "affected_fields_count": len(columns_with_nulls),
        "recommendation": "Review data collection process. High null rate indicates systemic issues."
    })

# Column-level critical nulls
if null_percentage_in_column > 50:
    alerts.append({
        "alert_id": "alert_nulls_column_critical",
        "severity": "high",
        "category": "column_quality",
        "message": f"{column_count} column(s) have >50% null values",
        "affected_fields_count": column_count,
        "recommendation": "Consider dropping columns with excessive nulls or advanced imputation."
    })
```

#### 2. **Outlier Remover Agent**

```python
# High outlier volume
if outlier_percentage > 20:
    alerts.append({
        "alert_id": "alert_outliers_high_volume",
        "severity": "critical",
        "category": "data_distribution",
        "message": f"High outlier volume: {outlier_count} outliers ({outlier_percentage:.1f}%)",
        "affected_fields_count": affected_columns,
        "recommendation": "Review data distribution. High outlier rate may indicate measurement errors."
    })
```

#### 3. **Duplicate Resolver Agent**

```python
# High duplicate volume
if duplicate_percentage > 30:
    alerts.append({
        "alert_id": "alert_duplicates_high_volume",
        "severity": "critical",
        "category": "data_uniqueness",
        "message": f"High duplicate volume: {duplicate_count} duplicates ({duplicate_percentage:.1f}%)",
        "affected_fields_count": detection_methods_count,
        "recommendation": "Review data collection process. High duplicate rate indicates systemic issues."
    })
```

#### 4. **Field Standardization Agent**

```python
# High field variation
if variation_count > columns * 10:
    alerts.append({
        "alert_id": "alert_standardization_high_variations",
        "severity": "high",
        "category": "field_consistency",
        "message": f"High field variation: {variation_count} variations across {columns} columns",
        "affected_fields_count": columns_count,
        "recommendation": "Implement standardization rules and data entry validation."
    })
```

#### 5. **Risk Scorer Agent**

```python
# PII detection alert
if pii_fields_detected > 0:
    alerts.append({
        "alert_id": "alert_pii_001",
        "severity": "critical",
        "category": "pii_detected",
        "message": f"{pii_fields_detected} PII field(s) detected",
        "affected_fields_count": pii_fields_detected,
        "recommendation": "Implement encryption at rest/transit, restrict access, audit logging."
    })

# GDPR compliance
if gdpr_applicable:
    alerts.append({
        "alert_id": "alert_compliance_gdpr",
        "severity": "critical",
        "category": "compliance",
        "message": "GDPR compliance requirements detected",
        "affected_fields_count": gdpr_field_count,
        "recommendation": "Ensure GDPR compliance: encryption, access controls, consent management."
    })
```

#### 6. **Governance Checker Agent**

```python
# Non-compliant governance
if compliance_status != "compliant":
    alerts.append({
        "alert_id": "alert_governance_001",
        "severity": "critical" if status == "non_compliant" else "high",
        "category": "governance_compliance",
        "message": f"Governance compliance: {score:.1f}/100 ({status.upper()})",
        "affected_fields_count": issues_count,
        "recommendation": f"Address {issues_count} governance issue(s) immediately."
    })
```

#### 7. **Drift Detector Agent**

```python
# Distribution drift detected
if drift_detected_count > 0:
    alerts.append({
        "alert_id": "alert_drift_001",
        "severity": "high",
        "category": "drift",
        "message": f"Distribution drift in {drift_count}/{total_fields} fields ({drift_pct:.1f}%)",
        "affected_fields_count": drift_count,
        "recommendation": f"{drift_count} field(s) showing drift. Retrain ML models."
    })
```

#### 8. **Cleanse Previewer Agent**

```python
# High-impact cleaning operations
if high_impact_rules > 0:
    alerts.append({
        "alert_id": "alert_preview_high_impact",
        "severity": "critical" if unsafe else "high",
        "category": "cleaning_impact",
        "message": f"{high_impact_rules} high-impact cleaning rule(s) detected",
        "affected_fields_count": high_impact_rules,
        "recommendation": "Review high-impact rules before execution. Consider backups."
    })
```

#### 9. **Cleanse Writeback Agent**

```python
# Integrity verification failure
if not data_ready:
    alerts.append({
        "alert_id": "alert_writeback_integrity_failure",
        "severity": "critical",
        "category": "data_integrity",
        "message": f"Integrity verification FAILED: {failed_checks} checks failed",
        "affected_fields_count": failed_checks,
        "recommendation": "Data NOT ready for pipeline. Address all failures immediately."
    })
```

#### 10. **Quarantine Agent**

```python
# High quarantine volume
if quarantine_percentage > 30:
    alerts.append({
        "alert_id": "alert_quarantine_high_volume",
        "severity": "critical",
        "category": "data_quality",
        "message": f"High quarantine volume: {quarantine_count} records ({quarantine_pct:.1f}%)",
        "affected_fields_count": issue_types_count,
        "recommendation": "Review data source quality. High quarantine rate indicates systemic issues."
    })
```

#### 11. **Readiness Rater Agent**

```python
# Dataset not ready
if status != "ready":
    alerts.append({
        "alert_id": "alert_readiness_001",
        "severity": "critical" if status == "not_ready" else "high",
        "category": "data_readiness",
        "message": f"Data readiness: {score:.1f}/100 ({status.upper()})",
        "affected_fields_count": issues_count,
        "recommendation": f"Fix {issues_count} issue(s) before production use."
    })
```

---

## Issues Structure

### Schema Definition

```python
{
    "issue_id": str,        # Unique identifier (e.g., "issue_nulls_15_email_null_value")
    "agent_id": str,        # Source agent (e.g., "null-handler")
    "field_name": str,      # Affected field/column name
    "issue_type": str,      # Classification (e.g., "null_value", "type_mismatch")
    "severity": str,        # "critical", "high", "medium", "low", "warning", "info"
    "message": str          # Detailed issue description
}
```

### Issue Type Taxonomy

```
Data Quality Issues:
├── null_value
├── type_mismatch
├── outlier_detected
├── duplicate_record
├── field_standardized
├── out_of_range
├── invalid_format
├── corrupted_record
└── missing_required_field

Risk & Compliance:
├── pii_detected
├── pii_email_address
├── pii_phone_number
├── pii_ssn
├── sensitive_personal_data
├── compliance_violation
└── governance_violation

Distribution & Drift:
├── distribution_drift
├── mean_shift
├── variance_shift
├── missing_column
└── new_column

Data Integrity:
├── integrity_verification_failure
├── schema_mismatch
├── data_retention
└── preview_issue
```

### Severity-Based Issue Handling

| Severity     | Action Required            | Example Issues                                             |
| ------------ | -------------------------- | ---------------------------------------------------------- |
| **Critical** | Immediate blocking         | PII without encryption, integrity failure, schema collapse |
| **High**     | Must fix before production | Type mismatches, high outliers, missing required fields    |
| **Medium**   | Should fix soon            | Format inconsistencies, moderate outliers                  |
| **Low**      | Nice to fix                | Minor standardization opportunities                        |
| **Warning**  | Monitor                    | Potential issues requiring validation                      |
| **Info**     | Informational              | Successful transformations, statistics                     |

### Issue Generation Patterns by Agent

#### 1. **Null Handler Agent**

```python
# Row-level null issues
for idx, row in original_df.iterrows():
    null_cols = row[row.isnull()].index.tolist()
    if null_cols:
        for col in null_cols:
            issues.append({
                "issue_id": f"issue_nulls_{idx}_{col}",
                "agent_id": "null-handler",
                "field_name": col,
                "issue_type": "null_value",
                "severity": "warning",
                "message": f"Null value found in column '{col}'"
            })
```

#### 2. **Outlier Remover Agent**

```python
# Outlier detection issues
for outlier in detected_outliers:
    issues.append({
        "issue_id": f"issue_outliers_{outlier['row_index']}_{outlier['column']}",
        "agent_id": "outlier-remover",
        "field_name": outlier['column'],
        "issue_type": "outlier_detected",
        "severity": outlier['severity'],  # "critical" or "warning"
        "message": f"Outlier detected: value {outlier['value']} (z-score: {outlier['z_score']:.2f})"
    })
```

#### 3. **Duplicate Resolver Agent**

```python
# Duplicate record issues
for dup in duplicate_records:
    issues.append({
        "issue_id": f"issue_duplicates_{dup['row_index']}_duplicate",
        "agent_id": "duplicate-resolver",
        "field_name": "record",
        "issue_type": "duplicate_record",
        "severity": "warning",
        "message": f"Duplicate record detected (method: {dup['detection_method']})"
    })
```

#### 4. **Field Standardization Agent**

```python
# Standardization applied issues (informational)
for standardization in standardizations_applied:
    issues.append({
        "issue_id": f"issue_standardization_{std['row_index']}_{std['column']}",
        "agent_id": "field-standardization",
        "field_name": std['column'],
        "issue_type": "field_standardized",
        "severity": "info",
        "message": f"Standardized: '{std['original_value']}' → '{std['standardized_value']}'"
    })
```

#### 5. **Type Fixer Agent**

```python
# Type mismatch issues
for type_issue in type_mismatches:
    issues.append({
        "issue_id": f"issue_types_{issue['column']}_type_mismatch",
        "agent_id": "type-fixer",
        "field_name": issue['column'],
        "issue_type": "type_mismatch",
        "severity": "warning",
        "message": f"Type mismatch: expected {issue['expected_type']}, found {issue['actual_type']}"
    })
```

#### 6. **Risk Scorer Agent**

```python
# PII detection issues
for pii_field in pii_fields:
    issues.append({
        "issue_id": f"issue_pii_{field['id']}_{field['pii_type']}",
        "agent_id": "score-risk",
        "field_name": field['name'],
        "issue_type": f"pii_{field['pii_type']}",
        "severity": "critical",
        "message": f"PII detected: {field['pii_type']} (confidence: {field['confidence']:.0%})"
    })

# Compliance violation issues
for violation in compliance_violations:
    issues.append({
        "issue_id": f"issue_compliance_{violation['field_id']}_{violation['idx']}",
        "agent_id": "score-risk",
        "field_name": violation['field_name'],
        "issue_type": "compliance_violation",
        "severity": "critical" if "HIPAA" in violation['message'] else "high",
        "message": violation['message']
    })
```

#### 7. **Governance Checker Agent**

```python
# Governance compliance issues
for gov_issue in governance_issues:
    issues.append({
        "issue_id": f"issue_governance_{gov_issue['type']}_{gov_issue['field']}",
        "agent_id": "governance-checker",
        "field_name": gov_issue['field'],
        "issue_type": gov_issue['type'],  # "missing_lineage_field", "missing_consent_field"
        "severity": gov_issue['severity'],  # "critical", "high"
        "message": gov_issue['message']
    })
```

#### 8. **Drift Detector Agent**

```python
# Distribution drift issues
for drift_field in drifted_fields:
    issues.append({
        "issue_id": f"issue_drift_{drift_field['field_id']}",
        "agent_id": "drift-detector",
        "field_name": drift_field['field_name'],
        "issue_type": "distribution_drift",
        "severity": drift_field['severity'],  # Based on PSI score
        "message": f"Significant distribution drift (PSI: {drift_field['psi_score']:.4f})"
    })

# Mean shift issues
if mean_shift_significant:
    issues.append({
        "issue_id": f"issue_drift_mean_{field_id}",
        "agent_id": "drift-detector",
        "field_name": field_name,
        "issue_type": "mean_shift",
        "severity": "high" if shift_pct > 25 else "medium",
        "message": f"Mean shifted by {change:.2f} ({shift_pct:.1f}%)"
    })
```

#### 9. **Cleanse Previewer Agent**

```python
# Preview impact issues
for impact_issue in impact_issues:
    issues.append({
        "issue_id": f"issue_preview_{issue['rule_id']}_{issue['issue_type']}",
        "agent_id": "cleanse-previewer",
        "field_name": issue['rule_id'],
        "issue_type": issue['issue_type'],
        "severity": issue['severity'],
        "message": issue['description']
    })
```

#### 10. **Cleanse Writeback Agent**

```python
# Integrity verification issues
for integrity_issue in integrity_issues:
    issues.append({
        "issue_id": f"issue_writeback_{issue['check_name']}",
        "agent_id": "cleanse-writeback",
        "field_name": issue['check_name'],
        "issue_type": "integrity_verification_failure",
        "severity": "high",
        "message": issue['message']
    })
```

#### 11. **Quarantine Agent**

```python
# Quarantined record issues
for q_issue in quarantine_issues:
    issues.append({
        "issue_id": f"issue_quarantine_{q_issue['row_index']}_{q_issue['issue_type']}",
        "agent_id": "quarantine-agent",
        "field_name": q_issue['column'],
        "issue_type": q_issue['issue_type'],  # "missing_required_field", "type_mismatch", etc.
        "severity": q_issue['severity'],
        "message": q_issue['description']
    })
```

#### 12. **Readiness Rater Agent**

```python
# Readiness deduction issues
for deduction in deductions:
    for field in deduction.get("fields_affected", []):
        issues.append({
            "issue_id": f"issue_readiness_{field}_{deduction['deduction_reason']}",
            "agent_id": "readiness-rater",
            "field_name": field,
            "issue_type": deduction['deduction_reason'],  # "missing_values", "format_inconsistency"
            "severity": deduction['severity'],
            "message": deduction['remediation']
        })
```

---

## Recommendations Structure

### Schema Definition

```python
{
    "recommendation_id": str,  # Unique identifier (e.g., "rec_nulls_drop_columns")
    "agent_id": str,           # Source agent (e.g., "null-handler")
    "field_name": str,         # Affected field(s) or "all" for dataset-level
    "priority": str,           # "critical", "high", "medium", "low"
    "recommendation": str,     # Actionable guidance
    "timeline": str            # Expected timeframe (e.g., "immediate", "1 week", "2-3 weeks")
}
```

### Priority & Timeline Guidelines

| Priority     | Timeline Options                | Use Cases                                                                     |
| ------------ | ------------------------------- | ----------------------------------------------------------------------------- |
| **Critical** | "immediate"                     | Data integrity failures, blocking compliance issues, security vulnerabilities |
| **High**     | "1 week", "1-2 weeks"           | Significant quality issues, performance problems, non-blocking compliance     |
| **Medium**   | "2 weeks", "2-3 weeks"          | Moderate improvements, optimization opportunities                             |
| **Low**      | "3 weeks", "4 weeks", "1 month" | Best practices, minor enhancements, documentation                             |

### Recommendation Generation Patterns by Agent

#### 1. **Null Handler Agent**

```python
# Critical: Drop high-null columns
if high_null_columns:
    recommendations.append({
        "recommendation_id": "rec_nulls_drop_columns",
        "agent_id": "null-handler",
        "field_name": ", ".join(high_null_columns[:3]),
        "priority": "high",
        "recommendation": f"Consider dropping {len(high_null_columns)} column(s) with >50% null values",
        "timeline": "1 week"
    })

# High: Advanced imputation
if medium_null_columns:
    recommendations.append({
        "recommendation_id": "rec_nulls_advanced_imputation",
        "agent_id": "null-handler",
        "field_name": ", ".join(medium_null_columns[:3]),
        "priority": "medium",
        "recommendation": f"Apply KNN or advanced imputation to {len(medium_null_columns)} column(s) with 20-50% nulls",
        "timeline": "2 weeks"
    })

# Medium: Strategy review
recommendations.append({
    "recommendation_id": "rec_nulls_strategy_review",
    "agent_id": "null-handler",
    "field_name": "all",
    "priority": "medium",
    "recommendation": f"Review imputation strategies for {len(imputation_log)} columns",
    "timeline": "2 weeks"
})

# High: Data source improvement
if null_percentage > 20:
    recommendations.append({
        "recommendation_id": "rec_nulls_source_quality",
        "agent_id": "null-handler",
        "field_name": "all",
        "priority": "high",
        "recommendation": "Improve data collection completeness at source to reduce null prevalence",
        "timeline": "1-2 weeks"
    })

# Low: Validation rules
recommendations.append({
    "recommendation_id": "rec_nulls_validation",
    "agent_id": "null-handler",
    "field_name": "all",
    "priority": "low",
    "recommendation": "Implement validation rules to prevent null values in critical fields at data entry",
    "timeline": "3 weeks"
})
```

#### 2. **Outlier Remover Agent**

```python
# High: Review high-outlier columns
if high_outlier_columns:
    recommendations.append({
        "recommendation_id": "rec_outliers_column_review",
        "agent_id": "outlier-remover",
        "field_name": ", ".join(high_outlier_columns[:3]),
        "priority": "high",
        "recommendation": f"Review {len(high_outlier_columns)} column(s) with >15% outliers for data quality issues",
        "timeline": "1 week"
    })

# Medium: Detection method optimization
recommendations.append({
    "recommendation_id": "rec_outliers_method",
    "agent_id": "outlier-remover",
    "field_name": "all",
    "priority": "medium",
    "recommendation": f"Optimize outlier detection method (current: {detection_method}) based on data distribution",
    "timeline": "2 weeks"
})

# High: Alternative strategy (if significant data loss)
if row_retention_rate < 90:
    recommendations.append({
        "recommendation_id": "rec_outliers_imputation",
        "agent_id": "outlier-remover",
        "field_name": "all",
        "priority": "high",
        "recommendation": "Consider imputation instead of removal to preserve data. Current strategy caused significant data loss.",
        "timeline": "1-2 weeks"
    })

# Medium: Statistical validation
recommendations.append({
    "recommendation_id": "rec_outliers_validation",
    "agent_id": "outlier-remover",
    "field_name": "all",
    "priority": "medium",
    "recommendation": "Validate detected outliers with domain experts to distinguish genuine outliers from valuable extreme values",
    "timeline": "2 weeks"
})

# Low: Monitoring
recommendations.append({
    "recommendation_id": "rec_outliers_monitoring",
    "agent_id": "outlier-remover",
    "field_name": "all",
    "priority": "low",
    "recommendation": "Establish outlier rate monitoring to detect distribution shifts or data quality degradation early",
    "timeline": "3 weeks"
})
```

#### 3. **Duplicate Resolver Agent**

```python
# Critical: Address conflicting duplicates
if conflicting_duplicates > 0:
    recommendations.append({
        "recommendation_id": "rec_duplicates_conflicts",
        "agent_id": "duplicate-resolver",
        "field_name": "multiple",
        "priority": "critical",
        "recommendation": f"Manually review and resolve {conflicting_duplicates} conflicting duplicate(s) with different values for same keys",
        "timeline": "immediate"
    })

# High: Unique constraints
if duplicate_percentage > 10:
    recommendations.append({
        "recommendation_id": "rec_duplicates_constraints",
        "agent_id": "duplicate-resolver",
        "field_name": "all",
        "priority": "high",
        "recommendation": "Implement unique key constraints at database level to prevent duplicate entry",
        "timeline": "1 week"
    })

# Medium: Merge strategy optimization
if rows_removed > original_rows * 0.1:
    recommendations.append({
        "recommendation_id": "rec_duplicates_merge_strategy",
        "agent_id": "duplicate-resolver",
        "field_name": "all",
        "priority": "medium",
        "recommendation": "Consider smart merge strategy instead of removal to preserve valuable information from duplicate records",
        "timeline": "2 weeks"
    })

# Medium: Data source improvement
recommendations.append({
    "recommendation_id": "rec_duplicates_source",
    "agent_id": "duplicate-resolver",
    "field_name": "all",
    "priority": "medium",
    "recommendation": "Review data entry and import processes to prevent duplicate creation at source",
    "timeline": "2 weeks"
})

# Low: Monitoring
recommendations.append({
    "recommendation_id": "rec_duplicates_monitoring",
    "agent_id": "duplicate-resolver",
    "field_name": "all",
    "priority": "low",
    "recommendation": "Establish duplicate rate monitoring and alerting to detect data quality degradation",
    "timeline": "3 weeks"
})
```

#### 4. **Field Standardization Agent**

```python
# High: Apply synonym mapping
if high_variation_columns:
    recommendations.append({
        "recommendation_id": "rec_standardization_synonyms",
        "agent_id": "field-standardization",
        "field_name": ", ".join(high_variation_columns[:3]),
        "priority": "high",
        "recommendation": f"Apply synonym mapping to {len(high_variation_columns)} high-variation column(s) to improve consistency",
        "timeline": "1 week"
    })

# Medium: Case strategy optimization
if case_strategy == 'none' and columns_needing_standardization > 0:
    recommendations.append({
        "recommendation_id": "rec_standardization_case",
        "agent_id": "field-standardization",
        "field_name": "all",
        "priority": "medium",
        "recommendation": "Enable case normalization (lowercase/uppercase/titlecase) to reduce case variations",
        "timeline": "2 weeks"
    })

# Medium: Whitespace handling
if not trim_whitespace or not normalize_internal_spacing:
    recommendations.append({
        "recommendation_id": "rec_standardization_whitespace",
        "agent_id": "field-standardization",
        "field_name": "all",
        "priority": "medium",
        "recommendation": "Enable whitespace trimming and internal spacing normalization for better consistency",
        "timeline": "2 weeks"
    })

# Medium: Data entry validation
recommendations.append({
    "recommendation_id": "rec_standardization_validation",
    "agent_id": "field-standardization",
    "field_name": "all",
    "priority": "medium",
    "recommendation": "Implement data entry validation rules to enforce standardization at source",
    "timeline": "2-3 weeks"
})

# Low: Continuous monitoring
recommendations.append({
    "recommendation_id": "rec_standardization_monitoring",
    "agent_id": "field-standardization",
    "field_name": "all",
    "priority": "low",
    "recommendation": "Establish field variation monitoring to detect standardization drift over time",
    "timeline": "3 weeks"
})
```

#### 5. **Type Fixer Agent**

```python
# Critical: Schema validation (if many issues)
if type_issues > column_count * 0.5:
    recommendations.append({
        "recommendation_id": "rec_types_schema_validation",
        "agent_id": "type-fixer",
        "field_name": "all",
        "priority": "critical",
        "recommendation": f"Implement schema validation at data ingestion to prevent {type_issues} type mismatches",
        "timeline": "immediate"
    })

# High: Handle failed conversions
if failed_conversions > 0:
    recommendations.append({
        "recommendation_id": "rec_types_failed_conversions",
        "agent_id": "type-fixer",
        "field_name": "multiple",
        "priority": "high",
        "recommendation": f"Review and fix {failed_conversions} failed type conversions with pre-cleaning or custom conversion logic",
        "timeline": "1-2 weeks"
    })

# Medium: Auto-conversion settings
recommendations.append({
    "recommendation_id": "rec_types_auto_conversion",
    "agent_id": "type-fixer",
    "field_name": "configuration",
    "priority": "medium",
    "recommendation": "Enable auto-conversion for numeric and datetime types to streamline type fixing process",
    "timeline": "2 weeks"
})

# Medium: Data validation
recommendations.append({
    "recommendation_id": "rec_types_validation",
    "agent_id": "type-fixer",
    "field_name": "all",
    "priority": "medium",
    "recommendation": "Add data validation rules to ensure converted values maintain semantic meaning",
    "timeline": "2 weeks"
})

# Low: Type documentation
recommendations.append({
    "recommendation_id": "rec_types_documentation",
    "agent_id": "type-fixer",
    "field_name": "all",
    "priority": "low",
    "recommendation": "Document expected data types for each column to prevent future type mismatches",
    "timeline": "3 weeks"
})
```

#### 6. **Risk Scorer Agent**

```python
# Critical: High-risk field security
for high_risk_field in high_risk_fields[:3]:
    recommendations.append({
        "recommendation_id": f"rec_risk_{field['id']}",
        "agent_id": "score-risk",
        "field_name": field['name'],
        "priority": "critical",
        "recommendation": f"Implement security measures for {field['name']}: encryption (AES-256), role-based access control, audit logging",
        "timeline": "immediate"
    })

# Critical: PII protection strategy
if pii_fields_detected > 0:
    recommendations.append({
        "recommendation_id": "rec_pii_handling",
        "agent_id": "score-risk",
        "field_name": f"{pii_fields_detected} fields",
        "priority": "critical",
        "recommendation": f"Implement PII protection strategy for {pii_fields_detected} field(s): anonymization, pseudonymization, or encryption",
        "timeline": "immediate"
    })

# High: Governance gaps
if governance_gaps > 0:
    recommendations.append({
        "recommendation_id": "rec_governance_gaps",
        "agent_id": "score-risk",
        "field_name": f"{governance_gaps} fields",
        "priority": "high",
        "recommendation": f"Address {governance_gaps} governance gap(s): implement data classification, lineage tracking, and access policies",
        "timeline": "1-2 weeks"
    })

# Critical: GDPR compliance
if "GDPR" in impacted_frameworks:
    recommendations.append({
        "recommendation_id": "rec_gdpr_compliance",
        "agent_id": "score-risk",
        "field_name": "all PII fields",
        "priority": "critical",
        "recommendation": "GDPR compliance: implement consent management, data portability, right to erasure, and breach notification procedures",
        "timeline": "2-4 weeks"
    })

# Critical: HIPAA compliance
if "HIPAA" in impacted_frameworks:
    recommendations.append({
        "recommendation_id": "rec_hipaa_compliance",
        "agent_id": "score-risk",
        "field_name": "all PHI fields",
        "priority": "critical",
        "recommendation": "HIPAA compliance: implement end-to-end encryption, access controls, audit trails, and Business Associate Agreements (BAAs)",
        "timeline": "immediate"
    })

# High: CCPA compliance
if "CCPA" in impacted_frameworks:
    recommendations.append({
        "recommendation_id": "rec_ccpa_compliance",
        "agent_id": "score-risk",
        "field_name": "all personal information",
        "priority": "high",
        "recommendation": "CCPA compliance: implement consumer rights mechanisms (access, delete, opt-out), privacy notices, and data inventory",
        "timeline": "2-3 weeks"
    })
```

#### 7. **Governance Checker Agent**

```python
# Critical: Critical governance issues
for critical_issue in critical_issues[:3]:
    recommendations.append({
        "recommendation_id": f"rec_governance_{issue['type']}_{issue['field']}",
        "agent_id": "governance-checker",
        "field_name": issue['field'],
        "priority": "critical",
        "recommendation": f"Address governance issue: {issue['message']}",
        "timeline": "immediate"
    })

# High: Data lineage tracking
if lineage_score < 80:
    recommendations.append({
        "recommendation_id": "rec_governance_lineage",
        "agent_id": "governance-checker",
        "field_name": ", ".join(missing_lineage_fields[:3]),
        "priority": "high",
        "recommendation": f"Implement data lineage tracking for {len(missing_lineage_fields)} field(s): document source systems, transformations, and data flow",
        "timeline": "2-3 weeks"
    })

# Critical: Consent management
if consent_score < 80:
    recommendations.append({
        "recommendation_id": "rec_governance_consent",
        "agent_id": "governance-checker",
        "field_name": ", ".join(missing_consent_fields[:3]),
        "priority": "critical",
        "recommendation": f"Implement consent management for {len(missing_consent_fields)} field(s): track user consent, preferences, and withdrawal requests",
        "timeline": "1-2 weeks"
    })

# High: Data classification
if classification_score < 80:
    recommendations.append({
        "recommendation_id": "rec_governance_classification",
        "agent_id": "governance-checker",
        "field_name": ", ".join(missing_classification_fields[:3]),
        "priority": "high",
        "recommendation": f"Implement data classification for {len(missing_classification_fields)} field(s): categorize as public, internal, confidential, or restricted",
        "timeline": "1-2 weeks"
    })

# Critical: PII protection
if pii_issues:
    recommendations.append({
        "recommendation_id": "rec_governance_pii_protection",
        "agent_id": "governance-checker",
        "field_name": ", ".join(pii_fields[:3]),
        "priority": "critical",
        "recommendation": f"Protect {len(pii_fields)} PII field(s): implement encryption, access controls, audit logging, and data masking",
        "timeline": "immediate"
    })

# Critical: Overall governance framework
if compliance_status == "non_compliant":
    recommendations.append({
        "recommendation_id": "rec_governance_overall",
        "agent_id": "governance-checker",
        "field_name": "entire dataset",
        "priority": "critical",
        "recommendation": f"Governance compliance is non-compliant ({score:.1f}/100). Implement comprehensive data governance framework with policies, procedures, and controls",
        "timeline": "4-6 weeks"
    })
```

#### 8. **Drift Detector Agent**

```python
# High: Model retraining
if drift_detected_count > 0:
    recommendations.append({
        "recommendation_id": "rec_drift_001",
        "agent_id": "drift-detector",
        "field_name": f"{drift_detected_count} fields",
        "priority": "high",
        "recommendation": f"Retrain ML models. {drift_detected_count} field(s) show significant distribution drift.",
        "timeline": "1 week"
    })

# Critical: High-severity drift fields
for high_severity_field in high_severity_fields[:3]:
    recommendations.append({
        "recommendation_id": f"rec_drift_high_{field['id']}",
        "agent_id": "drift-detector",
        "field_name": field['name'],
        "priority": "critical",
        "recommendation": f"Investigate {field['name']} - High drift detected (PSI: {field['psi']:.4f}). Review data collection process.",
        "timeline": "immediate"
    })

# Medium: Continuous monitoring
if drift_detected_count > 0:
    recommendations.append({
        "recommendation_id": "rec_drift_monitoring",
        "agent_id": "drift-detector",
        "field_name": "all fields",
        "priority": "medium",
        "recommendation": f"Implement continuous monitoring for {drift_detected_count} drifting field(s) to detect future changes",
        "timeline": "2-3 weeks"
    })

# Critical: Missing columns
if missing_columns:
    recommendations.append({
        "recommendation_id": "rec_drift_missing_cols",
        "agent_id": "drift-detector",
        "field_name": ", ".join(list(missing_columns)[:3]),
        "priority": "critical",
        "recommendation": f"{len(missing_columns)} column(s) missing from current dataset. Update data pipeline or impute missing columns",
        "timeline": "immediate"
    })

# Medium: New columns
if new_columns:
    recommendations.append({
        "recommendation_id": "rec_drift_new_cols",
        "agent_id": "drift-detector",
        "field_name": ", ".join(list(new_columns)[:3]),
        "priority": "medium",
        "recommendation": f"{len(new_columns)} new column(s) detected. Review schema changes and update models if needed",
        "timeline": "1-2 weeks"
    })
```

#### 9. **Cleanse Previewer Agent**

```python
# High: Review high-risk rules
if high_impact_rules > 0:
    recommendations.append({
        "recommendation_id": "rec_preview_001",
        "agent_id": "cleanse-previewer",
        "field_name": f"{high_impact_rules} rules",
        "priority": "high",
        "recommendation": f"Review {high_impact_rules} high-risk cleaning rule(s) before execution. Create backups.",
        "timeline": "1 week"
    })

# High: Data backup
if high_impact_rules > 0:
    recommendations.append({
        "recommendation_id": "rec_preview_backup",
        "agent_id": "cleanse-previewer",
        "field_name": "all",
        "priority": "high",
        "recommendation": "Create data backup before executing cleaning operations. High risk of significant data loss or corruption.",
        "timeline": "immediate"
    })

# Low: Safe to proceed
if preview_score >= 95:
    recommendations.append({
        "recommendation_id": "rec_preview_proceed",
        "agent_id": "cleanse-previewer",
        "field_name": "all",
        "priority": "low",
        "recommendation": "Preview analysis shows low risk. Safe to proceed with cleaning operations with confidence.",
        "timeline": "immediate"
    })

# Medium: Review before execution
elif preview_score >= 75:
    recommendations.append({
        "recommendation_id": "rec_preview_review",
        "agent_id": "cleanse-previewer",
        "field_name": "all",
        "priority": "medium",
        "recommendation": "Some operations may have moderate impact. Review changes before proceeding.",
        "timeline": "1 week"
    })

# High: Reconsider strategy
else:
    recommendations.append({
        "recommendation_id": "rec_preview_reconsider",
        "agent_id": "cleanse-previewer",
        "field_name": "all",
        "priority": "high",
        "recommendation": "Preview shows concerning changes. Consider revising cleaning strategy.",
        "timeline": "1 week"
    })
```

#### 10. **Cleanse Writeback Agent**

```python
# Critical: Fix integrity failures
if not data_ready:
    recommendations.append({
        "recommendation_id": "rec_writeback_integrity_failures",
        "agent_id": "cleanse-writeback",
        "field_name": ", ".join(failed_checks[:3]),
        "priority": "critical",
        "recommendation": f"CRITICAL: Fix {len(failed_checks)} failed integrity check(s) before proceeding: {', '.join(failed_checks)}",
        "timeline": "immediate"
    })

# High: Review manifest completeness
if manifest_transformation_count < agent_count * 2:
    recommendations.append({
        "recommendation_id": "rec_writeback_manifest",
        "agent_id": "cleanse-writeback",
        "field_name": "manifest",
        "priority": "high",
        "recommendation": f"Review manifest completeness: Only {manifest_transformation_count} transformations logged from {agent_count} agents",
        "timeline": "1 week"
    })

# High: Data retention review
if retention_rate < acceptable_threshold:
    recommendations.append({
        "recommendation_id": "rec_writeback_retention",
        "agent_id": "cleanse-writeback",
        "field_name": "all",
        "priority": "high",
        "recommendation": f"Review data retention: {retention_rate:.1f}% row retention is below acceptable threshold",
        "timeline": "1 week"
    })

# Low: Proceed to next tool
if data_ready:
    recommendations.append({
        "recommendation_id": "rec_writeback_proceed",
        "agent_id": "cleanse-writeback",
        "field_name": "all",
        "priority": "low",
        "recommendation": "Data package is verified and production-ready. Proceed to 'Master My Data' with confidence in data quality and lineage.",
        "timeline": "immediate"
    })

# Critical: Do not proceed
else:
    recommendations.append({
        "recommendation_id": "rec_writeback_review",
        "agent_id": "cleanse-writeback",
        "field_name": "all",
        "priority": "critical",
        "recommendation": "DO NOT proceed to next pipeline step. Address all integrity failures and re-run writeback verification.",
        "timeline": "immediate"
    })

# Low: Archive manifest
recommendations.append({
    "recommendation_id": "rec_writeback_audit",
    "agent_id": "cleanse-writeback",
    "field_name": "manifest",
    "priority": "low",
    "recommendation": "Archive comprehensive manifest for compliance and auditability requirements",
    "timeline": "2 weeks"
})
```

#### 11. **Quarantine Agent**

```python
# Critical: Address critical issues
if critical_issues > 0:
    recommendations.append({
        "recommendation_id": "rec_quarantine_critical",
        "agent_id": "quarantine-agent",
        "field_name": "multiple",
        "priority": "critical",
        "recommendation": f"Immediately review and fix {critical_issues} critical data integrity issues in quarantined records",
        "timeline": "immediate"
    })

# High: Investigate data source
if quarantine_percentage > 20:
    recommendations.append({
        "recommendation_id": "rec_quarantine_source",
        "agent_id": "quarantine-agent",
        "field_name": "all",
        "priority": "high",
        "recommendation": f"Investigate data source quality - {quarantine_percentage:.1f}% quarantine rate is excessive",
        "timeline": "1 week"
    })

# High: Schema validation
if 'schema_mismatch' in issue_types:
    recommendations.append({
        "recommendation_id": "rec_quarantine_schema",
        "agent_id": "quarantine-agent",
        "field_name": "schema",
        "priority": "high",
        "recommendation": "Implement schema validation at data ingestion to prevent schema mismatches",
        "timeline": "2 weeks"
    })

# Medium: Review quarantined data
if quarantine_count > 0:
    recommendations.append({
        "recommendation_id": "rec_quarantine_review",
        "agent_id": "quarantine-agent",
        "field_name": "all",
        "priority": "medium",
        "recommendation": f"Manually review quarantined data file to identify patterns and recovery opportunities",
        "timeline": "2 weeks"
    })

# Medium: Update detection rules
recommendations.append({
    "recommendation_id": "rec_quarantine_rules",
    "agent_id": "quarantine-agent",
    "field_name": "configuration",
    "priority": "medium",
    "recommendation": "Fine-tune quarantine detection rules based on observed patterns to reduce false positives",
    "timeline": "3 weeks"
})

# Low: Monitor trends
recommendations.append({
    "recommendation_id": "rec_quarantine_monitoring",
    "agent_id": "quarantine-agent",
    "field_name": "all",
    "priority": "low",
    "recommendation": "Establish quarantine rate monitoring and alerting to detect data quality degradation early",
    "timeline": "3 weeks"
})
```

#### 12. **Readiness Rater Agent**

```python
# Critical: Dataset not production-ready
if status == "not_ready":
    recommendations.append({
        "recommendation_id": "rec_readiness_overall",
        "agent_id": "readiness-rater",
        "field_name": "entire dataset",
        "priority": "critical",
        "recommendation": f"Dataset is not production-ready (score: {score:.1f}/100). Use 'Clean My Data' tool to improve quality before analysis",
        "timeline": "2-4 weeks"
    })

# High: Dataset needs review
elif status == "needs_review":
    recommendations.append({
        "recommendation_id": "rec_readiness_review",
        "agent_id": "readiness-rater",
        "field_name": "entire dataset",
        "priority": "high",
        "recommendation": f"Dataset needs review (score: {score:.1f}/100). Address identified issues before production deployment",
        "timeline": "1-2 weeks"
    })

# High: Improve completeness
if completeness_score < 80:
    recommendations.append({
        "recommendation_id": "rec_completeness_improvement",
        "agent_id": "readiness-rater",
        "field_name": f"{high_missing_fields_count} fields",
        "priority": "high" if completeness_status == "poor" else "medium",
        "recommendation": f"Improve completeness score ({completeness_score:.1f}/100): implement validation rules, impute missing values, or remove incomplete records",
        "timeline": "1-2 weeks"
    })

# Medium: Improve consistency
if consistency_score < 80:
    recommendations.append({
        "recommendation_id": "rec_consistency_improvement",
        "agent_id": "readiness-rater",
        "field_name": "data types",
        "priority": "medium",
        "recommendation": f"Improve consistency score ({consistency_score:.1f}/100): standardize data types and formats across fields",
        "timeline": "1 week"
    })

# High: Improve schema health
if schema_health < 80:
    recommendations.append({
        "recommendation_id": "rec_schema_improvement",
        "agent_id": "readiness-rater",
        "field_name": f"{unnamed_columns + null_columns} fields",
        "priority": "high" if schema_health_status == "poor" else "medium",
        "recommendation": f"Improve schema health ({schema_health:.1f}/100): rename unnamed columns, remove null-only columns, fix data type inconsistencies",
        "timeline": "1 week"
    })

# High: Remove duplicates
if duplicate_count > 0:
    recommendations.append({
        "recommendation_id": "rec_duplicates",
        "agent_id": "readiness-rater",
        "field_name": "N/A",
        "priority": "high" if duplicate_percentage > 10 else "medium",
        "recommendation": f"Remove or consolidate {duplicate_count} duplicate rows ({duplicate_percentage:.1f}%) to improve data quality",
        "timeline": "1 week"
    })
```

---

## Agent-Specific Patterns

### Pattern Summary Table

| Agent                     | Primary Alert Focus                         | Primary Issue Focus                                   | Recommendation Focus                                            |
| ------------------------- | ------------------------------------------- | ----------------------------------------------------- | --------------------------------------------------------------- |
| **Null Handler**          | High null volume, column criticality        | Row-level null values                                 | Drop columns, imputation strategies, source quality             |
| **Outlier Remover**       | High outlier volume, column distribution    | Outlier detection results                             | Column review, method optimization, validation                  |
| **Duplicate Resolver**    | High duplicate rate, conflicts              | Duplicate records detected                            | Conflict resolution, unique constraints, source improvement     |
| **Field Standardization** | High field variation, standardization needs | Standardization transformations                       | Synonym mapping, case/whitespace handling, validation           |
| **Type Fixer**            | Type mismatches, conversion failures        | Type mismatch details                                 | Schema validation, failed conversion handling, documentation    |
| **Risk Scorer**           | PII detection, compliance requirements      | PII/sensitive data, compliance violations             | Security measures, encryption, compliance frameworks            |
| **Governance Checker**    | Non-compliance, governance gaps             | Missing governance fields, PII without classification | Lineage tracking, consent management, classification            |
| **Drift Detector**        | Distribution drift, schema changes          | Drift per field, mean/variance shifts                 | Model retraining, monitoring, schema alignment                  |
| **Cleanse Previewer**     | High-impact operations, execution safety    | Rule impact analysis                                  | Review high-risk rules, backup recommendations                  |
| **Cleanse Writeback**     | Integrity verification failures             | Integrity check failures                              | Fix integrity issues, manifest completeness, pipeline readiness |
| **Quarantine Agent**      | High quarantine volume, critical issues     | Quarantined record details                            | Source investigation, schema validation, rule tuning            |
| **Readiness Rater**       | Dataset not ready, component scores         | Readiness deductions                                  | Overall readiness improvement, component-specific fixes         |

---

## Best Practices

### 1. **Alert Generation**

- **Prioritize by Impact**: Critical alerts should block production deployment
- **Provide Context**: Include affected field counts and percentages
- **Actionable Recommendations**: Every alert must have a clear next step
- **Avoid Alert Fatigue**: Only generate alerts for significant issues
- **Threshold-Based**: Use configurable thresholds to trigger alerts

### 2. **Issue Tracking**

- **Granular Detail**: Issues should be field/row-specific when possible
- **Severity Alignment**: Match severity to business impact
- **Limit Volume**: Return top 100 issues; provide summary statistics for more
- **Consistent IDs**: Use predictable ID patterns for tracking
- **Message Clarity**: Issues should be understandable by non-technical users

### 3. **Recommendation Generation**

- **Prioritize by Impact**: Critical recommendations require immediate action
- **Realistic Timelines**: Base timelines on typical implementation effort
- **Specific Guidance**: Avoid vague recommendations like "improve data quality"
- **Progressive Enhancement**: Order recommendations from critical to nice-to-have
- **Implementation Guidance**: Include what to do, not just what's wrong

### 4. **Cross-Agent Consistency**

- **Standardized Schemas**: All agents follow same alert/issue/recommendation structures
- **Severity Alignment**: Consistent interpretation of severity levels
- **Category Taxonomy**: Use established categories across all agents
- **ID Patterns**: Predictable naming conventions for tracking and deduplication
- **Message Templates**: Similar issues across agents should have similar messaging

### 5. **Performance Optimization**

- **Limit Issue Volume**: Cap at 100 issues per agent to prevent payload bloat
- **Prioritize Critical**: Return most severe issues first
- **Deduplication**: Prevent duplicate alerts/issues from multiple agents
- **Efficient Processing**: Generate alerts/issues during single data pass
- **Lazy Evaluation**: Only compute details when severity thresholds are met

### 6. **Integration Patterns**

- **API Response Structure**: Consistent placement in agent response JSON
- **Frontend Display**: Structured for dashboard visualization
- **Notification Systems**: Severity drives notification urgency
- **Workflow Integration**: Recommendations feed into task management
- **Audit Trail**: All alerts/issues/recommendations logged for compliance

### 7. **Evolution & Maintenance**

- **Version Control**: Track alert/issue patterns across agent versions
- **A/B Testing**: Validate recommendation effectiveness
- **Feedback Loop**: Adjust thresholds based on user feedback
- **Documentation**: Keep this guide updated as patterns evolve
- **Regression Testing**: Ensure consistent alert generation across updates

---

## Appendix: Quick Reference

### Severity Mapping

```
CRITICAL → immediate → Red
HIGH     → 1-2 weeks → Orange
MEDIUM   → 2-3 weeks → Yellow
LOW      → 3+ weeks  → Blue
```

### Common Alert IDs

```
alert_<agent>_<category>_<specific>
alert_nulls_high_volume
alert_pii_001
alert_governance_001
alert_drift_001
alert_readiness_001
```

### Common Issue Types

```
issue_<agent>_<row>_<column>_<type>
issue_nulls_15_email_null_value
issue_pii_user_id_pii_email_address
issue_types_age_type_mismatch
```

### Common Recommendation IDs

```
rec_<agent>_<action>
rec_nulls_drop_columns
rec_pii_handling
rec_governance_lineage
rec_drift_001
rec_readiness_overall
```

---

## Conclusion

This document provides a comprehensive guide to the structure and patterns of alerts, issues, and recommendations across all agents in the AgensiumBackendV2 system. By following these patterns and best practices, agents provide consistent, actionable, and valuable guidance for data quality improvement.

**For questions or updates, refer to the agent implementation files and update this documentation accordingly.**
