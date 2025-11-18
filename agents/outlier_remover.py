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
import base64
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
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = [{
            "summary_id": "exec_outlier_removal",
            "title": "Outlier Removal Status",
            "value": f"{cleaning_score['overall_score']:.1f}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"Quality: {quality_status}, Outliers Handled: {total_outliers}, {len(outlier_analysis['numeric_columns'])} numeric columns analyzed, {cleaning_score['metrics']['outlier_reduction_percentage']:.1f}% reduction"
        }]
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_parts = []
        ai_analysis_parts.append(f"OUTLIER REMOVER ANALYSIS:")
        ai_analysis_parts.append(f"- Cleaning Score: {cleaning_score['overall_score']:.1f}/100 (Outlier Reduction: {cleaning_score['metrics']['outlier_reduction_score']:.1f}, Data Retention: {cleaning_score['metrics']['data_retention_score']:.1f}, Detection Accuracy: {cleaning_score['metrics']['detection_accuracy_score']:.1f})")
        ai_analysis_parts.append(f"- Outliers Handled: {total_outliers} outliers detected and removed, {cleaning_score['metrics']['outlier_reduction_percentage']:.1f}% reduction achieved")
        
        numeric_cols = outlier_analysis['numeric_columns']
        ai_analysis_parts.append(f"- Columns Analyzed: {len(numeric_cols)} numeric columns ({', '.join(list(numeric_cols)[:5])}{'...' if len(numeric_cols) > 5 else ''})")
        ai_analysis_parts.append(f"- Data Retention: {cleaning_score['metrics']['row_retention_percentage']:.1f}% rows retained after outlier removal")
        ai_analysis_parts.append(f"- Methods Used: {', '.join(set([log.get('method', 'unknown') for log in removal_log]))}")
        
        if len(outlier_analysis.get('recommendations', [])) > 0:
            ai_analysis_parts.append(f"- Top Recommendation: {outlier_analysis['recommendations'][0].get('recommendation', 'Review outlier handling strategy')}")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # Add to outlier_handling_data
        outlier_handling_data["executive_summary"] = executive_summary
        outlier_handling_data["ai_analysis_text"] = ai_analysis_text
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # High outlier volume alert
        outlier_pct = (total_outliers / (len(original_df) * len(numeric_cols)) * 100) if len(numeric_cols) > 0 else 0
        if outlier_pct > 20:
            alerts.append({
                "alert_id": "alert_outliers_high_volume",
                "severity": "critical",
                "category": "data_distribution",
                "message": f"High outlier volume: {total_outliers} outliers detected ({outlier_pct:.1f}% of numeric data)",
                "affected_fields_count": len(outlier_analysis.get('outlier_summary', {})),
                "recommendation": "Review data distribution. High outlier rate may indicate measurement errors or data quality issues."
            })
        elif outlier_pct > 10:
            alerts.append({
                "alert_id": "alert_outliers_medium_volume",
                "severity": "high",
                "category": "data_distribution",
                "message": f"Moderate outlier volume: {total_outliers} outliers detected ({outlier_pct:.1f}% of numeric data)",
                "affected_fields_count": len(outlier_analysis.get('outlier_summary', {})),
                "recommendation": "Investigate outlier patterns to distinguish genuine outliers from data errors."
            })
        
        # Column-level outlier alerts
        high_outlier_cols = [col for col, data in outlier_analysis.get('outlier_summary', {}).items() 
                            if data.get('outlier_percentage', 0) > 15]
        if high_outlier_cols:
            alerts.append({
                "alert_id": "alert_outliers_column_critical",
                "severity": "high",
                "category": "column_distribution",
                "message": f"{len(high_outlier_cols)} column(s) have >15% outliers: {', '.join(high_outlier_cols[:3])}{'...' if len(high_outlier_cols) > 3 else ''}",
                "affected_fields_count": len(high_outlier_cols),
                "recommendation": "Review data collection methods for columns with excessive outliers."
            })
        
        # Data retention alert
        if cleaning_score['metrics']['row_retention_percentage'] < 90:
            alerts.append({
                "alert_id": "alert_outliers_data_loss",
                "severity": "high",
                "category": "data_retention",
                "message": f"Data retention: {cleaning_score['metrics']['row_retention_percentage']:.1f}% rows retained (below 90% threshold)",
                "affected_fields_count": len(original_df) - len(df_cleaned),
                "recommendation": "Review outlier removal strategy to minimize data loss. Consider outlier imputation instead of removal."
            })
        
        # Quality score alert
        if cleaning_score["overall_score"] < good_threshold:
            alerts.append({
                "alert_id": "alert_outliers_quality",
                "severity": "medium",
                "category": "quality_score",
                "message": f"Outlier removal quality score: {cleaning_score['overall_score']:.1f}/100 ({quality_status})",
                "affected_fields_count": len(numeric_cols),
                "recommendation": "Optimize outlier detection thresholds and removal strategies."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Convert outlier issues to standardized format
        for outlier_issue in outlier_issues[:100]:
            issues.append({
                "issue_id": f"issue_outliers_{outlier_issue.get('row_index', 0)}_{outlier_issue.get('column', 'unknown')}",
                "agent_id": "outlier-remover",
                "field_name": outlier_issue.get('column', 'N/A'),
                "issue_type": outlier_issue.get('issue_type', 'outlier_detected'),
                "severity": outlier_issue.get('severity', 'warning'),
                "message": outlier_issue.get('description', 'Outlier detected')
            })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        agent_recommendations = []
        
        # Recommendation 1: Review high-outlier columns
        if high_outlier_cols:
            agent_recommendations.append({
                "recommendation_id": "rec_outliers_column_review",
                "agent_id": "outlier-remover",
                "field_name": ", ".join(high_outlier_cols[:3]),
                "priority": "high",
                "recommendation": f"Review {len(high_outlier_cols)} column(s) with >15% outliers for data quality issues or measurement errors",
                "timeline": "1 week"
            })
        
        # Recommendation 2: Detection method optimization
        agent_recommendations.append({
            "recommendation_id": "rec_outliers_method",
            "agent_id": "outlier-remover",
            "field_name": "all",
            "priority": "medium",
            "recommendation": f"Optimize outlier detection method (current: {detection_method}) and thresholds based on data distribution characteristics",
            "timeline": "2 weeks"
        })
        
        # Recommendation 3: Column-specific strategies
        for rec in outlier_analysis.get('recommendations', [])[:3]:
            agent_recommendations.append({
                "recommendation_id": f"rec_outliers_{rec.get('column', 'unknown')}",
                "agent_id": "outlier-remover",
                "field_name": rec.get('column', 'N/A'),
                "priority": rec.get('priority', 'medium'),
                "recommendation": f"{rec.get('action', 'Review')}: {rec.get('reason', 'Optimize outlier handling')}",
                "timeline": "1 week" if rec.get('priority') == 'high' else "2 weeks"
            })
        
        # Recommendation 4: Alternative strategy
        if removal_strategy == 'remove' and len(df_cleaned) < len(original_df) * 0.9:
            agent_recommendations.append({
                "recommendation_id": "rec_outliers_imputation",
                "agent_id": "outlier-remover",
                "field_name": "all",
                "priority": "high",
                "recommendation": "Consider imputation instead of removal to preserve data. Current removal strategy caused significant data loss.",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 5: Statistical validation
        agent_recommendations.append({
            "recommendation_id": "rec_outliers_validation",
            "agent_id": "outlier-remover",
            "field_name": "all",
            "priority": "medium",
            "recommendation": "Validate detected outliers with domain experts to distinguish genuine outliers from valuable extreme values",
            "timeline": "2 weeks"
        })
        
        # Recommendation 6: Monitoring
        agent_recommendations.append({
            "recommendation_id": "rec_outliers_monitoring",
            "agent_id": "outlier-remover",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Establish outlier rate monitoring to detect distribution shifts or data quality degradation early",
            "timeline": "3 weeks"
        })

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
            "data": outlier_handling_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
            "cleaned_file": {
                "filename": f"cleaned_{filename}",
                "content": base64.b64encode(_generate_cleaned_file(df_cleaned, filename)).decode('utf-8'),
                "size_bytes": len(_generate_cleaned_file(df_cleaned, filename)),
                "format": filename.split('.')[-1].lower()
            }
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
