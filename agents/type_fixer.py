"""
Type Fixer Agent

Detects and fixes data type inconsistencies in data.
Analyzes column types and applies configurable type conversion strategies.
Input: CSV/JSON/XLSX file (primary)
Output: Standardized type fixing results with effectiveness scores
"""

import pandas as pd
import numpy as np
import io
import re
import time
import base64
from typing import Dict, Any, Optional, List


def execute_type_fixer(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Fix data types in data.

    Args:
        file_contents: File bytes (read as binary)
        filename: Original filename (used to detect format)
        parameters: Agent parameters from tool.json

    Returns:
        Standardized output dictionary
    """

    start_time = time.time()
    parameters = parameters or {}

    # Extract parameters with defaults
    auto_convert_numeric = parameters.get("auto_convert_numeric", True)
    auto_convert_datetime = parameters.get("auto_convert_datetime", True)
    auto_convert_category = parameters.get("auto_convert_category", True)
    preserve_mixed_types = parameters.get("preserve_mixed_types", False)
    type_reduction_weight = parameters.get("type_reduction_weight", 0.5)
    data_retention_weight = parameters.get("data_retention_weight", 0.3)
    column_retention_weight = parameters.get("column_retention_weight", 0.2)
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file based on format
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_contents), on_bad_lines='skip')
        elif filename.endswith('.json'):
            df = pd.read_json(io.BytesIO(file_contents))
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(file_contents))
        else:
            return {
                "status": "error",
                "agent_id": "type-fixer",
                "error": f"Unsupported file format: {filename}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.empty:
            return {
                "status": "error",
                "agent_id": "type-fixer",
                "agent_name": "Type Fixer",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Store original data for comparison
        original_df = df.copy()
        
        # Analyze type issues
        type_analysis = _analyze_type_issues(df)
        
        # Generate type fixing recommendations
        fix_config = _generate_fix_config(
            type_analysis,
            auto_convert_numeric,
            auto_convert_datetime,
            auto_convert_category
        )
        
        # Apply type fixes
        df_fixed, fix_log = _apply_type_fixes(df, fix_config)
        
        # Calculate fixing effectiveness
        fixing_score = _calculate_fixing_score(original_df, df_fixed, type_analysis, {
            "type_reduction_weight": type_reduction_weight,
            "data_retention_weight": data_retention_weight,
            "column_retention_weight": column_retention_weight,
            "excellent_threshold": excellent_threshold,
            "good_threshold": good_threshold
        })
        
        # Determine quality status
        if fixing_score["overall_score"] >= excellent_threshold:
            quality_status = "excellent"
        elif fixing_score["overall_score"] >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"
        
        # Identify type fixing issues
        type_issues = _identify_type_issues(original_df, df_fixed, type_analysis)
        
        # Build results
        type_fixing_data = {
            "fixing_score": fixing_score,
            "quality_status": quality_status,
            "type_analysis": type_analysis,
            "fix_log": fix_log,
            "summary": f"Type fixing completed. Quality: {quality_status}. Processed {len(original_df)} rows, fixed {len(fix_log)} type issues.",
            "row_level_issues": type_issues[:100]  # Limit to first 100
        }

        # Generate cleaned file (CSV format)
        cleaned_file_bytes = _generate_cleaned_file(df_fixed, filename)
        cleaned_file_base64 = base64.b64encode(cleaned_file_bytes).decode('utf-8')

        return {
            "status": "success",
            "agent_id": "type-fixer",
            "agent_name": "Type Fixer",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_processed": len(df_fixed),
                "type_issues_fixed": len(fix_log),
                "original_type_issues": type_analysis['total_issues'],
                "remaining_type_issues": type_analysis['total_issues'] - len(fix_log),
                "total_issues": len(type_issues)
            },
            "data": type_fixing_data,
            "cleaned_file": {
                "filename": f"cleaned_{filename}",
                "content": cleaned_file_base64,
                "size_bytes": len(cleaned_file_bytes),
                "format": filename.split('.')[-1].lower()
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "type-fixer",
            "agent_name": "Type Fixer",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _analyze_type_issues(df: pd.DataFrame) -> Dict[str, Any]:
    """Analyze data type inconsistencies in the dataset."""
    type_analysis = {
        "total_columns": len(df.columns),
        "columns_with_issues": [],
        "total_issues": 0,
        "type_summary": {},
        "recommendations": []
    }
    
    for col in df.columns:
        col_data = df[col].dropna()
        if len(col_data) == 0:
            continue
            
        current_dtype = str(df[col].dtype)
        issues = []
        suggested_type = current_dtype
        
        # Check for mixed types in object columns
        if current_dtype == 'object':
            numeric_count = 0
            date_count = 0
            string_count = 0
            
            sample_size = min(100, len(col_data))
            for val in col_data.head(sample_size):
                if _is_numeric_string(str(val)):
                    numeric_count += 1
                elif _is_date_string(str(val)):
                    date_count += 1
                else:
                    string_count += 1
            
            total_sampled = numeric_count + date_count + string_count
            if total_sampled > 0:
                numeric_pct = (numeric_count / total_sampled) * 100
                date_pct = (date_count / total_sampled) * 100
                
                if numeric_pct > 70:
                    issues.append("Should be numeric type")
                    suggested_type = "numeric"
                elif date_pct > 70:
                    issues.append("Should be datetime type")
                    suggested_type = "datetime"
        
        # Check for incorrectly typed numeric columns
        elif current_dtype in ['int64', 'float64']:
            if current_dtype == 'float64':
                try:
                    is_all_int = col_data.apply(lambda x: float(x).is_integer() if pd.notnull(x) else True).all()
                    if is_all_int:
                        issues.append("Float column contains only integer values")
                        suggested_type = "integer"
                except:
                    pass
        
        if issues:
            type_analysis["columns_with_issues"].append(str(col))
            type_analysis["total_issues"] += 1
            type_analysis["type_summary"][str(col)] = {
                "current_type": current_dtype,
                "suggested_type": suggested_type,
                "issues": issues,
                "sample_values": [str(x) for x in col_data.head(5).tolist()]
            }
            
            priority = "high" if len(issues) > 1 else "medium"
            type_analysis["recommendations"].append({
                "column": str(col),
                "action": f"convert_to_{suggested_type}",
                "reason": "; ".join(issues),
                "priority": priority
            })
    
    return type_analysis


def _is_numeric_string(value: str) -> bool:
    """Check if a string represents a numeric value."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def _is_date_string(value: str) -> bool:
    """Check if a string represents a date."""
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
        r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
    ]
    
    for pattern in date_patterns:
        if re.match(pattern, str(value)):
            return True
    return False


def _generate_fix_config(
    type_analysis: Dict[str, Any],
    auto_numeric: bool,
    auto_datetime: bool,
    auto_category: bool
) -> Dict[str, Any]:
    """Generate type fixing configuration based on analysis."""
    config = {"column_fixes": {}}
    
    for col, issue_data in type_analysis.get("type_summary", {}).items():
        if not auto_numeric and issue_data.get("suggested_type") == "numeric":
            continue
        if not auto_datetime and issue_data.get("suggested_type") == "datetime":
            continue
        if not auto_category and issue_data.get("suggested_type") == "category":
            continue
        
        config["column_fixes"][col] = issue_data.get("suggested_type", "string")
    
    return config


def _apply_type_fixes(df: pd.DataFrame, fix_config: Dict[str, Any]) -> tuple:
    """Apply type fixes to the dataframe."""
    df_fixed = df.copy()
    fix_log = []
    
    column_fixes = fix_config.get('column_fixes', {})
    
    for col, target_type in column_fixes.items():
        if col not in df_fixed.columns:
            continue
            
        try:
            original_type = str(df_fixed[col].dtype)
            
            if target_type == 'numeric':
                df_fixed[col] = pd.to_numeric(df_fixed[col], errors='coerce')
                fix_log.append(f"Converted '{col}' from {original_type} to numeric")
                
            elif target_type == 'integer':
                df_fixed[col] = df_fixed[col].astype('Int64')
                fix_log.append(f"Converted '{col}' from {original_type} to integer")
                
            elif target_type == 'datetime':
                df_fixed[col] = pd.to_datetime(df_fixed[col], errors='coerce')
                fix_log.append(f"Converted '{col}' from {original_type} to datetime")
                
            elif target_type == 'string':
                df_fixed[col] = df_fixed[col].astype(str)
                fix_log.append(f"Converted '{col}' from {original_type} to string")
                
            elif target_type == 'category':
                df_fixed[col] = df_fixed[col].astype('category')
                fix_log.append(f"Converted '{col}' from {original_type} to category")
                
        except Exception as e:
            fix_log.append(f"Error converting '{col}' to {target_type}: {str(e)}")
    
    return df_fixed, fix_log


def _calculate_fixing_score(
    original_df: pd.DataFrame,
    fixed_df: pd.DataFrame,
    type_analysis: Dict[str, Any],
    config: dict
) -> Dict[str, Any]:
    """Calculate type fixing effectiveness score."""
    original_issues = type_analysis.get('total_issues', 0)
    
    # Re-analyze to get remaining issues
    remaining_analysis = _analyze_type_issues(fixed_df)
    remaining_issues = remaining_analysis.get('total_issues', 0)
    
    # Calculate metrics
    issue_reduction_rate = ((original_issues - remaining_issues) / original_issues * 100) if original_issues > 0 else 100
    data_retention_rate = (len(fixed_df) / len(original_df) * 100) if len(original_df) > 0 else 0
    column_retention_rate = (len(fixed_df.columns) / len(original_df.columns) * 100) if len(original_df.columns) > 0 else 0
    
    # Calculate weighted score
    issue_weight = float(config.get('type_reduction_weight', 0.5))
    data_weight = float(config.get('data_retention_weight', 0.3))
    column_weight = float(config.get('column_retention_weight', 0.2))
    
    overall_score = (
        float(issue_reduction_rate) * issue_weight +
        float(data_retention_rate) * data_weight +
        float(column_retention_rate) * column_weight
    )
    
    # Determine fixing quality
    excellent_threshold = float(config.get('excellent_threshold', 90))
    good_threshold = float(config.get('good_threshold', 75))
    
    if overall_score >= excellent_threshold:
        quality = "excellent"
        quality_color = "green"
    elif overall_score >= good_threshold:
        quality = "good"
        quality_color = "yellow"
    else:
        quality = "needs_improvement"
        quality_color = "red"
    
    return _convert_numpy_types({
        "overall_score": round(overall_score, 1),
        "quality": quality,
        "quality_color": quality_color,
        "metrics": {
            "issue_reduction_rate": round(issue_reduction_rate, 1),
            "data_retention_rate": round(data_retention_rate, 1),
            "column_retention_rate": round(column_retention_rate, 1),
            "original_issues": original_issues,
            "remaining_issues": remaining_issues,
            "original_rows": len(original_df),
            "fixed_rows": len(fixed_df),
            "original_columns": len(original_df.columns),
            "fixed_columns": len(fixed_df.columns)
        },
        "weights_used": {
            "type_reduction_weight": issue_weight,
            "data_retention_weight": data_weight,
            "column_retention_weight": column_weight
        }
    })


def _identify_type_issues(
    original_df: pd.DataFrame,
    fixed_df: pd.DataFrame,
    type_analysis: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Identify type-level issues in the DataFrame."""
    issues = []
    
    # Add issues from type analysis
    for col, type_data in type_analysis.get("type_summary", {}).items():
        for issue_text in type_data.get("issues", []):
            issues.append({
                "column": str(col),
                "issue_type": "type_mismatch",
                "description": issue_text,
                "severity": "warning",
                "original_type": type_data.get("current_type"),
                "suggested_type": type_data.get("suggested_type")
            })
    
    return issues


def _convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        val = float(obj)
        if np.isnan(val):
            return None
        elif np.isinf(val):
            return str(val)
        return val
    elif isinstance(obj, (float, int)) and not isinstance(obj, bool):
        if isinstance(obj, float):
            if np.isnan(obj):
                return None
            elif np.isinf(obj):
                return str(obj)
        return obj
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: _convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy_types(item) for item in obj]
    else:
        return obj


def _generate_cleaned_file(df: pd.DataFrame, original_filename: str) -> bytes:
    """
    Generate cleaned data file in CSV format.
    
    Args:
        df: Cleaned dataframe
        original_filename: Original filename to determine format
        
    Returns:
        File contents as bytes
    """
    # Always export as CSV for consistency and compatibility
    output = io.BytesIO()
    df.to_csv(output, index=False)
    return output.getvalue()
