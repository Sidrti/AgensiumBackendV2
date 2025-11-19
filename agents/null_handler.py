"""
Null Handler Agent

Detects and handles missing values in data.
Analyzes null patterns and applies configurable imputation strategies.
Input: CSV/JSON/XLSX file (primary)
Output: Standardized null handling results with cleaning effectiveness scores
"""

import pandas as pd
import numpy as np
import io
import time
import base64
from typing import Dict, Any, Optional

try:
    from sklearn.impute import KNNImputer
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


def execute_null_handler(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handle missing values in data.

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
    global_strategy = parameters.get("global_strategy", "column_specific")
    column_strategies = parameters.get("column_strategies", {})
    fill_values = parameters.get("fill_values", {})
    knn_neighbors = parameters.get("knn_neighbors", 5)
    null_reduction_weight = parameters.get("null_reduction_weight", 0.5)
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
                "agent_id": "null-handler",
                "error": f"Unsupported file format: {filename}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.empty:
            return {
                "status": "error",
                "agent_id": "null-handler",
                "agent_name": "Null Handler",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Store original data for comparison
        original_df = df.copy()
        
        # Analyze null patterns
        null_analysis = _analyze_null_patterns(df)
        
        # Apply null handling strategies
        df_cleaned, imputation_log = _apply_null_handling(df, global_strategy, column_strategies, fill_values, knn_neighbors)
        
        # Calculate cleaning effectiveness
        cleaning_score = _calculate_cleaning_score(original_df, df_cleaned, null_analysis, {
            "null_reduction_weight": null_reduction_weight,
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
        
        # Identify null handling issues
        null_issues = _identify_null_issues(original_df, df_cleaned)
        
        # Generate cleaned file (CSV format)
        cleaned_file_bytes = _generate_cleaned_file(df_cleaned, filename)
        cleaned_file_base64 = base64.b64encode(cleaned_file_bytes).decode('utf-8')
        
        # Build results
        null_handling_data = {
            "cleaning_score": cleaning_score,
            "quality_status": quality_status,
            "null_analysis": null_analysis,
            "imputation_log": imputation_log,
            "summary": f"Null handling completed. Quality: {quality_status}. Processed {len(original_df)} rows, handled {null_analysis['total_nulls_detected']} null values.",
            "row_level_issues": null_issues[:100]  # Limit to first 100
        }
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = [{
            "summary_id": "exec_null_handling",
            "title": "Null Handling Status",
            "value": f"{cleaning_score['overall_score']:.1f}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "fair",
            "description": f"Quality: {quality_status}, Nulls Handled: {null_analysis['total_nulls_detected']}, {len(null_analysis['columns_with_nulls'])} columns affected, {cleaning_score['metrics']['null_reduction_percentage']:.1f}% reduction"
        }]
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_parts = []
        ai_analysis_parts.append(f"NULL HANDLER ANALYSIS:")
        ai_analysis_parts.append(f"- Cleaning Score: {cleaning_score['overall_score']:.1f}/100 (Null Reduction: {cleaning_score['metrics']['null_reduction_score']:.1f}, Data Retention: {cleaning_score['metrics']['data_retention_score']:.1f}, Column Retention: {cleaning_score['metrics']['column_retention_score']:.1f})")
        ai_analysis_parts.append(f"- Null Reduction: {null_analysis['total_nulls_detected']} nulls handled, {cleaning_score['metrics']['null_reduction_percentage']:.1f}% reduction achieved")
        
        cols_with_nulls = null_analysis['columns_with_nulls']
        ai_analysis_parts.append(f"- Columns Affected: {len(cols_with_nulls)} columns had nulls ({', '.join(list(cols_with_nulls)[:5])}{'...' if len(cols_with_nulls) > 5 else ''})")
        ai_analysis_parts.append(f"- Data Retention: {cleaning_score['metrics']['row_retention_percentage']:.1f}% rows retained, {cleaning_score['metrics']['column_retention_percentage']:.1f}% columns retained")
        ai_analysis_parts.append(f"- Imputation Applied: {len(imputation_log)} strategies used across columns")
        
        if len(null_analysis.get('recommendations', [])) > 0:
            ai_analysis_parts.append(f"- Top Recommendation: {null_analysis['recommendations'][0].get('recommendation', 'Review null handling strategy')}")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # Add to null_handling_data
        null_handling_data["executive_summary"] = executive_summary
        null_handling_data["ai_analysis_text"] = ai_analysis_text
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # Calculate additional metrics for alerts
        null_percentage = (null_analysis['total_nulls_detected'] / (len(original_df) * len(original_df.columns)) * 100) if len(original_df) * len(original_df.columns) > 0 else 0
        
        # Alert 1: High null volume alert
        if null_percentage > 30:
            alerts.append({
                "alert_id": "alert_nulls_high_volume",
                "severity": "critical",
                "category": "missing_data",
                "message": f"High null volume: {null_analysis['total_nulls_detected']} null values detected ({null_percentage:.1f}% of dataset)",
                "affected_fields_count": len(cols_with_nulls),
                "recommendation": "Review data collection process. High null rate indicates systemic data completeness issues."
            })
        elif null_percentage > 10:
            alerts.append({
                "alert_id": "alert_nulls_moderate_volume",
                "severity": "medium",
                "category": "missing_data",
                "message": f"Moderate null volume: {null_analysis['total_nulls_detected']} null values detected ({null_percentage:.1f}% of dataset)",
                "affected_fields_count": len(cols_with_nulls),
                "recommendation": "Monitor data quality trends. Consider implementing validation rules at data entry."
            })
        
        # Alert 2: Column-level critical nulls (>50%)
        high_null_cols = [col for col, data in null_analysis.get('null_summary', {}).items() 
                         if data.get('null_percentage', 0) > 50]
        if high_null_cols:
            alerts.append({
                "alert_id": "alert_nulls_column_critical",
                "severity": "high",
                "category": "column_quality",
                "message": f"{len(high_null_cols)} column(s) have >50% null values: {', '.join(high_null_cols[:3])}{'...' if len(high_null_cols) > 3 else ''}",
                "affected_fields_count": len(high_null_cols),
                "recommendation": "Consider dropping columns with excessive nulls or implementing advanced imputation strategies."
            })
        
        # Alert 3: Column retention warning
        columns_dropped = len(original_df.columns) - len(df_cleaned.columns)
        if columns_dropped > 0:
            column_retention_pct = cleaning_score['metrics'].get('column_retention_percentage', 100)
            severity = "high" if column_retention_pct < 80 else "medium"
            alerts.append({
                "alert_id": "alert_nulls_column_retention",
                "severity": severity,
                "category": "column_quality",
                "message": f"Column retention: {column_retention_pct:.1f}% - {columns_dropped} column(s) dropped during null handling",
                "affected_fields_count": columns_dropped,
                "recommendation": "Review dropped columns to ensure no critical data loss. Consider alternative imputation strategies."
            })
        
        # Alert 4: Data retention alert
        row_retention_pct = cleaning_score['metrics'].get('row_retention_percentage', 100)
        if row_retention_pct < 90:
            severity = "critical" if row_retention_pct < 70 else "high"
            alerts.append({
                "alert_id": "alert_nulls_data_loss",
                "severity": severity,
                "category": "data_retention",
                "message": f"Data retention: {row_retention_pct:.1f}% rows retained ({len(original_df) - len(df_cleaned)} rows lost)",
                "affected_fields_count": len(original_df) - len(df_cleaned),
                "recommendation": "Review null handling strategy to minimize data loss. Consider alternative imputation methods or adjust thresholds."
            })
        
        # Alert 5: Null pattern consistency alert
        rows_with_multiple_nulls = sum(1 for _, row in original_df.iterrows() if row.isnull().sum() > len(original_df.columns) * 0.3)
        if rows_with_multiple_nulls > len(original_df) * 0.1:
            alerts.append({
                "alert_id": "alert_nulls_pattern_clustering",
                "severity": "medium",
                "category": "data_quality",
                "message": f"Null clustering detected: {rows_with_multiple_nulls} rows ({(rows_with_multiple_nulls/len(original_df)*100):.1f}%) have >30% null values",
                "affected_fields_count": rows_with_multiple_nulls,
                "recommendation": "Investigate systematic data collection issues. Rows with clustered nulls may indicate process failures."
            })
        
        # Alert 6: Imputation effectiveness alert
        null_reduction_pct = cleaning_score['metrics'].get('null_reduction_rate', 0)
        if null_reduction_pct < 80:
            alerts.append({
                "alert_id": "alert_nulls_imputation_effectiveness",
                "severity": "medium",
                "category": "effectiveness",
                "message": f"Imputation effectiveness: {null_reduction_pct:.1f}% null reduction achieved (target: 80%+)",
                "affected_fields_count": len(imputation_log),
                "recommendation": "Review and optimize imputation strategies. Consider using advanced methods like KNN or domain-specific logic."
            })
        
        # Alert 7: Quality score alert
        if cleaning_score["overall_score"] < good_threshold:
            severity = "critical" if cleaning_score["overall_score"] < 50 else "high" if cleaning_score["overall_score"] < good_threshold else "medium"
            alerts.append({
                "alert_id": "alert_nulls_quality",
                "severity": severity,
                "category": "quality_score",
                "message": f"Null handling quality score: {cleaning_score['overall_score']:.1f}/100 ({quality_status})",
                "affected_fields_count": len(cols_with_nulls),
                "recommendation": "Optimize null handling strategy and imputation methods for better results. Review per-column strategies."
            })
        
        # Alert 8: Multiple columns requiring attention
        columns_needing_attention = [col for col, data in null_analysis.get('null_summary', {}).items() 
                                     if data.get('null_percentage', 0) > 20]
        if len(columns_needing_attention) > 5:
            alerts.append({
                "alert_id": "alert_nulls_widespread_issues",
                "severity": "high",
                "category": "data_quality",
                "message": f"Widespread null issues: {len(columns_needing_attention)} columns have >20% null values",
                "affected_fields_count": len(columns_needing_attention),
                "recommendation": "Systematic data quality issues detected. Review entire data collection and validation pipeline."
            })

        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Convert null issues to standardized format (row-level nulls)
        for null_issue in null_issues[:100]:
            issues.append({
                "issue_id": f"issue_nulls_{null_issue.get('row_index', 0)}_{null_issue.get('column', 'unknown')}",
                "agent_id": "null-handler",
                "field_name": null_issue.get('column', 'N/A'),
                "issue_type": null_issue.get('issue_type', 'null_value'),
                "severity": null_issue.get('severity', 'warning'),
                "message": null_issue.get('description', 'Null value detected')
            })
        
        # Add column-level issues for high null columns
        for col in high_null_cols[:20]:
            null_pct = null_analysis.get('null_summary', {}).get(col, {}).get('null_percentage', 0)
            issues.append({
                "issue_id": f"issue_nulls_column_high_{col}",
                "agent_id": "null-handler",
                "field_name": col,
                "issue_type": "high_null_column",
                "severity": "high",
                "message": f"Column '{col}' has {null_pct:.1f}% null values (exceeds 50% threshold)"
            })
        
        # Add imputation issues for columns where imputation may have failed
        imputation_failures = [entry for entry in imputation_log if 'failed' in entry.lower() or 'error' in entry.lower()]
        for i, failure in enumerate(imputation_failures[:10]):
            issues.append({
                "issue_id": f"issue_nulls_imputation_failure_{i}",
                "agent_id": "null-handler",
                "field_name": "multiple",
                "issue_type": "imputation_failure",
                "severity": "high",
                "message": f"Imputation issue: {failure}"
            })
        
        # Add data loss issues if significant rows were dropped
        if len(original_df) - len(df_cleaned) > len(original_df) * 0.1:
            issues.append({
                "issue_id": "issue_nulls_significant_data_loss",
                "agent_id": "null-handler",
                "field_name": "dataset",
                "issue_type": "data_retention",
                "severity": "critical",
                "message": f"Significant data loss: {len(original_df) - len(df_cleaned)} rows ({((len(original_df) - len(df_cleaned))/len(original_df)*100):.1f}%) removed due to null handling"
            })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        agent_recommendations = []
        
        # Calculate column categories
        high_null_cols = [col for col, data in null_analysis.get('null_summary', {}).items() 
                         if data.get('null_percentage', 0) > 50]
        medium_null_cols = [col for col, data in null_analysis.get('null_summary', {}).items() 
                           if 20 < data.get('null_percentage', 0) <= 50]
        low_null_cols = [col for col, data in null_analysis.get('null_summary', {}).items() 
                        if 0 < data.get('null_percentage', 0) <= 20]
        
        # Recommendation 1: Drop high-null columns
        if high_null_cols:
            agent_recommendations.append({
                "recommendation_id": "rec_nulls_drop_columns",
                "agent_id": "null-handler",
                "field_name": ", ".join(high_null_cols[:3]) + ("..." if len(high_null_cols) > 3 else ""),
                "priority": "high",
                "recommendation": f"Consider dropping {len(high_null_cols)} column(s) with >50% null values to improve data quality: {', '.join(high_null_cols[:5])}",
                "timeline": "1 week"
            })
        
        # Recommendation 2: Advanced imputation for medium-null columns
        if medium_null_cols:
            agent_recommendations.append({
                "recommendation_id": "rec_nulls_advanced_imputation",
                "agent_id": "null-handler",
                "field_name": ", ".join(medium_null_cols[:3]) + ("..." if len(medium_null_cols) > 3 else ""),
                "priority": "medium",
                "recommendation": f"Apply KNN or advanced imputation to {len(medium_null_cols)} column(s) with 20-50% nulls to preserve data while reducing missingness",
                "timeline": "2 weeks"
            })
        
        # Recommendation 3: Imputation strategy review
        agent_recommendations.append({
            "recommendation_id": "rec_nulls_strategy_review",
            "agent_id": "null-handler",
            "field_name": "all",
            "priority": "medium",
            "recommendation": f"Review and optimize imputation strategies for {len(imputation_log)} columns based on data distribution and business requirements",
            "timeline": "2 weeks"
        })
        
        # Recommendation 4: Data source improvement (if high null rate)
        null_pct = (null_analysis['total_nulls_detected'] / (len(original_df) * len(original_df.columns)) * 100) if len(original_df) * len(original_df.columns) > 0 else 0
        if null_pct > 20:
            agent_recommendations.append({
                "recommendation_id": "rec_nulls_source_quality",
                "agent_id": "null-handler",
                "field_name": "all",
                "priority": "high",
                "recommendation": f"Improve data collection completeness at source ({null_pct:.1f}% null rate). Address root causes in extraction, transformation, or entry processes.",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 5: Field-specific strategies (top 3 critical columns)
        for rec in null_analysis.get('recommendations', [])[:3]:
            priority_map = {"high": "high", "medium": "medium", "low": "low"}
            timeline_map = {"high": "1 week", "medium": "2 weeks", "low": "3 weeks"}
            priority = priority_map.get(rec.get('priority', 'medium'), 'medium')
            
            agent_recommendations.append({
                "recommendation_id": f"rec_nulls_{rec.get('column', 'unknown').replace(' ', '_')}",
                "agent_id": "null-handler",
                "field_name": rec.get('column', 'N/A'),
                "priority": priority,
                "recommendation": f"{rec.get('action', 'Review').replace('_', ' ').title()}: {rec.get('reason', 'Optimize null handling')}",
                "timeline": timeline_map.get(priority, "2 weeks")
            })
        
        # Recommendation 6: Validation rules implementation
        agent_recommendations.append({
            "recommendation_id": "rec_nulls_validation",
            "agent_id": "null-handler",
            "field_name": "all",
            "priority": "medium",
            "recommendation": "Implement validation rules to prevent null values in critical fields at data entry. Define required fields and enforce completeness checks.",
            "timeline": "2-3 weeks"
        })
        
        # Recommendation 7: Monitoring setup
        if len(cols_with_nulls) > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_nulls_monitoring",
                "agent_id": "null-handler",
                "field_name": "all",
                "priority": "low",
                "recommendation": f"Establish null rate monitoring for {len(cols_with_nulls)} affected column(s). Set up alerting when null percentages exceed thresholds.",
                "timeline": "3 weeks"
            })
        
        # Recommendation 8: Documentation of null patterns
        agent_recommendations.append({
            "recommendation_id": "rec_nulls_documentation",
            "agent_id": "null-handler",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Document null patterns, acceptable null rates per field, and business rules for handling missing data to ensure consistency.",
            "timeline": "3 weeks"
        })
        
        # Recommendation 9: Imputation method comparison (if low effectiveness)
        if cleaning_score['metrics'].get('null_reduction_rate', 100) < 80:
            agent_recommendations.append({
                "recommendation_id": "rec_nulls_method_comparison",
                "agent_id": "null-handler",
                "field_name": "all",
                "priority": "high",
                "recommendation": f"Current null reduction: {cleaning_score['metrics'].get('null_reduction_rate', 0):.1f}%. Test alternative imputation methods (KNN, MICE, regression) to improve effectiveness.",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 10: Data quality framework (if widespread issues)
        columns_needing_attention = [col for col, data in null_analysis.get('null_summary', {}).items() 
                                     if data.get('null_percentage', 0) > 20]
        if len(columns_needing_attention) > 5:
            agent_recommendations.append({
                "recommendation_id": "rec_nulls_quality_framework",
                "agent_id": "null-handler",
                "field_name": "all",
                "priority": "critical",
                "recommendation": f"Widespread null issues detected in {len(columns_needing_attention)} columns. Implement comprehensive data quality framework with upstream validation and completeness monitoring.",
                "timeline": "immediate"
            })


        return {
            "status": "success",
            "agent_id": "null-handler",
            "agent_name": "Null Handler",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_processed": len(df_cleaned),
                "nulls_handled": null_analysis['total_nulls_detected'],
                "original_nulls": null_analysis['total_nulls_detected'],
                "remaining_nulls": int(df_cleaned.isnull().sum().sum()),
                "total_issues": len(null_issues)
            },
            "data": null_handling_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
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
            "agent_id": "null-handler",
            "agent_name": "Null Handler",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _analyze_null_patterns(df: pd.DataFrame) -> Dict[str, Any]:
    """Analyze null patterns in the dataset."""
    null_analysis = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "columns_with_nulls": [],
        "total_nulls_detected": 0,
        "null_summary": {},
        "recommendations": []
    }
    
    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        null_percentage = float((null_count / len(df) * 100) if len(df) > 0 else 0)
        
        null_analysis["total_nulls_detected"] += null_count
        
        if null_count > 0:
            null_analysis["columns_with_nulls"].append(str(col))
            null_analysis["null_summary"][str(col)] = {
                "null_count": null_count,
                "null_percentage": round(null_percentage, 2),
                "data_type": str(df[col].dtype),
                "non_null_count": int(df[col].count()),
                "suggested_strategy": _suggest_imputation_strategy(df[col], null_percentage)
            }
            
            # Generate recommendations
            if null_percentage > 70:
                null_analysis["recommendations"].append({
                    "column": str(col),
                    "action": "consider_dropping",
                    "reason": f"Column has {null_percentage:.1f}% missing values",
                    "priority": "high"
                })
            elif null_percentage > 30:
                null_analysis["recommendations"].append({
                    "column": str(col),
                    "action": "advanced_imputation",
                    "reason": f"Column has {null_percentage:.1f}% missing values",
                    "priority": "medium"
                })
            else:
                null_analysis["recommendations"].append({
                    "column": str(col),
                    "action": "simple_imputation",
                    "reason": f"Column has {null_percentage:.1f}% missing values",
                    "priority": "low"
                })
    
    return null_analysis


def _suggest_imputation_strategy(series: pd.Series, null_percentage: float) -> str:
    """Suggest the best imputation strategy for a column."""
    if null_percentage > 70:
        return "drop_column"
    elif null_percentage > 50:
        return "knn_imputation"
    elif pd.api.types.is_numeric_dtype(series):
        non_null_data = series.dropna()
        if len(non_null_data) > 0:
            skewness = abs(non_null_data.skew()) if hasattr(non_null_data, 'skew') else 0
            return "median" if skewness > 1 else "mean"
        return "mean"
    elif pd.api.types.is_categorical_dtype(series) or series.dtype == 'object':
        return "mode"
    elif pd.api.types.is_datetime64_any_dtype(series):
        return "forward_fill"
    else:
        return "mode"


def _apply_null_handling(
    df: pd.DataFrame,
    global_strategy: str,
    column_strategies: Dict[str, str],
    fill_values: Dict[str, Any],
    knn_neighbors: int
) -> tuple:
    """Apply null handling strategies to the dataframe."""
    df_cleaned = df.copy()
    imputation_log = []
    
    # Apply global strategy
    if global_strategy == 'drop_rows':
        initial_rows = len(df_cleaned)
        df_cleaned = df_cleaned.dropna()
        rows_dropped = initial_rows - len(df_cleaned)
        imputation_log.append(f"Dropped {rows_dropped} rows with any null values")
    
    # Apply column-specific strategies
    for col, strategy in column_strategies.items():
        if col not in df_cleaned.columns:
            continue
        
        null_count_before = int(df_cleaned[col].isnull().sum())
        if null_count_before == 0:
            continue
        
        try:
            if strategy == 'drop_column':
                df_cleaned = df_cleaned.drop(columns=[col])
                imputation_log.append(f"Dropped column '{col}' (had {null_count_before} nulls)")
            
            elif strategy == 'mean' and pd.api.types.is_numeric_dtype(df_cleaned[col]):
                mean_val = float(df_cleaned[col].mean())
                df_cleaned[col] = df_cleaned[col].fillna(mean_val)
                imputation_log.append(f"Filled {null_count_before} nulls in '{col}' with mean ({mean_val:.2f})")
            
            elif strategy == 'median' and pd.api.types.is_numeric_dtype(df_cleaned[col]):
                median_val = float(df_cleaned[col].median())
                df_cleaned[col] = df_cleaned[col].fillna(median_val)
                imputation_log.append(f"Filled {null_count_before} nulls in '{col}' with median ({median_val:.2f})")
            
            elif strategy == 'mode':
                mode_val = df_cleaned[col].mode()
                if len(mode_val) > 0:
                    df_cleaned[col] = df_cleaned[col].fillna(mode_val.iloc[0])
                    imputation_log.append(f"Filled {null_count_before} nulls in '{col}' with mode ({mode_val.iloc[0]})")
            
            elif strategy == 'forward_fill':
                df_cleaned[col] = df_cleaned[col].fillna(method='ffill')
                null_count_after = int(df_cleaned[col].isnull().sum())
                filled_count = null_count_before - null_count_after
                imputation_log.append(f"Forward filled {filled_count} nulls in '{col}'")
            
            elif strategy == 'backward_fill':
                df_cleaned[col] = df_cleaned[col].fillna(method='bfill')
                null_count_after = int(df_cleaned[col].isnull().sum())
                filled_count = null_count_before - null_count_after
                imputation_log.append(f"Backward filled {filled_count} nulls in '{col}'")
            
            elif strategy == 'constant' and col in fill_values:
                fill_value = fill_values[col]
                df_cleaned[col] = df_cleaned[col].fillna(fill_value)
                imputation_log.append(f"Filled {null_count_before} nulls in '{col}' with constant ({fill_value})")
            
            elif strategy == 'knn_imputation':
                df_cleaned = _apply_knn_imputation(df_cleaned, [col], knn_neighbors)
                null_count_after = int(df_cleaned[col].isnull().sum())
                filled_count = null_count_before - null_count_after
                imputation_log.append(f"KNN imputed {filled_count} nulls in '{col}'")
        
        except Exception as e:
            imputation_log.append(f"Error applying {strategy} to '{col}': {str(e)}")
    
    return df_cleaned, imputation_log


def _apply_knn_imputation(df: pd.DataFrame, columns: list, n_neighbors: int = 5) -> pd.DataFrame:
    """Apply KNN imputation to numeric columns."""
    df_result = df.copy()
    
    if not HAS_SKLEARN:
        # Fallback to median imputation if sklearn not available
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        for col in columns:
            if col in numeric_cols and df_result[col].isnull().sum() > 0:
                df_result[col] = df_result[col].fillna(df_result[col].median())
        return df_result
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    target_cols = [col for col in columns if col in numeric_cols]
    
    if not target_cols:
        return df_result
    
    try:
        imputer = KNNImputer(n_neighbors=n_neighbors)
        df_numeric = df[numeric_cols]
        imputed_data = imputer.fit_transform(df_numeric)
        
        for i, col in enumerate(numeric_cols):
            if col in target_cols:
                df_result[col] = imputed_data[:, i]
    
    except Exception as e:
        # Fallback to median imputation if KNN fails
        for col in target_cols:
            if pd.api.types.is_numeric_dtype(df_result[col]):
                df_result[col] = df_result[col].fillna(df_result[col].median())
    
    return df_result


def _calculate_cleaning_score(
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    null_analysis: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate cleaning effectiveness score."""
    original_nulls = null_analysis["total_nulls_detected"]
    remaining_nulls = int(cleaned_df.isnull().sum().sum())
    nulls_handled = original_nulls - remaining_nulls
    
    # Calculate metrics
    null_reduction_rate = ((original_nulls - remaining_nulls) / original_nulls * 100) if original_nulls > 0 else 100
    data_retention_rate = (len(cleaned_df) / len(original_df) * 100) if len(original_df) > 0 else 0
    column_retention_rate = (len(cleaned_df.columns) / len(original_df.columns) * 100) if len(original_df.columns) > 0 else 0
    
    # Calculate weighted score
    null_weight = config.get('null_reduction_weight', 0.5)
    data_weight = config.get('data_retention_weight', 0.3)
    column_weight = config.get('column_retention_weight', 0.2)
    
    overall_score = (
        null_reduction_rate * null_weight +
        data_retention_rate * data_weight +
        column_retention_rate * column_weight
    )
    
    return {
        "overall_score": round(overall_score, 1),
        "metrics": {
            "null_reduction_rate": round(null_reduction_rate, 1),
            "data_retention_rate": round(data_retention_rate, 1),
            "column_retention_rate": round(column_retention_rate, 1),
            "original_nulls": original_nulls,
            "nulls_handled": nulls_handled,
            "remaining_nulls": remaining_nulls,
            "original_rows": len(original_df),
            "cleaned_rows": len(cleaned_df),
            "original_columns": len(original_df.columns),
            "cleaned_columns": len(cleaned_df.columns)
        }
    }


def _identify_null_issues(original_df: pd.DataFrame, cleaned_df: pd.DataFrame) -> list:
    """Identify row-level null issues."""
    issues = []
    
    for idx, row in original_df.iterrows():
        null_cols = row[row.isnull()].index.tolist()
        if null_cols:
            if len(issues) >= 100:
                break
            
            for col in null_cols:
                issues.append({
                    "row_index": int(idx),
                    "column": str(col),
                    "issue_type": "null_value",
                    "description": f"Null value found in column '{col}'",
                    "severity": "warning"
                })
    
    return issues


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
