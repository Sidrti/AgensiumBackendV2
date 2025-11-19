"""
Readiness Rater Agent

Rates data readiness for analysis based on quality metrics and component scoring.
Input: CSV/JSON/XLSX file (primary)
Output: Uniform readiness rating structure matching API specification
"""

import pandas as pd
import io
import time
from typing import Dict, Any, Optional


def rate_readiness(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Rate data readiness based on quality metrics.
    
    Args:
        file_contents: File bytes
        filename: Original filename
        parameters: Agent parameters matching tool.json (ready_threshold, needs_review_threshold, component weights)
        
    Returns:
        Uniform output structure matching API_SPECIFICATION.js response format
    """
    
    start_time = time.time()
    parameters = parameters or {}
    
    # Get parameters with defaults (matching tool.json)
    ready_threshold = parameters.get("ready_threshold", 80)
    needs_review_threshold = parameters.get("needs_review_threshold", 50)
    completeness_weight = parameters.get("completeness_weight", 0.3)
    consistency_weight = parameters.get("consistency_weight", 0.3)
    schema_health_weight = parameters.get("schema_health_weight", 0.4)
    
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
        
        # Calculate completeness score
        total_cells = len(df) * len(df.columns)
        missing_cells = df.isna().sum().sum()
        completeness_score = ((total_cells - missing_cells) / total_cells * 100) if total_cells > 0 else 0
        
        # Calculate consistency score
        # Check for data type consistency within columns
        consistency_issues = 0
        for col in df.columns:
            col_data = df[col].dropna()
            if len(col_data) > 0:
                # Check if numeric column has non-numeric values (simple check)
                try:
                    pd.to_numeric(col_data)
                except:
                    # Mixed types in numeric-looking column
                    if any(c.isdigit() for c in str(col_data.iloc[0])):
                        consistency_issues += 1
        
        consistency_score = 100 - (consistency_issues / max(len(df.columns), 1) * 20)
        consistency_score = max(0, min(100, consistency_score))
        
        # Calculate schema health
        # Check for missing column names, unexpected nulls, etc.
        schema_health = 100
        
        # Count problematic columns
        null_columns = 0
        unnamed_columns = 0
        inconsistent_columns = 0
        
        for col in df.columns:
            # Deduct for columns with all nulls (completely unusable)
            if df[col].isna().all():
                null_columns += 1
                schema_health -= 15  # Significant deduction for unusable column
            
            # Deduct for unnamed/auto-generated columns
            if str(col).startswith('Unnamed'):
                unnamed_columns += 1
                schema_health -= 8  # Moderate deduction for unnamed columns
            
            # Check for inconsistent data types within column
            if df[col].dtype == 'object':
                non_null = df[col].dropna().astype(str)
                if len(non_null) > 0:
                    # Try to detect mixed types (e.g., some numeric-looking, some text)
                    numeric_like = non_null.str.match(r'^-?\d+\.?\d*$').sum()
                    if 0 < numeric_like < len(non_null) * 0.3:
                        inconsistent_columns += 1
                        schema_health -= 5  # Minor deduction for mixed types
        
        # Cap schema health at 0
        schema_health = max(0, min(100, schema_health))
        
        # Calculate weighted readiness score
        readiness_score = (completeness_score * completeness_weight + 
                          consistency_score * consistency_weight + 
                          schema_health * schema_health_weight)
        
        # Determine status
        if readiness_score >= ready_threshold:
            status = "ready"
            status_description = "Dataset is suitable for analytics and ML with minor improvements"
            recommendation = "Proceed with analysis - dataset meets quality standards"
        elif readiness_score >= needs_review_threshold:
            status = "needs_review"
            status_description = "Dataset requires review and potential improvements before use"
            recommendation = "Address identified issues before production use"
        else:
            status = "not_ready"
            status_description = "Dataset requires significant improvements before analysis"
            recommendation = "Use 'Clean My Data' tool to improve data quality"
        
        # Find issues (deductions)
        deductions = []
        
        # Check for missing values - calculate actual impact
        for col in df.columns:
            missing_pct = (df[col].isna().sum() / len(df) * 100) if len(df) > 0 else 0
            if missing_pct > 10:
                # Impact calculation: higher missing % = higher deduction
                deduction_amount = min(missing_pct / 5, 25)  # Max 25 point deduction
                
                deductions.append({
                    "deduction_reason": "missing_values",
                    "fields_affected": [col],
                    "deduction_amount": round(deduction_amount, 2),
                    "severity": "critical" if missing_pct > 80 else "high" if missing_pct > 50 else "medium" if missing_pct > 25 else "low",
                    "remediation": "Impute missing values using domain knowledge, statistical methods, or remove records"
                })
        
        # Check for format inconsistencies (e.g., date formats)
        date_patterns = ['date', 'time', 'created', 'updated', 'timestamp', 'datetime']
        for col in df.columns:
            col_lower = col.lower()
            if any(x in col_lower for x in date_patterns):
                try:
                    # Try to parse as datetime
                    pd.to_datetime(df[col].dropna())
                except:
                    # Failed to parse all values as datetime
                    unparseable_count = 0
                    for val in df[col].dropna():
                        try:
                            pd.to_datetime(val)
                        except:
                            unparseable_count += 1
                    
                    unparseable_pct = (unparseable_count / len(df[col].dropna()) * 100) if len(df[col].dropna()) > 0 else 0
                    
                    if unparseable_pct > 0:
                        deduction_amount = min(unparseable_pct / 10, 12)  # Max 12 point deduction
                        
                        deductions.append({
                            "deduction_reason": "format_inconsistency",
                            "fields_affected": [col],
                            "deduction_amount": round(deduction_amount, 2),
                            "severity": "high" if unparseable_pct > 25 else "medium" if unparseable_pct > 10 else "low",
                            "remediation": f"Standardize date/time format. {unparseable_pct:.1f}% of values have inconsistent format"
                        })
        
        # Check for outliers (data quality indicator)
        for col in df.columns:
            if df[col].dtype in ['int64', 'float64']:
                col_data = df[col].dropna()
                if len(col_data) > 0:
                    Q1 = col_data.quantile(0.25)
                    Q3 = col_data.quantile(0.75)
                    IQR = Q3 - Q1
                    
                    outliers = col_data[(col_data < (Q1 - 1.5 * IQR)) | (col_data > (Q3 + 1.5 * IQR))]
                    outlier_pct = (len(outliers) / len(col_data) * 100) if len(col_data) > 0 else 0
                    
                    if outlier_pct > 5:
                        deduction_amount = min(outlier_pct / 20, 8)  # Max 8 point deduction
                        
                        deductions.append({
                            "deduction_reason": "potential_outliers",
                            "fields_affected": [col],
                            "deduction_amount": round(deduction_amount, 2),
                            "severity": "medium" if outlier_pct > 15 else "low",
                            "remediation": f"Review {outlier_pct:.1f}% of values as potential outliers. Validate or clean as needed"
                        })
        
        # Check for duplicate rows
        duplicate_count = len(df[df.duplicated()])
        duplicate_pct = (duplicate_count / len(df) * 100) if len(df) > 0 else 0
        
        if duplicate_pct > 0:
            deduction_amount = min(duplicate_pct / 10, 15)  # Max 15 point deduction
            
            deductions.append({
                "deduction_reason": "duplicate_rows",
                "fields_affected": [],
                "deduction_amount": round(deduction_amount, 2),
                "severity": "high" if duplicate_pct > 10 else "medium" if duplicate_pct > 5 else "low",
                "remediation": f"{duplicate_count} duplicate rows ({duplicate_pct:.1f}%) detected. Remove or consolidate duplicates"
            })
        
        # Component scores
        component_scores = [
            {
                "component": "completeness",
                "weight": completeness_weight,
                "score": round(completeness_score, 2),
                "status": "excellent" if completeness_score >= 95 else "good" if completeness_score >= 80 else "fair" if completeness_score >= 60 else "poor",
                "description": "Data has very few missing values" if completeness_score >= 95 else "Data has acceptable missing values" if completeness_score >= 80 else "Data has significant missing values"
            },
            {
                "component": "consistency",
                "weight": consistency_weight,
                "score": round(consistency_score, 2),
                "status": "excellent" if consistency_score >= 95 else "good" if consistency_score >= 80 else "fair" if consistency_score >= 60 else "poor",
                "description": "Data types are consistent" if consistency_score >= 90 else "Some data type inconsistencies detected"
            },
            {
                "component": "schema_health",
                "weight": schema_health_weight,
                "score": round(schema_health, 2),
                "status": "excellent" if schema_health >= 95 else "good" if schema_health >= 80 else "fair" if schema_health >= 60 else "poor",
                "description": "Schema is well-defined" if schema_health >= 90 else "Schema has minor issues"
            }
        ]
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # Overall readiness status alerts
        if status == "not_ready":
            alerts.append({
                "alert_id": "alert_readiness_001_not_ready",
                "severity": "critical",
                "category": "readiness_status",
                "message": f"Dataset NOT PRODUCTION-READY: {readiness_score:.1f}/100",
                "affected_fields_count": len(deductions),
                "recommendation": f"Critical issues detected. Use Clean My Data tool to improve quality before production use."
            })
        elif status == "needs_review":
            alerts.append({
                "alert_id": "alert_readiness_002_needs_review",
                "severity": "high",
                "category": "readiness_status",
                "message": f"Dataset NEEDS REVIEW: {readiness_score:.1f}/100 ({needs_review_threshold}-{ready_threshold} threshold)",
                "affected_fields_count": len(deductions),
                "recommendation": "Address identified issues before production deployment."
            })
        else:
            alerts.append({
                "alert_id": "alert_readiness_003_production_ready",
                "severity": "low",
                "category": "readiness_status",
                "message": f"Dataset PRODUCTION-READY: {readiness_score:.1f}/100",
                "affected_fields_count": 0,
                "recommendation": "Dataset meets quality standards. Proceed with analysis."
            })
        
        # Completeness alerts
        if completeness_score < 60:
            alerts.append({
                "alert_id": "alert_readiness_completeness_critical",
                "severity": "critical",
                "category": "data_completeness",
                "message": f"LOW COMPLETENESS SCORE: {completeness_score:.1f}/100 - Dataset has excessive missing data",
                "affected_fields_count": len([f for f in df.columns if (df[f].isna().sum() / len(df) * 100) > 10]),
                "recommendation": "Implement imputation strategy or remove incomplete records. Consider data source quality."
            })
        elif completeness_score < 80:
            alerts.append({
                "alert_id": "alert_readiness_completeness_high",
                "severity": "high",
                "category": "data_completeness",
                "message": f"MODERATE COMPLETENESS ISSUES: {completeness_score:.1f}/100 - Some columns have significant missing data",
                "affected_fields_count": len([f for f in df.columns if (df[f].isna().sum() / len(df) * 100) > 10]),
                "recommendation": "Investigate missing value patterns and apply targeted remediation."
            })
        
        # Consistency alerts
        if consistency_score < 70:
            alerts.append({
                "alert_id": "alert_readiness_consistency_critical",
                "severity": "high",
                "category": "data_consistency",
                "message": f"LOW CONSISTENCY SCORE: {consistency_score:.1f}/100 - Data types are inconsistent across fields",
                "affected_fields_count": consistency_issues,
                "recommendation": "Standardize data types and formats. Validate type casting rules."
            })
        
        # Schema health alerts
        if schema_health < 60:
            alerts.append({
                "alert_id": "alert_readiness_schema_critical",
                "severity": "critical",
                "category": "schema_health",
                "message": f"POOR SCHEMA HEALTH: {schema_health:.1f}/100 - Multiple schema issues detected",
                "affected_fields_count": null_columns + unnamed_columns + inconsistent_columns,
                "recommendation": f"Fix schema: rename {unnamed_columns} unnamed columns, remove {null_columns} empty columns, standardize {inconsistent_columns} mixed-type columns."
            })
        elif schema_health < 80:
            alerts.append({
                "alert_id": "alert_readiness_schema_high",
                "severity": "high",
                "category": "schema_health",
                "message": f"SCHEMA ISSUES: {schema_health:.1f}/100 - Some columns have naming or type problems",
                "affected_fields_count": null_columns + unnamed_columns,
                "recommendation": "Review and fix schema issues: unnamed columns, empty columns, or type inconsistencies."
            })
        
        # Duplicate rows alerts
        if duplicate_pct > 20:
            alerts.append({
                "alert_id": "alert_readiness_duplicates_critical",
                "severity": "critical",
                "category": "duplicate_records",
                "message": f"HIGH DUPLICATE VOLUME: {duplicate_count} rows ({duplicate_pct:.1f}%) are duplicates",
                "affected_fields_count": duplicate_count,
                "recommendation": "Investigate duplicate source. Remove or consolidate before analysis to prevent skewed results."
            })
        elif duplicate_pct > 5:
            alerts.append({
                "alert_id": "alert_readiness_duplicates_high",
                "severity": "high",
                "category": "duplicate_records",
                "message": f"DUPLICATE RECORDS DETECTED: {duplicate_count} rows ({duplicate_pct:.1f}%) are duplicates",
                "affected_fields_count": duplicate_count,
                "recommendation": "Remove duplicate rows to ensure data integrity and prevent bias in analysis."
            })
        
        # Insufficient sample size alert
        if len(df) < 100:
            alerts.append({
                "alert_id": "alert_readiness_sample_size",
                "severity": "medium",
                "category": "data_volume",
                "message": f"INSUFFICIENT SAMPLE SIZE: Only {len(df)} records (< 100 recommended)",
                "affected_fields_count": 0,
                "recommendation": "Gather more data. Statistical analysis and ML models perform better with larger datasets."
            })
        
        # Format inconsistency alerts
        format_issues = len([d for d in deductions if d.get('deduction_reason') == 'format_inconsistency'])
        if format_issues > 0:
            alerts.append({
                "alert_id": "alert_readiness_format_inconsistency",
                "severity": "medium",
                "category": "format_validation",
                "message": f"FORMAT INCONSISTENCIES: {format_issues} field(s) have inconsistent formats",
                "affected_fields_count": format_issues,
                "recommendation": "Standardize date, time, and other format-specific fields using consistent parsing rules."
            })
        
        # Outlier detection alert
        outlier_issues = len([d for d in deductions if d.get('deduction_reason') == 'potential_outliers'])
        if outlier_issues > 0:
            alerts.append({
                "alert_id": "alert_readiness_outliers",
                "severity": "medium",
                "category": "outlier_detection",
                "message": f"POTENTIAL OUTLIERS: {outlier_issues} field(s) contain outlier values",
                "affected_fields_count": outlier_issues,
                "recommendation": "Review and validate outlier values. Determine if they are errors or legitimate extreme values."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Add field-specific issues from deductions (limit to 100)
        issue_count = 0
        for deduction in deductions:
            if issue_count >= 100:
                break
            
            for field in deduction.get("fields_affected", []):
                if issue_count >= 100:
                    break
                
                issue_type = deduction.get('deduction_reason', 'unknown')
                severity = deduction.get('severity', 'medium')
                
                # Map deduction reason to issue_type taxonomy
                if issue_type == 'missing_values':
                    issue_type = 'null_value'
                elif issue_type == 'duplicate_rows':
                    issue_type = 'duplicate_record'
                elif issue_type == 'format_inconsistency':
                    issue_type = 'invalid_format'
                elif issue_type == 'potential_outliers':
                    issue_type = 'outlier_detected'
                
                issues.append({
                    "issue_id": f"issue_readiness_{len(issues)}_{field}",
                    "agent_id": "readiness-rater",
                    "field_name": field,
                    "issue_type": issue_type,
                    "severity": severity,
                    "message": deduction.get("remediation", f"Field '{field}' has {issue_type.replace('_', ' ')} issues")
                })
                issue_count += 1
        
        # Add schema-related issues
        if null_columns > 0:
            for col in df.columns:
                if issue_count >= 100:
                    break
                if df[col].isna().all():
                    issues.append({
                        "issue_id": f"issue_readiness_{len(issues)}_{col}_null",
                        "agent_id": "readiness-rater",
                        "field_name": col,
                        "issue_type": "missing_required_field",
                        "severity": "critical",
                        "message": f"Column '{col}' is completely empty (100% null) and should be removed"
                    })
                    issue_count += 1
        
        if unnamed_columns > 0:
            for col in df.columns:
                if issue_count >= 100:
                    break
                if str(col).startswith('Unnamed'):
                    issues.append({
                        "issue_id": f"issue_readiness_{len(issues)}_{col}",
                        "agent_id": "readiness-rater",
                        "field_name": col,
                        "issue_type": "invalid_format",
                        "severity": "high",
                        "message": f"Column '{col}' is unnamed or auto-generated. Provide meaningful column name for clarity."
                    })
                    issue_count += 1
        
        # Add consistency issues
        for col in df.columns:
            if issue_count >= 100:
                break
            col_lower = col.lower()
            if any(x in col_lower for x in ['date', 'time', 'created', 'updated', 'timestamp', 'datetime']):
                try:
                    pd.to_datetime(df[col].dropna())
                except:
                    unparseable_count = 0
                    for val in df[col].dropna():
                        try:
                            pd.to_datetime(val)
                        except:
                            unparseable_count += 1
                    
                    if unparseable_count > 0:
                        issues.append({
                            "issue_id": f"issue_readiness_{len(issues)}_{col}_format",
                            "agent_id": "readiness-rater",
                            "field_name": col,
                            "issue_type": "invalid_format",
                            "severity": "high" if unparseable_count > len(df[col].dropna()) * 0.25 else "medium",
                            "message": f"Column '{col}' has {unparseable_count} inconsistent date/time formats"
                        })
                        issue_count += 1
        
        # Add duplicate record issues (sample)
        if duplicate_count > 0 and issue_count < 100:
            dup_indices = df[df.duplicated(keep=False)].index[:min(10, len(df[df.duplicated(keep=False)]))]
            for idx in dup_indices:
                if issue_count >= 100:
                    break
                issues.append({
                    "issue_id": f"issue_readiness_{len(issues)}_row_{idx}",
                    "agent_id": "readiness-rater",
                    "field_name": "N/A",
                    "issue_type": "duplicate_record",
                    "severity": "high",
                    "message": f"Row {idx} is a duplicate of another record. Remove or consolidate before analysis."
                })
                issue_count += 1
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        recommendations = []
        
        # Overall readiness recommendation (critical priority)
        if status == "not_ready":
            recommendations.append({
                "recommendation_id": "rec_readiness_001_overall_critical",
                "agent_id": "readiness-rater",
                "field_name": "entire dataset",
                "priority": "critical",
                "recommendation": f"CRITICAL: Dataset is NOT PRODUCTION-READY (score: {readiness_score:.1f}/100). Use 'Clean My Data' tool to remediate issues. Address all critical and high-severity issues before proceeding to analysis or ML workflows.",
                "timeline": "immediate"
            })
        elif status == "needs_review":
            recommendations.append({
                "recommendation_id": "rec_readiness_002_review_required",
                "agent_id": "readiness-rater",
                "field_name": "entire dataset",
                "priority": "high",
                "recommendation": f"Dataset needs review (score: {readiness_score:.1f}/100). Prioritize addressing high-severity issues identified in alerts before production deployment. Estimated readiness impact: {100 - readiness_score:.1f} points of improvement possible.",
                "timeline": "1-2 weeks"
            })
        else:
            recommendations.append({
                "recommendation_id": "rec_readiness_003_production_ready",
                "agent_id": "readiness-rater",
                "field_name": "entire dataset",
                "priority": "low",
                "recommendation": f"Dataset is PRODUCTION-READY (score: {readiness_score:.1f}/100). Proceed with analysis and ML workflows. Continue monitoring data quality through regular profiling cycles.",
                "timeline": "1 month"
            })
        
        # Completeness-specific recommendation
        if completeness_score < 95:
            high_null_fields = [f for f in df.columns if (df[f].isna().sum() / len(df) * 100) > 10]
            field_count = len(high_null_fields)
            
            recommendations.append({
                "recommendation_id": "rec_readiness_completeness",
                "agent_id": "readiness-rater",
                "field_name": ", ".join(high_null_fields[:5]) if high_null_fields else "N/A",
                "priority": "critical" if completeness_score < 60 else "high" if completeness_score < 80 else "medium",
                "recommendation": f"Improve COMPLETENESS (current: {completeness_score:.1f}/100): {field_count} field(s) have >10% missing values. Implement missing value handling strategy: (1) Remove rows with critical nulls, (2) Impute using domain knowledge or statistical methods, or (3) Drop columns if >50% null.",
                "timeline": "immediate" if completeness_score < 60 else "1-2 weeks"
            })
        
        # Consistency-specific recommendation
        if consistency_score < 95:
            recommendations.append({
                "recommendation_id": "rec_readiness_consistency",
                "agent_id": "readiness-rater",
                "field_name": "data types",
                "priority": "high" if consistency_score < 70 else "medium",
                "recommendation": f"Improve DATA CONSISTENCY (current: {consistency_score:.1f}/100): Standardize data types and formats across fields. Use type validation rules, enforce schema constraints, and test type conversions before production. Ensure numeric fields contain only valid numbers, date fields follow ISO 8601 format, and categorical fields have defined allowed values.",
                "timeline": "1-2 weeks"
            })
        
        # Schema health-specific recommendation
        if schema_health < 95:
            recommendations.append({
                "recommendation_id": "rec_readiness_schema",
                "agent_name": "readiness-rater",
                "field_name": f"{unnamed_columns} unnamed + {null_columns} empty columns",
                "priority": "critical" if schema_health < 60 else "high" if schema_health < 80 else "medium",
                "recommendation": f"Improve SCHEMA HEALTH (current: {schema_health:.1f}/100): (1) Rename {unnamed_columns} auto-generated column name(s) to meaningful names; (2) Remove {null_columns} completely empty columns; (3) Fix {inconsistent_columns} column(s) with mixed data types by applying consistent parsing and validation rules.",
                "timeline": "1 week"
            })
        
        # Duplicate handling recommendation
        if duplicate_count > 0:
            recommendations.append({
                "recommendation_id": "rec_readiness_duplicates",
                "agent_id": "readiness-rater",
                "field_name": "N/A",
                "priority": "critical" if duplicate_pct > 20 else "high" if duplicate_pct > 5 else "medium",
                "recommendation": f"Remove/consolidate DUPLICATE RECORDS: {duplicate_count} rows ({duplicate_pct:.1f}%) are duplicates. Investigate source of duplicates (data loading, ETL errors, or legitimate records). Apply deduplication strategy: exact match removal, fuzzy matching, or business rule-based consolidation. This is critical as duplicates skew analysis and bias ML models.",
                "timeline": "1 week"
            })
        
        # Format standardization recommendation
        format_issues = len([d for d in deductions if d.get('deduction_reason') == 'format_inconsistency'])
        if format_issues > 0:
            recommendations.append({
                "recommendation_id": "rec_readiness_formats",
                "agent_id": "readiness-rater",
                "field_name": ", ".join([d.get('fields_affected', ['N/A'])[0] for d in deductions if d.get('deduction_reason') == 'format_inconsistency'][:3]),
                "priority": "high",
                "recommendation": f"Standardize FIELD FORMATS: {format_issues} field(s) have inconsistent formats. For date/time fields, enforce single format (e.g., YYYY-MM-DD HH:MM:SS). Use validation rules and data transformation pipelines to ensure all values conform to expected format before storing.",
                "timeline": "1 week"
            })
        
        # Outlier handling recommendation
        outlier_issues = len([d for d in deductions if d.get('deduction_reason') == 'potential_outliers'])
        if outlier_issues > 0:
            recommendations.append({
                "recommendation_id": "rec_readiness_outliers",
                "agent_id": "readiness-rater",
                "field_name": ", ".join([d.get('fields_affected', ['N/A'])[0] for d in deductions if d.get('deduction_reason') == 'potential_outliers'][:3]),
                "priority": "medium",
                "recommendation": f"Review and validate OUTLIERS: {outlier_issues} numeric field(s) contain potential outliers (beyond 1.5*IQR). Determine if outliers are errors or legitimate extreme values. Action: (1) Investigate root cause, (2) Fix errors if data quality issues, (3) Keep and flag if legitimate, or (4) Apply appropriate outlier treatment (capping, transformation, removal).",
                "timeline": "2-3 weeks"
            })
        
        # Sample size recommendation
        if len(df) < 100:
            recommendations.append({
                "recommendation_id": "rec_readiness_sample_size",
                "agent_id": "readiness-rater",
                "field_name": "entire dataset",
                "priority": "medium",
                "recommendation": f"Increase SAMPLE SIZE: Current dataset has only {len(df)} records. Recommended minimum is 100-1000 records depending on use case. Larger samples improve statistical reliability and ML model performance. Consider combining data sources or extending collection period to gather more data.",
                "timeline": "2-4 weeks"
            })
        
        # Top deductions as recommendations
        if status != "ready" and len(deductions) > 0:
            sorted_deductions = sorted(deductions, key=lambda x: x.get("deduction_amount", 0), reverse=True)[:2]
            
            for idx, deduction in enumerate(sorted_deductions):
                if idx >= 2:  # Limit to top 2
                    break
                
                deduction_reason = deduction.get('deduction_reason', '').replace('_', ' ').title()
                fields_affected = deduction.get('fields_affected', [])
                field_names = ", ".join(fields_affected[:3]) if fields_affected else "N/A"
                deduction_amount = deduction.get('deduction_amount', 0)
                
                recommendations.append({
                    "recommendation_id": f"rec_readiness_deduction_{idx}",
                    "agent_id": "readiness-rater",
                    "field_name": field_names,
                    "priority": "critical" if deduction.get("severity") in ["critical"] else "high" if deduction.get("severity") == "high" else "medium",
                    "recommendation": f"{deduction_reason} ({deduction_amount:.1f} point impact): {deduction.get('remediation', 'Remediation details available in data assessment')}",
                    "timeline": "1-2 weeks" if deduction.get("severity") in ["critical", "high"] else "2-3 weeks"
                })
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = []
        
        # Data Readiness Status
        executive_summary.append({
            "summary_id": "exec_readiness",
            "title": "Data Readiness Status",
            "value": str(round(readiness_score, 1)),
            "status": "ready" if status == "ready" else "needs_review" if status == "needs_review" else "not_ready",
            "description": f"{readiness_score:.1f}/100 - {'Production ready' if status == 'ready' else 'Needs improvement'}"
        })
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_text_parts = []
        ai_analysis_text_parts.append(f"DATA READINESS: {status.upper().replace('_', ' ')} ({readiness_score:.1f}/100)")
        ai_analysis_text_parts.append(f"- Completeness: {completeness_score:.1f}/100")
        ai_analysis_text_parts.append(f"- Consistency: {consistency_score:.1f}/100")
        ai_analysis_text_parts.append(f"- Schema Health: {schema_health:.1f}/100")
        
        if len(deductions) > 0:
            ai_analysis_text_parts.append(f"- {len(deductions)} issue(s) affecting readiness")
            
            # Top deductions
            top_deductions = sorted(deductions, key=lambda x: x.get("deduction_amount", 0), reverse=True)[:3]
            for deduction in top_deductions:
                ai_analysis_text_parts.append(f"  • {deduction.get('deduction_reason', '').replace('_', ' ').title()}: -{deduction.get('deduction_amount', 0):.1f} points")
        
        if status == "ready":
            ai_analysis_text_parts.append("- Dataset is production-ready for analysis")
        else:
            ai_analysis_text_parts.append(f"- {status_description}")
        
        ai_analysis_text = "\n".join(ai_analysis_text_parts)
        
        # ==================== GENERATE ROW-LEVEL-ISSUES ====================
        row_level_issues = []
        
        # Extract row-level issues from identified problems
        
        # 1. Add issues for rows with high null percentages
        for idx in df.index:
            row_null_count = df.loc[idx].isna().sum()
            row_null_pct = (row_null_count / len(df.columns) * 100) if len(df.columns) > 0 else 0
            
            if row_null_pct > 30:
                row_level_issues.append({
                    "row_index": int(idx),
                    "column": "global",
                    "issue_type": "readiness_low",
                    "severity": "critical" if row_null_pct > 50 else "warning",
                    "message": f"Row {idx} has {row_null_pct:.1f}% null values ({int(row_null_count)} of {len(df.columns)} columns) - exceeds 30% threshold",
                    "value": None,
                    "null_percentage": round(row_null_pct, 2)
                })
        
        # 2. Add issues for rows with outlier values
        for col in df.columns:
            if df[col].dtype in ['int64', 'float64']:
                col_data = df[col].dropna()
                if len(col_data) > 0:
                    Q1 = col_data.quantile(0.25)
                    Q3 = col_data.quantile(0.75)
                    IQR = Q3 - Q1
                    
                    if IQR > 0:
                        lower_bound = Q1 - 1.5 * IQR
                        upper_bound = Q3 + 1.5 * IQR
                        
                        outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
                        outlier_indices = df[outlier_mask].index.tolist()
                        
                        for idx in outlier_indices[:100]:
                            row_level_issues.append({
                                "row_index": int(idx),
                                "column": col,
                                "issue_type": "validation_failed",
                                "severity": "warning",
                                "message": f"Row {idx} has outlier value in '{col}': {df.loc[idx, col]}",
                                "value": float(df.loc[idx, col]),
                                "bounds": {
                                    "lower": float(lower_bound),
                                    "upper": float(upper_bound)
                                }
                            })
        
        # 3. Add issues for duplicate rows
        dup_mask = df.duplicated(keep=False)
        dup_indices = df[dup_mask].index.tolist()
        
        for idx in dup_indices[:100]:
            row_level_issues.append({
                "row_index": int(idx),
                "column": "global",
                "issue_type": "quality_gate_failed",
                "severity": "high",
                "message": f"Row {idx} is a duplicate record - affects data integrity and analysis results",
                "value": None
            })
        
        # 4. Add issues for rows with format inconsistencies
        date_patterns = ['date', 'time', 'created', 'updated', 'timestamp', 'datetime']
        for col in df.columns:
            col_lower = col.lower()
            if any(x in col_lower for x in date_patterns):
                for idx in df.index:
                    try:
                        pd.to_datetime(df.loc[idx, col])
                    except:
                        if pd.notna(df.loc[idx, col]):
                            row_level_issues.append({
                                "row_index": int(idx),
                                "column": col,
                                "issue_type": "validation_failed",
                                "severity": "warning",
                                "message": f"Row {idx} has invalid date/time format in '{col}': {df.loc[idx, col]}",
                                "value": str(df.loc[idx, col])
                            })
                            
                            if len(row_level_issues) >= 1000:
                                break
            
            if len(row_level_issues) >= 1000:
                break
        
        # 5. Add issues for rows with type mismatches in numeric columns
        for col in df.columns:
            if df[col].dtype == 'object':
                for idx in df.index:
                    val = df.loc[idx, col]
                    if pd.notna(val):
                        try:
                            float(val)
                        except (ValueError, TypeError):
                            # Check if this is supposed to be numeric based on column name
                            col_lower = col.lower()
                            if any(x in col_lower for x in ['price', 'amount', 'quantity', 'count', 'value', 'rate', 'score', 'id']):
                                row_level_issues.append({
                                    "row_index": int(idx),
                                    "column": col,
                                    "issue_type": "validation_failed",
                                    "severity": "medium",
                                    "message": f"Row {idx} has non-numeric value in numeric column '{col}': {val}",
                                    "value": str(val)
                                })
                                
                                if len(row_level_issues) >= 1000:
                                    break
            
            if len(row_level_issues) >= 1000:
                break
        
        # Cap at 1000 issues
        row_level_issues = row_level_issues[:1000]
        
        # Calculate row-level-issues summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {
                "critical": 0,
                "warning": 0,
                "info": 0
            },
            "affected_rows": len(set(issue["row_index"] for issue in row_level_issues)),
            "affected_columns": list(set(issue["column"] for issue in row_level_issues))
        }
        
        for issue in row_level_issues:
            issue_type = issue.get("issue_type", "validation_failed")
            severity = issue.get("severity", "info")
            
            if issue_type not in issue_summary["by_type"]:
                issue_summary["by_type"][issue_type] = 0
            issue_summary["by_type"][issue_type] += 1
            
            if severity in issue_summary["by_severity"]:
                issue_summary["by_severity"][severity] += 1
        
        return {
            "status": "success",
            "agent_id": "readiness-rater",
            "agent_name": "ReadinessRater",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "readiness_score": round(readiness_score, 2),
                "readiness_status": status,
                "components_ready": len([c for c in component_scores if c["score"] >= 80]),
                "components_needs_review": len([c for c in component_scores if 60 <= c["score"] < 80]),
                "components_not_ready": len([c for c in component_scores if c["score"] < 60])
            },
            "data": {
                "readiness_assessment": {
                    "overall_score": round(readiness_score, 2),
                    "overall_status": status,
                    "status_description": status_description,
                    "recommendation": recommendation
                },
                "component_scores": component_scores,
                "deductions": deductions
            },
            "alerts": alerts,
            "issues": issues,
            "recommendations": recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }
