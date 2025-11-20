"""
Unified Profiler Agent

Comprehensive data profiling with statistics and quality metrics.
Input: CSV/JSON/XLSX file (primary)
Output: Uniform profiling structure with field-level analysis matching API specification
"""

import pandas as pd
import numpy as np
import io
import time
from typing import Dict, Any, Optional
from scipy import stats


def profile_data(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Profile data with comprehensive statistics.
    
    Args:
        file_contents: File bytes
        filename: Original filename
        parameters: Agent parameters from tool.json (null_alert_threshold, categorical_threshold, etc.)
        
    Returns:
        Uniform output structure matching API_SPECIFICATION.js response format
    """
    
    start_time = time.time()
    parameters = parameters or {}
    
    # Get parameters with defaults (matching tool.json)
    null_alert_threshold = parameters.get("null_alert_threshold", 50)
    categorical_threshold = parameters.get("categorical_threshold", 20)
    categorical_ratio_threshold = parameters.get("categorical_ratio_threshold", 0.05)
    top_n_values = parameters.get("top_n_values", 10)
    outlier_iqr_multiplier = parameters.get("outlier_iqr_multiplier", 1.5)
    outlier_alert_threshold = parameters.get("outlier_alert_threshold", 5)
    
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
        
        # Profile each field
        field_profiles = []
        critical_issues = 0
        warnings = 0
        info_messages = 0
        
        for col in df.columns:
            col_data = df[col]
            missing_count = col_data.isna().sum()
            missing_pct = (missing_count / len(df) * 100) if len(df) > 0 else 0
            
            # Determine data type
            data_type = str(col_data.dtype)
            if data_type == 'object':
                semantic_type = 'string'
            elif data_type in ['int64', 'int32', 'int16', 'int8']:
                semantic_type = 'integer'
            elif data_type in ['float64', 'float32']:
                semantic_type = 'float'
            else:
                semantic_type = data_type
            
            # Check for PII/sensitivity
            estimated_pii_type = None
            estimated_sensitivity_level = "low"
            
            col_lower = col.lower()
            non_null_sample = col_data.dropna().astype(str).head(100)
            
            # Email detection - check for @ symbol pattern
            if col_lower in ['email', 'email_address', 'email_addr', 'contact_email']:
                if len(non_null_sample) > 0:
                    email_matches = non_null_sample.str.contains('@', regex=False).sum()
                    email_pct = (email_matches / len(non_null_sample) * 100) if len(non_null_sample) > 0 else 0
                    
                    if email_pct > 70:
                        estimated_pii_type = "email_address"
                        estimated_sensitivity_level = "high"
            
            # Phone detection - check for common phone patterns
            elif col_lower in ['phone', 'phone_number', 'contact_phone', 'mobile', 'telephone']:
                if len(non_null_sample) > 0:
                    phone_matches = non_null_sample.str.match(r'^[\d\s\-\(\)\+]{10,}$').sum()
                    phone_pct = (phone_matches / len(non_null_sample) * 100) if len(non_null_sample) > 0 else 0
                    
                    if phone_pct > 70:
                        estimated_pii_type = "phone_number"
                        estimated_sensitivity_level = "high"
            
            # SSN detection
            elif col_lower in ['ssn', 'social_security', 'social_security_number']:
                if len(non_null_sample) > 0:
                    ssn_matches = non_null_sample.str.match(r'^\d{3}-\d{2}-\d{4}$').sum()
                    ssn_pct = (ssn_matches / len(non_null_sample) * 100) if len(non_null_sample) > 0 else 0
                    
                    if ssn_pct > 70:
                        estimated_pii_type = "ssn"
                        estimated_sensitivity_level = "high"
            
            # Name detection - check if mostly text with capital letters
            elif col_lower in ['name', 'full_name', 'first_name', 'last_name', 'person_name', 'customer_name']:
                if len(non_null_sample) > 0:
                    # Check if values look like names (contain spaces or capital letters)
                    name_like = 0
                    for val in non_null_sample:
                        # Simple heuristic: contains letters and spaces, or starts with capital letter
                        if any(c.isupper() for c in val) and any(c.isalpha() for c in val):
                            name_like += 1
                    
                    name_pct = (name_like / len(non_null_sample) * 100) if len(non_null_sample) > 0 else 0
                    
                    if name_pct > 80:
                        estimated_pii_type = "name"
                        estimated_sensitivity_level = "high"
            
            # Credit card detection
            elif col_lower in ['credit_card', 'card_number', 'cc_number', 'payment_card']:
                if len(non_null_sample) > 0:
                    cc_matches = non_null_sample.str.match(r'^\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}$').sum()
                    cc_pct = (cc_matches / len(non_null_sample) * 100) if len(non_null_sample) > 0 else 0
                    
                    if cc_pct > 70:
                        estimated_pii_type = "credit_card"
                        estimated_sensitivity_level = "critical"
            
            # Calculate quality indicators
            completeness_score = 100 - missing_pct
            unique_count = col_data.nunique()
            unique_percentage = (unique_count / len(col_data) * 100) if len(col_data) > 0 else 0
            
            # Validity score (basic)
            validity_score = 100.0
            if data_type in ['int64', 'float64']:
                # Check for outliers
                Q1 = col_data.quantile(0.25)
                Q3 = col_data.quantile(0.75)
                IQR = Q3 - Q1
                outliers = col_data[(col_data < (Q1 - outlier_iqr_multiplier * IQR)) | 
                                   (col_data > (Q3 + outlier_iqr_multiplier * IQR))]
                outlier_pct = (len(outliers) / len(col_data) * 100) if len(col_data) > 0 else 0
                validity_score = 100 - min(outlier_pct, 20)
            
            # Consistency score
            consistency_score = 100.0 if unique_count > 1 else 50.0
            
            # Overall quality score
            quality_score = (completeness_score + validity_score + consistency_score) / 3
            
            # Build field profile
            field_profile = {
                "field_id": col,
                "field_name": col,
                "data_type": semantic_type,
                "semantic_type": semantic_type,
                "properties": {
                    "null_count": int(missing_count),
                    "null_percentage": round(missing_pct, 2),
                    "unique_count": int(unique_count),
                    "unique_percentage": round(unique_percentage, 2),
                    "is_primary_key": False,
                    "is_foreign_key": False,
                    "estimated_pii_type": estimated_pii_type,
                    "estimated_sensitivity_level": estimated_sensitivity_level
                },
                "quality_score": round(quality_score, 2),
                "quality_indicators": {
                    "completeness_score": round(completeness_score, 2),
                    "uniqueness_score": round((unique_percentage) / 100 * 100, 2),
                    "validity_score": round(validity_score, 2),
                    "consistency_score": round(consistency_score, 2)
                }
            }
            
            # Add statistics for numeric fields
            if data_type in ['int64', 'float64']:
                non_null_data = col_data.dropna()
                if len(non_null_data) > 0:
                    field_profile["statistics"] = {
                        "type": "numeric",
                        "count": len(non_null_data),
                        "min": float(non_null_data.min()),
                        "max": float(non_null_data.max()),
                        "mean": float(non_null_data.mean()),
                        "median": float(non_null_data.median()),
                        "stddev": float(non_null_data.std()),
                        "variance": float(non_null_data.var()),
                        "p25": float(non_null_data.quantile(0.25)),
                        "p50": float(non_null_data.quantile(0.50)),
                        "p75": float(non_null_data.quantile(0.75)),
                        "skewness": float(non_null_data.skew()),
                        "kurtosis": float(non_null_data.kurtosis()),
                        "outlier_count": int(len(col_data[(col_data < (col_data.quantile(0.25) - outlier_iqr_multiplier * (col_data.quantile(0.75) - col_data.quantile(0.25)))) | (col_data > (col_data.quantile(0.75) + outlier_iqr_multiplier * (col_data.quantile(0.75) - col_data.quantile(0.25))))])),
                        "outlier_percentage": round((len(col_data[(col_data < (col_data.quantile(0.25) - outlier_iqr_multiplier * (col_data.quantile(0.75) - col_data.quantile(0.25)))) | (col_data > (col_data.quantile(0.75) + outlier_iqr_multiplier * (col_data.quantile(0.75) - col_data.quantile(0.25))))]) / len(col_data) * 100), 2) if len(col_data) > 0 else 0,
                        "entropy": float(stats.entropy(col_data.value_counts()) if len(col_data.value_counts()) > 0 else 0)
                    }
            else:
                # String statistics
                non_null_data = col_data.dropna().astype(str)
                if len(non_null_data) > 0:
                    field_profile["statistics"] = {
                        "type": "string",
                        "min_length": int(non_null_data.str.len().min()),
                        "max_length": int(non_null_data.str.len().max()),
                        "avg_length": round(non_null_data.str.len().mean(), 2),
                        "entropy": round(float(stats.entropy(col_data.value_counts()) if len(col_data.value_counts()) > 0 else 0), 2),
                        "charset_diversity": ["alphanumeric", "special"] if any(col_data.astype(str).str.contains(r'[!@#$%^&*()_+=\[\]{};:\'",.<>?/\\|`~-]', regex=True, na=False)) else ["alphanumeric"]
                    }
            
            # Add distribution (top values)
            top_values = col_data.value_counts().head(top_n_values)
            field_profile["distribution"] = {
                "type": "non_uniform" if len(top_values) > 1 else "uniform",
                "top_values": [
                    {"value": str(k), "count": int(v), "percentage": round((v / len(col_data) * 100), 2)}
                    for k, v in top_values.items()
                ]
            }
            
            field_profiles.append(field_profile)
            
            # Track issues
            if missing_pct > null_alert_threshold:
                critical_issues += 1
            elif missing_pct > 10:
                warnings += 1
            else:
                info_messages += 1
        
        # Calculate overall quality score
        overall_quality_score = round(np.mean([f["quality_score"] for f in field_profiles]), 2) if field_profiles else 100
        
        # ==================== GENERATE ROW-LEVEL-ISSUES ====================
        row_level_issues = []
        
        for col_idx, col in enumerate(df.columns):
            col_data = df[col]
            non_null_data = col_data.dropna()
            data_type = str(col_data.dtype)
            
            # Issue 1: Null values
            null_mask = col_data.isna()
            for row_idx in df[null_mask].index:
                row_level_issues.append({
                    "row_index": int(row_idx),
                    "column": col,
                    "issue_type": "null",
                    "severity": "warning",
                    "message": f"Null/missing value in column '{col}'",
                    "value": None
                })
            
            # Issue 2: Outliers (numeric fields only)
            if data_type in ['int64', 'float64'] and len(non_null_data) > 0:
                Q1 = col_data.quantile(0.25)
                Q3 = col_data.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - outlier_iqr_multiplier * IQR
                upper_bound = Q3 + outlier_iqr_multiplier * IQR
                
                outlier_mask = (col_data < lower_bound) | (col_data > upper_bound)
                for row_idx in df[outlier_mask].index:
                    row_value = col_data.loc[row_idx]
                    row_level_issues.append({
                        "row_index": int(row_idx),
                        "column": col,
                        "issue_type": "outlier",
                        "severity": "warning",
                        "message": f"Outlier detected in '{col}': value {row_value} outside IQR bounds [{lower_bound:.2f}, {upper_bound:.2f}]",
                        "value": float(row_value),
                        "bounds": {
                            "lower": float(lower_bound),
                            "upper": float(upper_bound)
                        }
                    })
            
            # Issue 3: Type mismatches (check if non-null values don't match expected type)
            if data_type == 'object' and len(non_null_data) > 0:
                # Try to detect numeric values in string columns (or vice versa)
                try:
                    numeric_attempt = pd.to_numeric(non_null_data, errors='coerce')
                    type_mismatch_mask = numeric_attempt.notna() & non_null_data.notna() & (numeric_attempt != non_null_data)
                    
                    for row_idx in df[type_mismatch_mask].index:
                        if not pd.isna(col_data.loc[row_idx]):
                            row_level_issues.append({
                                "row_index": int(row_idx),
                                "column": col,
                                "issue_type": "type_mismatch",
                                "severity": "info",
                                "message": f"Value in '{col}' could be interpreted as numeric: {col_data.loc[row_idx]}",
                                "value": str(col_data.loc[row_idx])
                            })
                except:
                    pass
            
            # Issue 4: Distribution anomalies (values in low-probability areas)
            if data_type in ['int64', 'float64'] and len(non_null_data) > 2:
                # Calculate z-scores to identify values far from mean
                mean_val = non_null_data.mean()
                std_val = non_null_data.std()
                
                if std_val > 0:
                    z_scores = np.abs((col_data - mean_val) / std_val)
                    extreme_mask = (z_scores > 3) & (col_data.notna())
                    
                    for row_idx in df[extreme_mask].index:
                        row_value = col_data.loc[row_idx]
                        z_score = (row_value - mean_val) / std_val
                        row_level_issues.append({
                            "row_index": int(row_idx),
                            "column": col,
                            "issue_type": "distribution_anomaly",
                            "severity": "info",
                            "message": f"Value in '{col}' is statistically unusual (z-score: {abs(z_score):.2f}): {row_value}",
                            "value": float(row_value),
                            "z_score": float(z_score)
                        })
        
        # Cap row-level-issues at 1000 to avoid memory issues
        row_level_issues = row_level_issues[:1000]
        
        # Calculate issue summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {},
            "affected_rows": len(set(issue["row_index"] for issue in row_level_issues)),
            "affected_columns": sorted(list(set(issue["column"] for issue in row_level_issues)))
        }
        
        # Count by type
        for issue in row_level_issues:
            issue_type = issue["issue_type"]
            issue_summary["by_type"][issue_type] = issue_summary["by_type"].get(issue_type, 0) + 1
        
        # Count by severity
        for issue in row_level_issues:
            severity = issue["severity"]
            issue_summary["by_severity"][severity] = issue_summary["by_severity"].get(severity, 0) + 1
        
        # Create quality summary
        quality_summary = {
            "overall_quality_score": overall_quality_score,
            "quality_grade": "A" if overall_quality_score >= 90 else "B" if overall_quality_score >= 80 else "C" if overall_quality_score >= 70 else "D" if overall_quality_score >= 60 else "F",
            "completeness_score": round(np.mean([f["quality_indicators"]["completeness_score"] for f in field_profiles]), 2),
            "validity_score": round(np.mean([f["quality_indicators"]["validity_score"] for f in field_profiles]), 2),
            "consistency_score": round(np.mean([f["quality_indicators"]["consistency_score"] for f in field_profiles]), 2),
            "accuracy_score": round(np.mean([f["quality_indicators"]["validity_score"] for f in field_profiles]), 2),
            "fields_requiring_attention": len([f for f in field_profiles if f["quality_score"] < 80]),
            "critical_issues": critical_issues,
            "warnings": warnings,
            "info_messages": info_messages
        }
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        quality_grade = quality_summary["quality_grade"]
        fields_with_issues = len([f for f in field_profiles if f["quality_score"] < 80])
        
        # Alert 1: Overall data quality status
        if overall_quality_score < 80:
            alerts.append({
                "alert_id": "alert_profile_quality_overall",
                "severity": "critical" if overall_quality_score < 50 else "high" if overall_quality_score < 60 else "medium",
                "category": "data_quality",
                "message": f"Data quality score is {overall_quality_score:.1f}/100 (Grade {quality_grade}). {fields_with_issues} field(s) need improvement.",
                "affected_fields_count": fields_with_issues,
                "recommendation": f"Comprehensive data quality remediation required. {fields_with_issues} field(s) with quality < 80. Priority: improve completeness, consistency, and validity."
            })
        elif overall_quality_score >= 90:
            alerts.append({
                "alert_id": "alert_profile_quality_excellent",
                "severity": "low",
                "category": "data_quality",
                "message": f"Data quality EXCELLENT: {overall_quality_score:.1f}/100 (Grade {quality_grade})",
                "affected_fields_count": 0,
                "recommendation": "Maintain current data quality standards and validation practices"
            })
        
        # Alert 2: High null/missing data percentage
        fields_with_high_nulls = [f for f in field_profiles if f.get("properties", {}).get("null_percentage", 0) > 50]
        if fields_with_high_nulls:
            avg_null_pct = np.mean([f.get("properties", {}).get("null_percentage", 0) for f in fields_with_high_nulls])
            alerts.append({
                "alert_id": "alert_profile_high_nulls",
                "severity": "critical" if avg_null_pct > 75 else "high",
                "category": "missing_data",
                "message": f"High null/missing data: {len(fields_with_high_nulls)} field(s) with >{50}% missing values (avg: {avg_null_pct:.1f}%)",
                "affected_fields_count": len(fields_with_high_nulls),
                "recommendation": f"Address {len(fields_with_high_nulls)} field(s) with excessive missing values through imputation, validation, or column removal"
            })
        
        # Alert 3: Unexpected distribution shape anomalies
        distribution_anomalies = [f for f in field_profiles if f.get("properties", {}).get("distribution_shape", "") in ["bimodal", "skewed", "highly_skewed"]]
        if distribution_anomalies:
            alerts.append({
                "alert_id": "alert_profile_distribution_anomalies",
                "severity": "high",
                "category": "data_distribution",
                "message": f"Unexpected distribution patterns: {len(distribution_anomalies)} field(s) show bimodal/skewed distributions",
                "affected_fields_count": len(distribution_anomalies),
                "recommendation": "Investigate distribution anomalies - may indicate data collection issues, multiple populations, or outlier influence"
            })
        
        # Alert 4: Type/semantic conflicts detected
        type_conflicts = len([f for f in field_profiles if "type_conflict" in str(f.get("properties", {})).lower()])
        if type_conflicts > 0 or any(f.get("properties", {}).get("type_mismatch", False) for f in field_profiles):
            alerts.append({
                "alert_id": "alert_profile_type_conflicts",
                "severity": "high",
                "category": "data_integrity",
                "message": f"Type/semantic conflicts detected: Values don't match declared field types in {type_conflicts or 1}+ field(s)",
                "affected_fields_count": type_conflicts or 1,
                "recommendation": "Review field type definitions and actual data values. Use 'Type Fixer' agent to resolve type mismatches"
            })
        
        # Alert 5: PII/Sensitive data detected
        pii_fields = [f for f in field_profiles if f.get("properties", {}).get("pii_type") or f.get("properties", {}).get("sensitivity_level") in ["high", "critical"]]
        if pii_fields:
            pii_types = set()
            critical_pii = 0
            for f in pii_fields:
                if f.get("properties", {}).get("pii_type"):
                    pii_types.add(f.get("properties", {}).get("pii_type"))
                if f.get("properties", {}).get("sensitivity_level") == "critical":
                    critical_pii += 1
            
            alerts.append({
                "alert_id": "alert_profile_pii_detected",
                "severity": "critical" if critical_pii > 0 else "high",
                "category": "pii_detected",
                "message": f"PII/Sensitive data detected: {len(pii_fields)} field(s) contain {', '.join(pii_types)}",
                "affected_fields_count": len(pii_fields),
                "recommendation": f"Implement data protection measures: encryption, access controls, audit logging. {critical_pii} field(s) require immediate attention"
            })
        
        # Alert 6: Cardinality concerns (high/low uniqueness)
        low_cardinality = [f for f in field_profiles if f.get("properties", {}).get("unique_percentage", 100) < 5]
        high_cardinality = [f for f in field_profiles if f.get("properties", {}).get("unique_percentage", 0) > 95 and f.get("properties", {}).get("null_percentage", 0) < 10]
        
        if low_cardinality:
            alerts.append({
                "alert_id": "alert_profile_low_cardinality",
                "severity": "medium",
                "category": "column_quality",
                "message": f"Low cardinality (potential duplicates): {len(low_cardinality)} field(s) with <5% unique values",
                "affected_fields_count": len(low_cardinality),
                "recommendation": "Verify low-cardinality fields are intentional (e.g., status flags). Consider consolidation or encoding"
            })
        
        if high_cardinality:
            alerts.append({
                "alert_id": "alert_profile_high_cardinality",
                "severity": "medium",
                "category": "column_quality",
                "message": f"High cardinality: {len(high_cardinality)} field(s) with >95% unique values (potential ID fields)",
                "affected_fields_count": len(high_cardinality),
                "recommendation": "High-cardinality fields detected - typically IDs or keys. Verify completeness and uniqueness constraints"
            })
        
        # Alert 7: Outlier detection summary
        fields_with_outliers = [f for f in field_profiles if f.get("statistics", {}).get("outlier_percentage", 0) > 5]
        if fields_with_outliers:
            avg_outlier_pct = np.mean([f.get("statistics", {}).get("outlier_percentage", 0) for f in fields_with_outliers])
            alerts.append({
                "alert_id": "alert_profile_outliers_detected",
                "severity": "high" if avg_outlier_pct > 10 else "medium",
                "category": "data_quality",
                "message": f"Outliers detected: {len(fields_with_outliers)} numeric field(s) with >{5}% outliers (avg: {avg_outlier_pct:.1f}%)",
                "affected_fields_count": len(fields_with_outliers),
                "recommendation": "Review outlier values - may be valid extremes or data errors. Use 'Outlier Remover' for remediation"
            })
        
        # Alert 8: Field completeness analysis
        avg_completeness = quality_summary.get("completeness_score", 100)
        if avg_completeness < 80:
            alerts.append({
                "alert_id": "alert_profile_completeness_gap",
                "severity": "high" if avg_completeness < 60 else "medium",
                "category": "missing_data",
                "message": f"Low data completeness: Average {avg_completeness:.1f}/100. Multiple fields have missing values",
                "affected_fields_count": len([f for f in field_profiles if f.get("properties", {}).get("null_percentage", 0) > 0]),
                "recommendation": "Implement missing data handling strategy: imputation, interpolation, or validation rule enforcement"
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Add field-level quality issues with comprehensive categorization
        for idx, field in enumerate(field_profiles[:100]):  # Limit to 100 issues
            field_quality = field.get("quality_score", 0)
            field_name = field.get("field_name")
            field_id = field.get("field_id")
            properties = field.get("properties", {})
            
            # Primary quality score issue
            if field_quality < 80:
                issues.append({
                    "issue_id": f"issue_profile_quality_{field_id}",
                    "agent_id": "unified-profiler",
                    "field_name": field_name,
                    "issue_type": "low_quality_score",
                    "severity": "critical" if field_quality < 50 else "high" if field_quality < 60 else "medium",
                    "message": f"Field quality score: {field_quality:.1f}/100. Requires attention for data validation and cleaning.",
                    "quality_score": field_quality,
                    "remediation_priority": "immediate" if field_quality < 50 else "high"
                })
            
            # Null/Missing value issues
            missing_pct = properties.get("null_percentage", 0)
            if missing_pct > 10:
                issues.append({
                    "issue_id": f"issue_profile_nulls_{field_id}",
                    "agent_id": "unified-profiler",
                    "field_name": field_name,
                    "issue_type": "high_null_percentage",
                    "severity": "critical" if missing_pct > 75 else "high" if missing_pct > 50 else "medium",
                    "message": f"{missing_pct:.1f}% missing/null values in '{field_name}'. Data completeness impacted.",
                    "null_percentage": missing_pct,
                    "remediation_priority": "immediate" if missing_pct > 50 else "high"
                })
            
            # Outlier issues (for numeric fields)
            if field.get("statistics", {}).get("type") == "numeric":
                outlier_count = field.get("statistics", {}).get("outlier_count", 0)
                outlier_pct = field.get("statistics", {}).get("outlier_percentage", 0)
                
                if outlier_pct > 5:
                    issues.append({
                        "issue_id": f"issue_profile_outliers_{field_id}",
                        "agent_id": "unified-profiler",
                        "field_name": field_name,
                        "issue_type": "high_outlier_percentage",
                        "severity": "high" if outlier_pct > 10 else "medium",
                        "message": f"{outlier_count} outliers detected ({outlier_pct:.1f}% of {field_name} values)",
                        "outlier_count": outlier_count,
                        "outlier_percentage": outlier_pct
                    })
            
            # Cardinality issues
            unique_pct = properties.get("unique_percentage", 100)
            
            # Low cardinality (potential duplicates/consolidation candidates)
            if unique_pct < 5:
                issues.append({
                    "issue_id": f"issue_profile_low_cardinality_{field_id}",
                    "agent_id": "unified-profiler",
                    "field_name": field_name,
                    "issue_type": "low_cardinality",
                    "severity": "medium",
                    "message": f"Very low cardinality: Only {unique_pct:.1f}% unique values (potential flag/status field or duplicates)",
                    "unique_percentage": unique_pct
                })
            
            # High cardinality (potential ID/key field)
            elif unique_pct > 95 and missing_pct < 10:
                issues.append({
                    "issue_id": f"issue_profile_high_cardinality_{field_id}",
                    "agent_id": "unified-profiler",
                    "field_name": field_name,
                    "issue_type": "high_cardinality",
                    "severity": "low",
                    "message": f"High cardinality field: {unique_pct:.1f}% unique values (likely identifier/key field)",
                    "unique_percentage": unique_pct
                })
            
            # Type mismatch issues
            if properties.get("type_mismatch", False) or "type_conflict" in str(properties).lower():
                issues.append({
                    "issue_id": f"issue_profile_type_conflict_{field_id}",
                    "agent_id": "unified-profiler",
                    "field_name": field_name,
                    "issue_type": "type_mismatch",
                    "severity": "high",
                    "message": f"Type conflict: Values in '{field_name}' don't match declared data type",
                    "declared_type": properties.get("data_type", "unknown"),
                    "actual_type": field.get("statistics", {}).get("inferred_type", "mixed")
                })
            
            # Distribution anomalies
            distribution_shape = properties.get("distribution_shape", "")
            if distribution_shape in ["bimodal", "highly_skewed", "multimodal"]:
                issues.append({
                    "issue_id": f"issue_profile_distribution_{field_id}",
                    "agent_id": "unified-profiler",
                    "field_name": field_name,
                    "issue_type": "unexpected_distribution",
                    "severity": "medium",
                    "message": f"Unusual distribution shape in '{field_name}': {distribution_shape} (may indicate multiple populations or data collection issues)",
                    "distribution_shape": distribution_shape
                })
            
            # PII/Sensitivity issues
            pii_type = properties.get("pii_type")
            sensitivity = properties.get("sensitivity_level", "low")
            
            if pii_type or sensitivity in ["high", "critical"]:
                issues.append({
                    "issue_id": f"issue_profile_pii_{field_id}",
                    "agent_id": "unified-profiler",
                    "field_name": field_name,
                    "issue_type": f"pii_{pii_type}" if pii_type else "sensitive_data",
                    "severity": "critical" if sensitivity == "critical" else "high",
                    "message": f"Sensitive data detected in '{field_name}': {pii_type or 'sensitive'}. Implement encryption and access controls.",
                    "pii_type": pii_type,
                    "sensitivity_level": sensitivity
                })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        recommendations = []
        
        # Recommendation 1: Critical - Address high null percentage fields
        fields_with_critical_nulls = [f for f in field_profiles if f.get("properties", {}).get("null_percentage", 0) > 75]
        if fields_with_critical_nulls:
            field_names = [f.get("field_name") for f in fields_with_critical_nulls[:3]]
            recommendations.append({
                "recommendation_id": "rec_profile_critical_nulls",
                "agent_id": "unified-profiler",
                "field_name": ", ".join(field_names),
                "priority": "critical",
                "recommendation": f"CRITICAL: Address {len(fields_with_critical_nulls)} field(s) with >75% missing values. Options: 1) Drop columns if not needed, 2) Implement imputation strategy, 3) Investigate data collection gaps",
                "timeline": "immediate",
                "estimated_effort_hours": 8,
                "owner": "Data Quality Team"
            })
        
        # Recommendation 2: High - Data quality improvement strategy
        low_quality_fields = sorted([f for f in field_profiles if f.get("quality_score", 0) < 80], 
                                   key=lambda x: x.get("quality_score", 0))[:5]
        
        if low_quality_fields:
            recommendations.append({
                "recommendation_id": "rec_profile_quality_improvement",
                "agent_id": "unified-profiler",
                "field_name": f"{len([f for f in field_profiles if f.get('quality_score', 0) < 80])} fields",
                "priority": "high" if overall_quality_score < 70 else "medium",
                "recommendation": f"Implement comprehensive quality improvement plan: 1) Profile results show {overall_quality_score:.1f}/100 quality score, 2) Focus on top 5 low-quality fields, 3) Run 'Clean My Data' tool for automated fixes, 4) Implement validation rules for ongoing data quality",
                "timeline": "1-2 weeks",
                "estimated_effort_hours": 12,
                "owner": "Data Governance Team"
            })
        
        # Recommendation 3: High - Distribution analysis for anomalies
        anomaly_fields = [f for f in field_profiles if f.get("properties", {}).get("distribution_shape", "") in ["bimodal", "highly_skewed", "multimodal"]]
        if anomaly_fields:
            recommendations.append({
                "recommendation_id": "rec_profile_distribution_analysis",
                "agent_id": "unified-profiler",
                "field_name": f"{len(anomaly_fields)} field(s)",
                "priority": "high",
                "recommendation": f"Investigate {len(anomaly_fields)} field(s) with unusual distributions (bimodal/skewed): 1) Analyze for data collection issues, 2) Check for multiple populations or segments, 3) Identify and handle outlier influence, 4) Consider data stratification or transformation",
                "timeline": "1 week",
                "estimated_effort_hours": 6,
                "owner": "Data Analysis Team"
            })
        
        # Recommendation 4: High - Type verification and fixing
        type_conflict_fields = [f for f in field_profiles if f.get("properties", {}).get("type_mismatch", False)]
        if type_conflict_fields:
            recommendations.append({
                "recommendation_id": "rec_profile_type_resolution",
                "agent_id": "unified-profiler",
                "field_name": f"{len(type_conflict_fields)} field(s)",
                "priority": "high",
                "recommendation": f"Fix {len(type_conflict_fields)} type mismatch(es): 1) Verify declared field types match actual data, 2) Run 'Type Fixer' agent to resolve conversions, 3) Update schema if needed, 4) Add type validation rules to prevent future mismatches",
                "timeline": "1 week",
                "estimated_effort_hours": 8,
                "owner": "Data Engineering Team"
            })
        
        # Recommendation 5: High/Medium - Outlier handling strategy
        if fields_with_outliers:
            recommendations.append({
                "recommendation_id": "rec_profile_outlier_handling",
                "agent_id": "unified-profiler",
                "field_name": f"{len(fields_with_outliers)} field(s)",
                "priority": "high" if len(fields_with_outliers) > 5 else "medium",
                "recommendation": f"Develop outlier handling strategy for {len(fields_with_outliers)} numeric field(s): 1) Validate outliers are not data errors, 2) Run 'Outlier Remover' with IQR or Z-score method, 3) Document outlier decisions, 4) Consider domain expertise for business outliers",
                "timeline": "1-2 weeks",
                "estimated_effort_hours": 10,
                "owner": "Data Science Team"
            })
        
        # Recommendation 6: Medium - Missing data handling framework
        if avg_completeness < 80:
            recommendations.append({
                "recommendation_id": "rec_profile_missing_data_strategy",
                "agent_id": "unified-profiler",
                "field_name": f"all ({len([f for f in field_profiles if f.get('properties', {}).get('null_percentage', 0) > 0])} fields with nulls)",
                "priority": "high" if avg_completeness < 60 else "medium",
                "recommendation": f"Implement missing data handling: 1) Completeness score {avg_completeness:.1f}/100, 2) Choose strategy per field: drop, impute, or interpolate, 3) Use 'Null Handler' agent for automated imputation, 4) Document all missing data decisions and assumptions",
                "timeline": "1-2 weeks",
                "estimated_effort_hours": 10,
                "owner": "Data Quality Team"
            })
        
        # Recommendation 7: Medium - PII/Sensitive data protection
        if pii_fields:
            critical_pii_count = len([f for f in pii_fields if f.get("properties", {}).get("sensitivity_level") == "critical"])
            recommendations.append({
                "recommendation_id": "rec_profile_pii_protection",
                "agent_id": "unified-profiler",
                "field_name": f"{len(pii_fields)} PII field(s)",
                "priority": "critical" if critical_pii_count > 0 else "high",
                "recommendation": f"Implement PII protection for {len(pii_fields)} sensitive field(s): 1) Encrypt critical PII ({critical_pii_count} field(s)), 2) Implement role-based access controls, 3) Add comprehensive audit logging, 4) Use 'Score Risk' agent for compliance assessment, 5) Document data lineage and usage",
                "timeline": "immediate" if critical_pii_count > 0 else "1 week",
                "estimated_effort_hours": 16 if critical_pii_count > 0 else 10,
                "owner": "Privacy & Security Officer"
            })
        
        # Recommendation 8: Medium - Cardinality optimization
        if low_cardinality or high_cardinality:
            recommendations.append({
                "recommendation_id": "rec_profile_cardinality_review",
                "agent_id": "unified-profiler",
                "field_name": f"{len(low_cardinality) + len(high_cardinality)} field(s)",
                "priority": "medium",
                "recommendation": f"Optimize cardinality: 1) Review {len(low_cardinality)} low-cardinality fields (consolidation candidates), 2) Verify {len(high_cardinality)} high-cardinality fields are properly indexed, 3) Ensure uniqueness constraints on key fields, 4) Consider encoding categorical variables",
                "timeline": "2 weeks",
                "estimated_effort_hours": 6,
                "owner": "Database Administrator"
            })
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = []
        
        # Overall Data Quality Score
        executive_summary.append({
            "summary_id": "exec_quality",
            "title": "Overall Data Quality Score",
            "value": str(round(overall_quality_score, 1)),
            "status": "excellent" if overall_quality_score >= 90 else "good" if overall_quality_score >= 80 else "fair",
            "description": f"Grade {quality_grade}: {overall_quality_score:.1f}/100"
        })
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_text_parts = []
        ai_analysis_text_parts.append(f"DATA QUALITY: Overall score {overall_quality_score:.1f}/100 (Grade {quality_grade})")
        ai_analysis_text_parts.append(f"- Completeness: {quality_summary.get('completeness_score', 0):.1f}/100")
        ai_analysis_text_parts.append(f"- Validity: {quality_summary.get('validity_score', 0):.1f}/100")
        ai_analysis_text_parts.append(f"- Consistency: {quality_summary.get('consistency_score', 0):.1f}/100")
        
        if fields_with_issues > 0:
            ai_analysis_text_parts.append(f"- {fields_with_issues} field(s) require attention (quality score < 80)")
        
        if quality_summary.get("critical_issues", 0) > 0:
            ai_analysis_text_parts.append(f"- {quality_summary.get('critical_issues', 0)} critical quality issue(s) detected")
        
        ai_analysis_text = "\n".join(ai_analysis_text_parts)
        
        return {
            "status": "success",
            "agent_id": "unified-profiler",
            "agent_name": "UnifiedProfiler",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_columns": len(df.columns),
                "total_rows": len(df),
                "columns_with_issues": len([f for f in field_profiles if f["quality_score"] < 80])
            },
            "data": {
                "fields": field_profiles,
                "quality_summary": quality_summary,
                "overrides": {
                    "null_alert_threshold": null_alert_threshold,
                    "categorical_threshold": categorical_threshold,
                    "categorical_ratio_threshold": categorical_ratio_threshold,
                    "top_n_values": top_n_values,
                    "outlier_iqr_multiplier": outlier_iqr_multiplier,
                    "outlier_alert_threshold": outlier_alert_threshold
                }
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
