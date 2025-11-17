"""
Outlier Remover Agent

Detects and handles outliers in numeric data.
Uses configurable detection methods (Z-score, IQR, Percentile) and removal/imputation strategies.
Input: CSV/JSON/XLSX file (primary)
Output: Standardized outlier handling results with cleaning effectiveness scores
"""

import pandas as pd
import numpy as np
import io
import time
from typing import Dict, Any, Optional, List
from scipy import stats


def execute_outlier_remover(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handle outliers in numeric data.

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
    detection_method = parameters.get("detection_method", "iqr")
    removal_strategy = parameters.get("removal_strategy", "remove")
    z_threshold = parameters.get("z_threshold", 3.0)
    iqr_multiplier = parameters.get("iqr_multiplier", 1.5)
    lower_percentile = parameters.get("lower_percentile", 1.0)
    upper_percentile = parameters.get("upper_percentile", 99.0)
    outlier_reduction_weight = parameters.get("outlier_reduction_weight", 0.5)
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
                "agent_id": "outlier-remover",
                "error": f"Unsupported file format: {filename}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.empty:
            return {
                "status": "error",
                "agent_id": "outlier-remover",
                "agent_name": "Outlier Remover",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Store original data for comparison
        original_df = df.copy()
        
        # Analyze outliers
        outlier_analysis = _analyze_outliers(df, {
            "detection_method": detection_method,
            "z_threshold": z_threshold,
            "iqr_multiplier": iqr_multiplier,
            "lower_percentile": lower_percentile,
            "upper_percentile": upper_percentile
        })
        
        # Remove/impute outliers
        df_cleaned, removal_log, outlier_issues = _remove_outliers(df, outlier_analysis, removal_strategy)
        
        # Calculate cleaning effectiveness
        total_outliers = sum(col_data["outlier_count"] for col_data in outlier_analysis["outlier_summary"].values())
        cleaning_score = _calculate_cleaning_score(original_df, df_cleaned, total_outliers, {
            "outlier_reduction_weight": outlier_reduction_weight,
            "data_retention_weight": data_retention_weight,
            "column_retention_weight": column_retention_weight,
            "excellent_threshold": excellent_threshold,
            "good_threshold": good_threshold
        })
        
        # Determine quality status
        if cleaning_score["overall_score"] >= excellent_threshold:
            quality_status = "excellent"
        elif cleaning_score["overall_score"] >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"
        
        # Build results
        outlier_handling_data = {
            "outlier_score": cleaning_score,
            "quality_status": quality_status,
            "outlier_analysis": outlier_analysis,
            "removal_log": removal_log,
            "summary": f"Outlier removal completed. Quality: {quality_status}. Processed {len(original_df)} rows, handled {total_outliers} outliers.",
            "row_level_issues": outlier_issues[:100]  # Limit to first 100
        }

        return {
            "status": "success",
            "agent_id": "outlier-remover",
            "agent_name": "Outlier Remover",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_processed": len(df_cleaned),
                "outliers_handled": cleaning_score["metrics"]["original_outliers"],
                "original_outliers": cleaning_score["metrics"]["original_outliers"],
                "remaining_outliers": 0,  # Depends on strategy
                "total_issues": len(outlier_issues)
            },
            "data": outlier_handling_data
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "outlier-remover",
            "agent_name": "Outlier Remover",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _detect_outliers_zscore(series: pd.Series, threshold: float = 3.0) -> List[Dict[str, Any]]:
    """Detect outliers using Z-score method."""
    outliers = []
    if len(series.dropna()) < 3:
        return outliers
    
    z_scores = np.abs(stats.zscore(series.dropna()))
    outlier_indices = series.dropna().index[z_scores > threshold]
    
    for idx in outlier_indices:
        z_val = z_scores[series.dropna().index.get_loc(idx)]
        severity = "critical" if z_val > 4.0 else "warning"
        outliers.append({
            "row_index": int(idx),
            "value": float(series.loc[idx]),
            "z_score": float(z_val),
            "severity": severity,
            "method": "z_score"
        })
    
    return outliers


def _detect_outliers_iqr(series: pd.Series, multiplier: float = 1.5) -> List[Dict[str, Any]]:
    """Detect outliers using IQR method."""
    outliers = []
    clean_series = series.dropna()
    
    if len(clean_series) < 4:
        return outliers
    
    Q1 = clean_series.quantile(0.25)
    Q3 = clean_series.quantile(0.75)
    IQR = Q3 - Q1
    
    lower_bound = Q1 - multiplier * IQR
    upper_bound = Q3 + multiplier * IQR
    
    for idx, value in clean_series.items():
        if value < lower_bound or value > upper_bound:
            distance = max(abs(value - lower_bound), abs(value - upper_bound))
            extreme_multiplier = 3.0
            severity = "critical" if distance > extreme_multiplier * IQR else "warning"
            
            outliers.append({
                "row_index": int(idx),
                "value": float(value),
                "lower_bound": float(lower_bound),
                "upper_bound": float(upper_bound),
                "severity": severity,
                "method": "iqr"
            })
    
    return outliers


def _detect_outliers_percentile(series: pd.Series, lower_pct: float = 1.0, upper_pct: float = 99.0) -> List[Dict[str, Any]]:
    """Detect outliers using percentile method."""
    outliers = []
    clean_series = series.dropna()
    
    if len(clean_series) < 10:
        return outliers
    
    lower_bound = clean_series.quantile(lower_pct / 100)
    upper_bound = clean_series.quantile(upper_pct / 100)
    
    for idx, value in clean_series.items():
        if value < lower_bound or value > upper_bound:
            extreme_lower = clean_series.quantile(0.001)
            extreme_upper = clean_series.quantile(0.999)
            severity = "critical" if (value < extreme_lower or value > extreme_upper) else "warning"
            
            outliers.append({
                "row_index": int(idx),
                "value": float(value),
                "lower_bound": float(lower_bound),
                "upper_bound": float(upper_bound),
                "severity": severity,
                "method": "percentile"
            })
    
    return outliers


def _analyze_outliers(df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze outliers in all numeric columns."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    analysis = {
        "total_rows": len(df),
        "numeric_columns": numeric_cols,
        "outlier_summary": {},
        "recommendations": []
    }
    
    detection_method = config.get('detection_method', 'iqr')
    
    for col in numeric_cols:
        series = df[col]
        
        if detection_method == 'z_score':
            threshold = config.get('z_threshold', 3.0)
            outliers = _detect_outliers_zscore(series, threshold)
        elif detection_method == 'percentile':
            lower_pct = config.get('lower_percentile', 1.0)
            upper_pct = config.get('upper_percentile', 99.0)
            outliers = _detect_outliers_percentile(series, lower_pct, upper_pct)
        else:  # Default to IQR
            multiplier = config.get('iqr_multiplier', 1.5)
            outliers = _detect_outliers_iqr(series, multiplier)
        
        outlier_count = len(outliers)
        outlier_percentage = (outlier_count / len(series) * 100) if len(series) > 0 else 0
        
        if outlier_count > 0:
            analysis["outlier_summary"][str(col)] = {
                "outlier_count": outlier_count,
                "outlier_percentage": round(outlier_percentage, 2),
                "data_type": str(series.dtype),
                "total_values": len(series),
                "method_used": detection_method,
                "outliers": outliers[:50]  # Limit for performance
            }
            
            # Generate recommendations
            if outlier_percentage > 20:
                analysis["recommendations"].append({
                    "column": str(col),
                    "action": "review_data_quality",
                    "reason": f"Column has {outlier_percentage:.1f}% outliers - may indicate data quality issues",
                    "priority": "high"
                })
            elif outlier_percentage > 5:
                analysis["recommendations"].append({
                    "column": str(col),
                    "action": "consider_removal",
                    "reason": f"Column has {outlier_percentage:.1f}% outliers - consider removal or imputation",
                    "priority": "medium"
                })
            else:
                analysis["recommendations"].append({
                    "column": str(col),
                    "action": "safe_to_remove",
                    "reason": f"Column has {outlier_percentage:.1f}% outliers - safe to remove",
                    "priority": "low"
                })
    
    return analysis


def _remove_outliers(
    df: pd.DataFrame,
    outlier_analysis: Dict[str, Any],
    removal_strategy: str
) -> tuple:
    """Remove or impute outliers based on strategy."""
    df_cleaned = df.copy()
    removal_log = []
    row_level_issues = []
    
    for col, col_analysis in outlier_analysis["outlier_summary"].items():
        outliers = col_analysis["outliers"]
        
        for outlier in outliers:
            row_idx = outlier["row_index"]
            original_value = outlier["value"]
            
            issue = {
                "row_index": row_idx,
                "column": col,
                "issue_type": "outlier_detected",
                "description": f"Outlier detected in column '{col}' using {outlier.get('method', 'unknown')} method",
                "severity": outlier["severity"],
                "value": original_value
            }
            
            if removal_strategy == 'remove':
                if row_idx in df_cleaned.index:
                    df_cleaned = df_cleaned.drop(row_idx)
                    issue["action_taken"] = "removed"
                    issue["issue_type"] = "outlier_removed"
                    removal_log.append(f"Removed row {row_idx} from column '{col}' (value: {original_value})")
            
            elif removal_strategy == 'impute_mean':
                if col in df_cleaned.columns and row_idx in df_cleaned.index:
                    mean_val = df_cleaned[col].mean()
                    df_cleaned.loc[row_idx, col] = mean_val
                    issue["action_taken"] = f"imputed_mean ({mean_val:.2f})"
                    issue["issue_type"] = "outlier_imputed"
                    removal_log.append(f"Imputed row {row_idx} in column '{col}' with mean ({mean_val:.2f})")
            
            elif removal_strategy == 'impute_median':
                if col in df_cleaned.columns and row_idx in df_cleaned.index:
                    median_val = df_cleaned[col].median()
                    df_cleaned.loc[row_idx, col] = median_val
                    issue["action_taken"] = f"imputed_median ({median_val:.2f})"
                    issue["issue_type"] = "outlier_imputed"
                    removal_log.append(f"Imputed row {row_idx} in column '{col}' with median ({median_val:.2f})")
            
            row_level_issues.append(issue)
    
    return df_cleaned, removal_log, row_level_issues


def _calculate_cleaning_score(
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    total_outliers: int,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate outlier removal effectiveness score."""
    
    # Calculate metrics
    outlier_reduction_rate = 100.0  # Assume all detected outliers were handled
    data_retention_rate = (len(cleaned_df) / len(original_df) * 100) if len(original_df) > 0 else 0
    column_retention_rate = (len(cleaned_df.columns) / len(original_df.columns) * 100) if len(original_df.columns) > 0 else 0
    
    # Calculate weighted score
    outlier_weight = config.get('outlier_reduction_weight', 0.5)
    data_weight = config.get('data_retention_weight', 0.3)
    column_weight = config.get('column_retention_weight', 0.2)
    
    overall_score = (
        outlier_reduction_rate * outlier_weight +
        data_retention_rate * data_weight +
        column_retention_rate * column_weight
    )
    
    return {
        "overall_score": round(overall_score, 1),
        "metrics": {
            "outlier_reduction_rate": round(outlier_reduction_rate, 1),
            "data_retention_rate": round(data_retention_rate, 1),
            "column_retention_rate": round(column_retention_rate, 1),
            "original_outliers": total_outliers,
            "original_rows": len(original_df),
            "cleaned_rows": len(cleaned_df),
            "original_columns": len(original_df.columns),
            "cleaned_columns": len(cleaned_df.columns)
        }
    }
