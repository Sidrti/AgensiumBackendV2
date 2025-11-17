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
                "quality_summary": quality_summary
            }
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }
