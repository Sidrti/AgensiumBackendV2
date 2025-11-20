"""
Unified Profiler Agent

Comprehensive data profiling with statistics and quality metrics.
Input: CSV file (primary)
Output: Uniform profiling structure with field-level analysis matching API specification
"""

import polars as pl
import numpy as np
import io
import time
import re
from typing import Dict, Any, Optional, List
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
        # Read file - CSV only
        if not filename.endswith('.csv'):
            return {
                "status": "error",
                "error": f"Unsupported file format: {filename}. Only CSV files are supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }
            
        try:
            # Read CSV with Polars
            # infer_schema_length=10000 to get good type inference
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }
        
        # Profile each field
        field_profiles = []
        critical_issues = 0
        warnings = 0
        info_messages = 0
        
        total_rows = df.height
        
        for col in df.columns:
            col_data = df[col]
            null_count = col_data.null_count()
            missing_pct = (null_count / total_rows * 100) if total_rows > 0 else 0
            
            # Determine data type
            dtype = col_data.dtype
            if dtype == pl.Utf8:
                semantic_type = 'string'
            elif dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64]:
                semantic_type = 'integer'
            elif dtype in [pl.Float32, pl.Float64]:
                semantic_type = 'float'
            elif dtype in [pl.Date, pl.Datetime]:
                semantic_type = 'datetime'
            elif dtype == pl.Boolean:
                semantic_type = 'boolean'
            else:
                semantic_type = str(dtype)
            
            # Check for PII/sensitivity
            estimated_pii_type = None
            estimated_sensitivity_level = "low"
            
            col_lower = col.lower()
            
            # Sample for PII detection (non-null strings)
            if dtype == pl.Utf8:
                non_null_sample = col_data.drop_nulls().head(100)
            else:
                non_null_sample = col_data.cast(pl.Utf8).drop_nulls().head(100)
                
            sample_len = non_null_sample.len()
            
            if sample_len > 0:
                # Email detection
                if col_lower in ['email', 'email_address', 'email_addr', 'contact_email']:
                    email_matches = non_null_sample.str.contains('@', literal=True).sum()
                    email_pct = (email_matches / sample_len * 100)
                    if email_pct > 70:
                        estimated_pii_type = "email_address"
                        estimated_sensitivity_level = "high"
                
                # Phone detection
                elif col_lower in ['phone', 'phone_number', 'contact_phone', 'mobile', 'telephone']:
                    phone_pattern = r'^[\d\s\-\(\)\+]{10,}$'
                    phone_matches = non_null_sample.str.contains(phone_pattern).sum()
                    phone_pct = (phone_matches / sample_len * 100)
                    if phone_pct > 70:
                        estimated_pii_type = "phone_number"
                        estimated_sensitivity_level = "high"
                
                # SSN detection
                elif col_lower in ['ssn', 'social_security', 'social_security_number']:
                    ssn_pattern = r'^\d{3}-\d{2}-\d{4}$'
                    ssn_matches = non_null_sample.str.contains(ssn_pattern).sum()
                    ssn_pct = (ssn_matches / sample_len * 100)
                    if ssn_pct > 70:
                        estimated_pii_type = "ssn"
                        estimated_sensitivity_level = "high"
                
                # Name detection
                elif col_lower in ['name', 'full_name', 'first_name', 'last_name', 'person_name', 'customer_name']:
                    # Heuristic: contains letters and spaces, or starts with capital letter
                    # Polars regex check
                    name_pattern = r'[A-Z][a-z]*'
                    name_matches = non_null_sample.str.contains(name_pattern).sum()
                    name_pct = (name_matches / sample_len * 100)
                    if name_pct > 80:
                        estimated_pii_type = "name"
                        estimated_sensitivity_level = "high"
                
                # Credit card detection
                elif col_lower in ['credit_card', 'card_number', 'cc_number', 'payment_card']:
                    cc_pattern = r'^\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}$'
                    cc_matches = non_null_sample.str.contains(cc_pattern).sum()
                    cc_pct = (cc_matches / sample_len * 100)
                    if cc_pct > 70:
                        estimated_pii_type = "credit_card"
                        estimated_sensitivity_level = "critical"
            
            # Calculate quality indicators
            completeness_score = 100 - missing_pct
            unique_count = col_data.n_unique()
            unique_percentage = (unique_count / total_rows * 100) if total_rows > 0 else 0
            
            # Validity score (basic)
            validity_score = 100.0
            outlier_count = 0
            outlier_pct = 0.0
            
            if semantic_type in ['integer', 'float'] and total_rows > 0:
                # Check for outliers
                q1 = col_data.quantile(0.25)
                q3 = col_data.quantile(0.75)
                
                if q1 is not None and q3 is not None:
                    iqr = q3 - q1
                    lower_bound = q1 - outlier_iqr_multiplier * iqr
                    upper_bound = q3 + outlier_iqr_multiplier * iqr
                    
                    # Use DataFrame filter to avoid Series.filter(expr) issues
                    # We just need the count of outliers
                    outlier_count = df.filter((pl.col(col) < lower_bound) | (pl.col(col) > upper_bound)).height
                    outlier_pct = (outlier_count / total_rows * 100)
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
                    "null_count": int(null_count),
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
                    "uniqueness_score": round(unique_percentage, 2),
                    "validity_score": round(validity_score, 2),
                    "consistency_score": round(consistency_score, 2)
                }
            }
            
            # Add statistics
            if semantic_type in ['integer', 'float']:
                non_null_data = col_data.drop_nulls()
                if non_null_data.len() > 0:
                    # Calculate stats
                    # Polars aggregations
                    stats_df = non_null_data.to_frame("val").select([
                        pl.min("val").alias("min"),
                        pl.max("val").alias("max"),
                        pl.mean("val").alias("mean"),
                        pl.median("val").alias("median"),
                        pl.std("val").alias("std"),
                        pl.var("val").alias("var"),
                        pl.col("val").quantile(0.25).alias("p25"),
                        pl.col("val").quantile(0.50).alias("p50"),
                        pl.col("val").quantile(0.75).alias("p75"),
                        pl.col("val").skew().alias("skew"),
                        pl.col("val").kurtosis().alias("kurtosis")
                    ])
                    
                    stats_row = stats_df.row(0, named=True)
                    
                    # Entropy
                    value_counts = non_null_data.value_counts()
                    counts = value_counts["count"].to_numpy()
                    entropy_val = stats.entropy(counts) if len(counts) > 0 else 0
                    
                    field_profile["statistics"] = {
                        "type": "numeric",
                        "count": non_null_data.len(),
                        "min": _safe_float(stats_row["min"]),
                        "max": _safe_float(stats_row["max"]),
                        "mean": _safe_float(stats_row["mean"]),
                        "median": _safe_float(stats_row["median"]),
                        "stddev": _safe_float(stats_row["std"]),
                        "variance": _safe_float(stats_row["var"]),
                        "p25": _safe_float(stats_row["p25"]),
                        "p50": _safe_float(stats_row["p50"]),
                        "p75": _safe_float(stats_row["p75"]),
                        "skewness": _safe_float(stats_row["skew"]),
                        "kurtosis": _safe_float(stats_row["kurtosis"]),
                        "outlier_count": int(outlier_count),
                        "outlier_percentage": round(outlier_pct, 2),
                        "entropy": float(entropy_val)
                    }
            else:
                # String statistics
                non_null_data = col_data.drop_nulls().cast(pl.Utf8)
                if non_null_data.len() > 0:
                    lengths = non_null_data.str.len_bytes() # Approximate char length
                    
                    # Entropy
                    value_counts = non_null_data.value_counts()
                    counts = value_counts["count"].to_numpy()
                    entropy_val = stats.entropy(counts) if len(counts) > 0 else 0
                    
                    # Charset diversity
                    has_special = non_null_data.str.contains(r'[!@#$%^&*()_+=\[\]{};:\'",.<>?/\\|`~-]').any()
                    
                    field_profile["statistics"] = {
                        "type": "string",
                        "min_length": int(lengths.min()) if lengths.len() > 0 else 0,
                        "max_length": int(lengths.max()) if lengths.len() > 0 else 0,
                        "avg_length": round(float(lengths.mean()), 2) if lengths.len() > 0 else 0,
                        "entropy": round(float(entropy_val), 2),
                        "charset_diversity": ["alphanumeric", "special"] if has_special else ["alphanumeric"]
                    }
            
            # Add distribution (top values)
            # Polars value_counts
            top_vals_df = col_data.value_counts(sort=True).head(top_n_values)
            top_values_list = []
            
            for row in top_vals_df.iter_rows(named=True):
                val = row[col]
                count = row["count"]
                top_values_list.append({
                    "value": str(val),
                    "count": int(count),
                    "percentage": round((count / total_rows * 100), 2)
                })
                
            field_profile["distribution"] = {
                "type": "non_uniform" if len(top_values_list) > 1 else "uniform",
                "top_values": top_values_list
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
        
        # Limit row level issues processing to avoid performance hit on large files
        # We can process in chunks or just limit the number of issues found
        
        for col in df.columns:
            if len(row_level_issues) >= 1000: break
            
            col_data = df[col]
            dtype = col_data.dtype
            
            # Issue 1: Null values
            # Filter rows with nulls
            null_rows = df.with_row_index("row_index").filter(pl.col(col).is_null())
            
            for row in null_rows.iter_rows(named=True):
                if len(row_level_issues) >= 1000: break
                row_level_issues.append({
                    "row_index": int(row["row_index"]),
                    "column": col,
                    "issue_type": "null",
                    "severity": "warning",
                    "message": f"Null/missing value in column '{col}'",
                    "value": None
                })
            
            # Issue 2: Outliers (numeric fields only)
            if dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64, pl.Float32, pl.Float64]:
                q1 = col_data.quantile(0.25)
                q3 = col_data.quantile(0.75)
                
                if q1 is not None and q3 is not None:
                    iqr = q3 - q1
                    lower_bound = q1 - outlier_iqr_multiplier * iqr
                    upper_bound = q3 + outlier_iqr_multiplier * iqr
                    
                    outlier_rows = df.with_row_index("row_index").filter(
                        (pl.col(col) < lower_bound) | (pl.col(col) > upper_bound)
                    )
                    
                    for row in outlier_rows.iter_rows(named=True):
                        if len(row_level_issues) >= 1000: break
                        val = row[col]
                        row_level_issues.append({
                            "row_index": int(row["row_index"]),
                            "column": col,
                            "issue_type": "outlier",
                            "severity": "warning",
                            "message": f"Outlier detected in '{col}': value {val} outside IQR bounds [{lower_bound:.2f}, {upper_bound:.2f}]",
                            "value": float(val) if val is not None else None,
                            "bounds": {
                                "lower": float(lower_bound),
                                "upper": float(upper_bound)
                            }
                        })
            
            # Issue 3: Type mismatches (check if non-null values don't match expected type)
            if dtype == pl.Utf8:
                # Try to detect numeric values in string columns
                # Regex check for numeric
                numeric_pattern = r"^-?\d+(\.\d+)?$"
                numeric_rows = df.with_row_index("row_index").filter(
                    pl.col(col).is_not_null() & pl.col(col).str.contains(numeric_pattern)
                )
                
                # Only report if it's a mixed column (not fully numeric which would be handled by type inference usually, but here we are checking Utf8)
                # If the column is Utf8, it means Polars inferred it as string. If we find numbers, it might be mixed.
                
                for row in numeric_rows.iter_rows(named=True):
                    if len(row_level_issues) >= 1000: break
                    val = row[col]
                    row_level_issues.append({
                        "row_index": int(row["row_index"]),
                        "column": col,
                        "issue_type": "type_mismatch",
                        "severity": "info",
                        "message": f"Value in '{col}' could be interpreted as numeric: {val}",
                        "value": str(val)
                    })
            
            # Issue 4: Distribution anomalies (z-score)
            if dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64, pl.Float32, pl.Float64]:
                mean_val = col_data.mean()
                std_val = col_data.std()
                
                if mean_val is not None and std_val is not None and std_val > 0:
                    # Calculate z-scores
                    # Filter rows with abs(z_score) > 3
                    anomaly_rows = df.with_row_index("row_index").filter(
                        pl.col(col).is_not_null() &
                        (((pl.col(col) - mean_val) / std_val).abs() > 3)
                    )
                    
                    for row in anomaly_rows.iter_rows(named=True):
                        if len(row_level_issues) >= 1000: break
                        val = row[col]
                        z_score = (val - mean_val) / std_val
                        row_level_issues.append({
                            "row_index": int(row["row_index"]),
                            "column": col,
                            "issue_type": "distribution_anomaly",
                            "severity": "info",
                            "message": f"Value in '{col}' is statistically unusual (z-score: {abs(z_score):.2f}): {val}",
                            "value": float(val),
                            "z_score": float(z_score)
                        })

        # Cap row-level-issues at 1000
        row_level_issues = row_level_issues[:1000]
        
        # Calculate issue summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {},
            "affected_rows": len(set(issue["row_index"] for issue in row_level_issues)),
            "affected_columns": sorted(list(set(issue["column"] for issue in row_level_issues)))
        }
        
        for issue in row_level_issues:
            issue_type = issue["issue_type"]
            issue_summary["by_type"][issue_type] = issue_summary["by_type"].get(issue_type, 0) + 1
            severity = issue["severity"]
            issue_summary["by_severity"][severity] = issue_summary["by_severity"].get(severity, 0) + 1
            
        # Create quality summary
        quality_summary = {
            "overall_quality_score": overall_quality_score,
            "quality_grade": "A" if overall_quality_score >= 90 else "B" if overall_quality_score >= 80 else "C" if overall_quality_score >= 70 else "D" if overall_quality_score >= 60 else "F",
            "completeness_score": round(np.mean([f["quality_indicators"]["completeness_score"] for f in field_profiles]), 2) if field_profiles else 0,
            "validity_score": round(np.mean([f["quality_indicators"]["validity_score"] for f in field_profiles]), 2) if field_profiles else 0,
            "consistency_score": round(np.mean([f["quality_indicators"]["consistency_score"] for f in field_profiles]), 2) if field_profiles else 0,
            "accuracy_score": round(np.mean([f["quality_indicators"]["validity_score"] for f in field_profiles]), 2) if field_profiles else 0,
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
        # (Simplified as we don't have distribution shape analysis in this version yet, but keeping structure)
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

def _safe_float(val):
    """Safely convert to float, handling None/NaN."""
    if val is None:
        return 0.0
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return 0.0
        return f
    except:
        return 0.0
