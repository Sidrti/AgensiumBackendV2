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
        
        # Build results
        null_handling_data = {
            "cleaning_score": cleaning_score,
            "quality_status": quality_status,
            "null_analysis": null_analysis,
            "imputation_log": imputation_log,
            "summary": f"Null handling completed. Quality: {quality_status}. Processed {len(original_df)} rows, handled {null_analysis['total_nulls_detected']} null values.",
            "row_level_issues": null_issues[:100]  # Limit to first 100
        }

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
            "data": null_handling_data
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
