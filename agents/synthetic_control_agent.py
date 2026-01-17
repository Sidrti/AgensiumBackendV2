"""
Synthetic Control Agent

Measures campaign impact without randomized control by constructing a
statistically similar synthetic control population from a baseline dataset.

Input: Two CSV files (primary = exposed/treatment group, baseline = non-exposed universe)
Output: Synthetic control analysis, incremental lift measurement, match confidence,
        alerts/issues/recommendations following Agensium agent response standard.
"""

import io
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import polars as pl

from .agent_utils import normalize_column_names, validate_required_parameters


def _convert_numpy_types(obj: Any) -> Any:
    """Convert numpy scalars/arrays into JSON-serializable Python types."""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def _parse_iso_date(value: Any) -> Optional[date]:
    """Parse ISO date string to date object."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s).date()
        except Exception:
            return None
    return None


def _resolve_column(requested: Optional[str], available: List[str]) -> Optional[str]:
    """Resolve column name with case-insensitive matching."""
    if not requested:
        return None
    if requested in available:
        return requested
    normalized = normalize_column_names([requested], available, case_sensitive=False)
    return normalized[0] if normalized else None


def _safe_int(value: Any, default: int, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    """Safely convert value to int with bounds checking."""
    try:
        if value is None:
            return default
        v = int(value)
    except Exception:
        return default
    if min_value is not None:
        v = max(min_value, v)
    if max_value is not None:
        v = min(max_value, v)
    return v


def _safe_float(value: Any, default: float, min_value: Optional[float] = None, max_value: Optional[float] = None) -> float:
    """Safely convert value to float with bounds checking."""
    try:
        if value is None:
            return default
        v = float(value)
        if np.isnan(v) or np.isinf(v):
            return default
    except Exception:
        return default
    if min_value is not None:
        v = max(min_value, v)
    if max_value is not None:
        v = min(max_value, v)
    return v


def _cap_list(items: List[Dict[str, Any]], limit: int = 1000) -> List[Dict[str, Any]]:
    """Cap list to specified limit."""
    return items[:limit] if len(items) > limit else items


def _aggregate_customer_features(
    df: pl.DataFrame,
    customer_col: str,
    date_col: str,
    value_col: str,
    start_date: date,
    end_date: date
) -> pl.DataFrame:
    """
    Aggregate transaction data to customer-level features for a given period.
    
    Returns: DataFrame with customer_id, total_value, transaction_count, avg_value, recency_days
    """
    filtered = df.filter(
        (pl.col("transaction_date") >= pl.lit(start_date)) &
        (pl.col("transaction_date") <= pl.lit(end_date))
    )
    
    agg = filtered.group_by("customer_id").agg([
        pl.sum("value").alias("total_value"),
        pl.count().alias("transaction_count"),
        pl.mean("value").alias("avg_value"),
        pl.max("transaction_date").alias("last_transaction_date"),
    ])
    
    # Calculate recency from end_date
    agg = agg.with_columns([
        (pl.lit(end_date).cast(pl.Date) - pl.col("last_transaction_date")).dt.total_days().cast(pl.Float64).alias("recency_days"),
    ])
    
    return agg


def _match_synthetic_control(
    treatment_features: pl.DataFrame,
    control_pool_features: pl.DataFrame,
    match_ratio: int = 1
) -> Tuple[pl.DataFrame, Dict[str, Any]]:
    """
    Match treatment customers to control customers based on pre-period features.
    Uses nearest neighbor matching on normalized features.
    
    Returns: (matched control DataFrame, matching diagnostics)
    """
    # Features to match on
    feature_cols = ["total_value", "transaction_count", "avg_value"]
    
    # Convert to numpy for matching
    treatment_array = treatment_features.select(feature_cols).fill_null(0).to_numpy()
    control_array = control_pool_features.select(feature_cols).fill_null(0).to_numpy()
    
    if treatment_array.shape[0] == 0 or control_array.shape[0] == 0:
        return pl.DataFrame(), {"error": "Empty features for matching"}
    
    # Normalize features (z-score)
    combined = np.vstack([treatment_array, control_array])
    means = np.nanmean(combined, axis=0)
    stds = np.nanstd(combined, axis=0)
    stds = np.where(stds < 1e-10, 1.0, stds)  # Avoid division by zero
    
    treatment_normalized = (treatment_array - means) / stds
    control_normalized = (control_array - means) / stds
    
    # Find nearest neighbors for each treatment unit
    matched_indices = []
    distances = []
    used_control_indices = set()
    
    for i, t_row in enumerate(treatment_normalized):
        # Calculate Euclidean distances to all control units
        dists = np.sqrt(np.sum((control_normalized - t_row) ** 2, axis=1))
        
        # Sort by distance and find best available match
        sorted_indices = np.argsort(dists)
        
        matches_found = 0
        for j in sorted_indices:
            if matches_found >= match_ratio:
                break
            if j not in used_control_indices:
                matched_indices.append(int(j))
                distances.append(float(dists[j]))
                used_control_indices.add(j)
                matches_found += 1
    
    # Extract matched control customers
    if not matched_indices:
        return pl.DataFrame(), {"error": "No matches found"}
    
    matched_control = control_pool_features[matched_indices]
    
    # Calculate matching diagnostics
    avg_distance = np.mean(distances) if distances else 0.0
    max_distance = np.max(distances) if distances else 0.0
    
    # Match quality score (inverse of normalized distance)
    match_confidence = max(0.0, min(100.0, 100.0 * (1.0 - avg_distance / 3.0)))  # Scale: 3.0 is very poor
    
    diagnostics = {
        "treatment_count": treatment_features.height,
        "control_pool_size": control_pool_features.height,
        "matched_control_count": len(matched_indices),
        "avg_match_distance": round(avg_distance, 4),
        "max_match_distance": round(max_distance, 4),
        "match_confidence_score": round(match_confidence, 2),
        "feature_means": {col: round(m, 4) for col, m in zip(feature_cols, means)},
        "feature_stds": {col: round(s, 4) for col, s in zip(feature_cols, stds)},
    }
    
    return matched_control, diagnostics


def _calculate_lift(
    treatment_features_pre: pl.DataFrame,
    treatment_features_post: pl.DataFrame,
    control_features_pre: pl.DataFrame,
    control_features_post: pl.DataFrame,
) -> Dict[str, Any]:
    """
    Calculate incremental lift using difference-in-differences approach.
    
    Lift = (Treatment_Post - Treatment_Pre) - (Control_Post - Control_Pre)
    """
    # Aggregate totals
    treatment_pre_total = treatment_features_pre.select(pl.sum("total_value")).item() or 0.0
    treatment_post_total = treatment_features_post.select(pl.sum("total_value")).item() or 0.0
    control_pre_total = control_features_pre.select(pl.sum("total_value")).item() or 0.0
    control_post_total = control_features_post.select(pl.sum("total_value")).item() or 0.0
    
    treatment_pre_avg = treatment_features_pre.select(pl.mean("total_value")).item() or 0.0
    treatment_post_avg = treatment_features_post.select(pl.mean("total_value")).item() or 0.0
    control_pre_avg = control_features_pre.select(pl.mean("total_value")).item() or 0.0
    control_post_avg = control_features_post.select(pl.mean("total_value")).item() or 0.0
    
    # Difference-in-differences (per customer average)
    treatment_change_avg = treatment_post_avg - treatment_pre_avg
    control_change_avg = control_post_avg - control_pre_avg
    incremental_lift_avg = treatment_change_avg - control_change_avg
    
    # Total incremental lift
    treatment_customers = max(treatment_features_pre.height, treatment_features_post.height)
    total_incremental_lift = incremental_lift_avg * treatment_customers
    
    # Percentage lift
    if control_pre_avg > 0:
        pct_lift = (incremental_lift_avg / control_pre_avg) * 100
    else:
        pct_lift = 0.0
    
    # Counterfactual: what treatment would have done without intervention
    counterfactual_treatment_post = treatment_pre_avg + control_change_avg
    
    return {
        "treatment": {
            "pre_period_total": round(float(treatment_pre_total), 2),
            "post_period_total": round(float(treatment_post_total), 2),
            "pre_period_avg": round(float(treatment_pre_avg), 2),
            "post_period_avg": round(float(treatment_post_avg), 2),
            "change_avg": round(float(treatment_change_avg), 2),
            "customer_count": treatment_customers,
        },
        "control": {
            "pre_period_total": round(float(control_pre_total), 2),
            "post_period_total": round(float(control_post_total), 2),
            "pre_period_avg": round(float(control_pre_avg), 2),
            "post_period_avg": round(float(control_post_avg), 2),
            "change_avg": round(float(control_change_avg), 2),
            "customer_count": control_features_pre.height,
        },
        "lift": {
            "incremental_lift_per_customer": round(float(incremental_lift_avg), 2),
            "total_incremental_lift": round(float(total_incremental_lift), 2),
            "percentage_lift": round(float(pct_lift), 2),
            "counterfactual_post_avg": round(float(counterfactual_treatment_post), 2),
        }
    }


def _generate_time_series(
    df: pl.DataFrame,
    start_date: date,
    end_date: date,
    group_name: str
) -> List[Dict[str, Any]]:
    """Generate daily time series for visualization."""
    filtered = df.filter(
        (pl.col("transaction_date") >= pl.lit(start_date)) &
        (pl.col("transaction_date") <= pl.lit(end_date))
    )
    
    daily = filtered.group_by("transaction_date").agg([
        pl.sum("value").alias("daily_value"),
        pl.n_unique("customer_id").alias("active_customers"),
        pl.count().alias("transaction_count"),
    ]).sort("transaction_date")
    
    time_series = []
    for row in daily.iter_rows(named=True):
        time_series.append({
            "date": str(row["transaction_date"]),
            "group": group_name,
            "value": round(float(row["daily_value"] or 0), 2),
            "active_customers": int(row["active_customers"] or 0),
            "transactions": int(row["transaction_count"] or 0),
        })
    
    return time_series


def execute_synthetic_control_agent(
    file_contents: bytes,
    filename: str,
    baseline_contents: Optional[bytes] = None,
    baseline_filename: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute synthetic control analysis."""

    start_time = time.time()
    parameters = parameters or {}

    # ----------------------------
    # Parse parameters (aligned to analyze_my_data_tool.json)
    # ----------------------------
    customer_id_column = parameters.get("customer_id_column")
    transaction_date_column = parameters.get("transaction_date_column")
    value_column = parameters.get("value_column")
    
    pre_period_start_date = _parse_iso_date(parameters.get("pre_period_start_date"))
    pre_period_end_date = _parse_iso_date(parameters.get("pre_period_end_date"))
    treatment_start_date = _parse_iso_date(parameters.get("treatment_start_date"))
    treatment_end_date = _parse_iso_date(parameters.get("treatment_end_date"))
    
    excellent_threshold = _safe_int(parameters.get("excellent_threshold"), 90, 0, 100)
    good_threshold = _safe_int(parameters.get("good_threshold"), 75, 0, 100)

    agent_id = "synthetic-control-agent"
    agent_name = "Synthetic Control Agent"

    try:
        # ----------------------------
        # Input validation
        # ----------------------------
        if not filename.lower().endswith(".csv"):
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"Unsupported primary file format: {filename}. Only CSV is supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }
        
        if baseline_contents is None or baseline_filename is None:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "Synthetic control requires both primary (treatment) and baseline (control pool) files.",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }
        
        if not baseline_filename.lower().endswith(".csv"):
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"Unsupported baseline file format: {baseline_filename}. Only CSV is supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        required_error = validate_required_parameters(
            parameters,
            ["customer_id_column", "transaction_date_column", "value_column",
             "pre_period_start_date", "pre_period_end_date",
             "treatment_start_date", "treatment_end_date"],
        )
        if required_error:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": required_error,
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }
        
        # Validate date sequence
        if pre_period_start_date > pre_period_end_date:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "pre_period_start_date cannot be after pre_period_end_date",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }
        
        if treatment_start_date > treatment_end_date:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "treatment_start_date cannot be after treatment_end_date",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }
        
        if pre_period_end_date >= treatment_start_date:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "pre_period_end_date must be before treatment_start_date",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # ----------------------------
        # Load treatment (primary) CSV
        # ----------------------------
        try:
            df_treatment = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"Failed to parse primary CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        if df_treatment.height == 0 or df_treatment.width == 0:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "Primary file is empty or has no columns",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # ----------------------------
        # Load baseline (control pool) CSV
        # ----------------------------
        try:
            df_baseline = pl.read_csv(io.BytesIO(baseline_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"Failed to parse baseline CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        if df_baseline.height == 0 or df_baseline.width == 0:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "Baseline file is empty or has no columns",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # Resolve columns for treatment
        t_customer_col = _resolve_column(customer_id_column, df_treatment.columns)
        t_date_col = _resolve_column(transaction_date_column, df_treatment.columns)
        t_value_col = _resolve_column(value_column, df_treatment.columns)

        # Resolve columns for baseline
        b_customer_col = _resolve_column(customer_id_column, df_baseline.columns)
        b_date_col = _resolve_column(transaction_date_column, df_baseline.columns)
        b_value_col = _resolve_column(value_column, df_baseline.columns)

        missing_cols = []
        if t_customer_col is None:
            missing_cols.append(f"customer_id_column ({customer_id_column}) in primary file")
        if t_date_col is None:
            missing_cols.append(f"transaction_date_column ({transaction_date_column}) in primary file")
        if t_value_col is None:
            missing_cols.append(f"value_column ({value_column}) in primary file")
        if b_customer_col is None:
            missing_cols.append(f"customer_id_column ({customer_id_column}) in baseline file")
        if b_date_col is None:
            missing_cols.append(f"transaction_date_column ({transaction_date_column}) in baseline file")
        if b_value_col is None:
            missing_cols.append(f"value_column ({value_column}) in baseline file")

        if missing_cols:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"Column(s) not found: {', '.join(missing_cols)}",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # ----------------------------
        # Standardize treatment data
        # ----------------------------
        treatment_working = df_treatment.select([
            pl.col(t_customer_col).alias("customer_id"),
            pl.col(t_date_col).alias("transaction_date_raw"),
            pl.col(t_value_col).alias("value_raw"),
        ]).with_row_index("row_index")

        treatment_working = treatment_working.with_columns(
            pl.col("customer_id").cast(pl.Utf8, strict=False)
        )

        if treatment_working["transaction_date_raw"].dtype in (pl.Date, pl.Datetime):
            parsed_date = pl.col("transaction_date_raw").cast(pl.Date, strict=False)
        else:
            parsed_date = (
                pl.col("transaction_date_raw")
                .cast(pl.Utf8, strict=False)
                .str.strip_chars()
                .str.to_datetime(strict=False)
                .cast(pl.Date, strict=False)
            )

        parsed_value = pl.col("value_raw").cast(pl.Float64, strict=False)
        parsed_value = pl.when(parsed_value.is_finite()).then(parsed_value).otherwise(None)

        treatment_working = treatment_working.with_columns([
            parsed_date.alias("transaction_date"),
            parsed_value.alias("value"),
        ])

        # ----------------------------
        # Standardize baseline data
        # ----------------------------
        baseline_working = df_baseline.select([
            pl.col(b_customer_col).alias("customer_id"),
            pl.col(b_date_col).alias("transaction_date_raw"),
            pl.col(b_value_col).alias("value_raw"),
        ]).with_row_index("row_index")

        baseline_working = baseline_working.with_columns(
            pl.col("customer_id").cast(pl.Utf8, strict=False)
        )

        if baseline_working["transaction_date_raw"].dtype in (pl.Date, pl.Datetime):
            b_parsed_date = pl.col("transaction_date_raw").cast(pl.Date, strict=False)
        else:
            b_parsed_date = (
                pl.col("transaction_date_raw")
                .cast(pl.Utf8, strict=False)
                .str.strip_chars()
                .str.to_datetime(strict=False)
                .cast(pl.Date, strict=False)
            )

        b_parsed_value = pl.col("value_raw").cast(pl.Float64, strict=False)
        b_parsed_value = pl.when(b_parsed_value.is_finite()).then(b_parsed_value).otherwise(None)

        baseline_working = baseline_working.with_columns([
            b_parsed_date.alias("transaction_date"),
            b_parsed_value.alias("value"),
        ])

        # ----------------------------
        # Row-level issues
        # ----------------------------
        row_level_issues: List[Dict[str, Any]] = []

        # Treatment data issues
        bad_date_t = treatment_working.filter(pl.col("transaction_date").is_null() & pl.col("transaction_date_raw").is_not_null())
        for r in bad_date_t.select(["row_index", "transaction_date_raw"]).head(200).iter_rows(named=True):
            row_level_issues.append({
                "row_index": int(r["row_index"]),
                "column": t_date_col,
                "issue_type": "invalid_date_treatment",
                "severity": "high",
                "message": "Transaction date could not be parsed in treatment file",
                "value": str(r.get("transaction_date_raw")),
            })

        bad_value_t = treatment_working.filter(pl.col("value").is_null() & pl.col("value_raw").is_not_null())
        for r in bad_value_t.select(["row_index", "value_raw"]).head(200).iter_rows(named=True):
            row_level_issues.append({
                "row_index": int(r["row_index"]),
                "column": t_value_col,
                "issue_type": "invalid_value_treatment",
                "severity": "high",
                "message": "Value could not be parsed in treatment file",
                "value": str(r.get("value_raw")),
            })

        # Baseline data issues
        bad_date_b = baseline_working.filter(pl.col("transaction_date").is_null() & pl.col("transaction_date_raw").is_not_null())
        for r in bad_date_b.select(["row_index", "transaction_date_raw"]).head(200).iter_rows(named=True):
            row_level_issues.append({
                "row_index": int(r["row_index"]),
                "column": b_date_col,
                "issue_type": "invalid_date_baseline",
                "severity": "high",
                "message": "Transaction date could not be parsed in baseline file",
                "value": str(r.get("transaction_date_raw")),
            })

        # ----------------------------
        # Filter valid rows
        # ----------------------------
        treatment_valid = treatment_working.filter(
            pl.col("customer_id").is_not_null() & (pl.col("customer_id") != "") &
            pl.col("transaction_date").is_not_null() &
            pl.col("value").is_not_null()
        )

        baseline_valid = baseline_working.filter(
            pl.col("customer_id").is_not_null() & (pl.col("customer_id") != "") &
            pl.col("transaction_date").is_not_null() &
            pl.col("value").is_not_null()
        )

        treatment_total = treatment_working.height
        treatment_valid_count = treatment_valid.height
        baseline_total = baseline_working.height
        baseline_valid_count = baseline_valid.height

        if treatment_valid_count == 0:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "No valid rows in treatment file after parsing",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        if baseline_valid_count == 0:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "No valid rows in baseline file after parsing",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # ----------------------------
        # Aggregate features for pre-period
        # ----------------------------
        treatment_pre_features = _aggregate_customer_features(
            treatment_valid, "customer_id", "transaction_date", "value",
            pre_period_start_date, pre_period_end_date
        )

        baseline_pre_features = _aggregate_customer_features(
            baseline_valid, "customer_id", "transaction_date", "value",
            pre_period_start_date, pre_period_end_date
        )

        if treatment_pre_features.height == 0:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "No treatment customers found in pre-period",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        if baseline_pre_features.height == 0:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "No baseline customers found in pre-period",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # ----------------------------
        # Match synthetic control
        # ----------------------------
        matched_control_pre, match_diagnostics = _match_synthetic_control(
            treatment_pre_features,
            baseline_pre_features
        )

        if matched_control_pre.height == 0 or "error" in match_diagnostics:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": match_diagnostics.get("error", "Failed to match synthetic control"),
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # Get matched control customer IDs
        matched_customer_ids = matched_control_pre.select("customer_id").to_series().to_list()

        # ----------------------------
        # Aggregate features for treatment period
        # ----------------------------
        treatment_post_features = _aggregate_customer_features(
            treatment_valid, "customer_id", "transaction_date", "value",
            treatment_start_date, treatment_end_date
        )

        # Filter baseline to only matched customers for post-period
        baseline_matched = baseline_valid.filter(pl.col("customer_id").is_in(matched_customer_ids))
        control_post_features = _aggregate_customer_features(
            baseline_matched, "customer_id", "transaction_date", "value",
            treatment_start_date, treatment_end_date
        )

        # ----------------------------
        # Calculate lift
        # ----------------------------
        lift_analysis = _calculate_lift(
            treatment_pre_features,
            treatment_post_features,
            matched_control_pre,
            control_post_features
        )

        # ----------------------------
        # Generate time series for visualization
        # ----------------------------
        # Full period for time series
        full_start = pre_period_start_date
        full_end = treatment_end_date

        treatment_time_series = _generate_time_series(
            treatment_valid, full_start, full_end, "treatment"
        )
        control_time_series = _generate_time_series(
            baseline_matched, full_start, full_end, "synthetic_control"
        )

        # ----------------------------
        # Quality assessment
        # ----------------------------
        match_confidence = match_diagnostics.get("match_confidence_score", 50.0)
        
        if match_confidence >= excellent_threshold:
            quality_status = "excellent"
        elif match_confidence >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"

        # ----------------------------
        # Alerts
        # ----------------------------
        alerts: List[Dict[str, Any]] = []

        if match_confidence < 50:
            alerts.append({
                "alert_id": "alert_poor_match_quality",
                "severity": "critical",
                "category": "match_quality",
                "message": f"Match confidence ({match_confidence:.1f}%) is very low. Synthetic control may not be representative.",
                "affected_fields_count": 0,
                "recommendation": "Increase baseline pool size, improve feature overlap, or adjust matching criteria.",
            })
        elif match_confidence < 70:
            alerts.append({
                "alert_id": "alert_moderate_match_quality",
                "severity": "high",
                "category": "match_quality",
                "message": f"Match confidence ({match_confidence:.1f}%) is moderate. Results should be interpreted cautiously.",
                "affected_fields_count": 0,
                "recommendation": "Consider collecting more baseline data or using additional matching features.",
            })

        if treatment_pre_features.height < 50:
            alerts.append({
                "alert_id": "alert_small_treatment",
                "severity": "medium",
                "category": "data_volume",
                "message": f"Only {treatment_pre_features.height} treatment customers. Results may have high variance.",
                "affected_fields_count": 0,
                "recommendation": "Use a longer observation period or larger treatment group for more stable results.",
            })

        treatment_invalid_rate = ((treatment_total - treatment_valid_count) / treatment_total * 100) if treatment_total > 0 else 0
        if treatment_invalid_rate > 10:
            alerts.append({
                "alert_id": "alert_treatment_data_quality",
                "severity": "medium",
                "category": "data_quality",
                "message": f"{treatment_invalid_rate:.1f}% of treatment rows were invalid.",
                "affected_fields_count": 2,
                "recommendation": "Fix data quality issues in treatment file for more accurate analysis.",
            })

        # ----------------------------
        # Issues
        # ----------------------------
        issues: List[Dict[str, Any]] = []

        issues.append({
            "issue_id": "issue_synthetic_control_quality",
            "agent_id": agent_id,
            "field_name": "match_quality",
            "issue_type": "match_assessment",
            "severity": "low" if quality_status in ["excellent", "good"] else "medium",
            "message": f"Synthetic control match confidence: {match_confidence:.1f}/100 ({quality_status}).",
        })

        if baseline_pre_features.height < treatment_pre_features.height * 2:
            issues.append({
                "issue_id": "issue_small_control_pool",
                "agent_id": agent_id,
                "field_name": "baseline",
                "issue_type": "data_warning",
                "severity": "medium",
                "message": f"Control pool ({baseline_pre_features.height}) is less than 2x treatment size ({treatment_pre_features.height}). May limit match quality.",
            })

        # ----------------------------
        # Recommendations
        # ----------------------------
        recommendations: List[Dict[str, Any]] = []

        recommendations.append({
            "recommendation_id": "rec_validate_parallel_trends",
            "agent_id": agent_id,
            "field_name": "methodology",
            "priority": "high",
            "recommendation": "Review pre-period time series to validate parallel trends assumption. Treatment and control should move together before intervention.",
            "timeline": "immediate",
        })

        recommendations.append({
            "recommendation_id": "rec_sensitivity_analysis",
            "agent_id": agent_id,
            "field_name": "robustness",
            "priority": "medium",
            "recommendation": "Run sensitivity analysis by varying the pre-period window and matching ratio to test result stability.",
            "timeline": "1-2 weeks",
        })

        if match_confidence < good_threshold:
            recommendations.append({
                "recommendation_id": "rec_improve_matching",
                "agent_id": agent_id,
                "field_name": "match_quality",
                "priority": "high",
                "recommendation": "Consider adding more features for matching (demographics, product categories) to improve control quality.",
                "timeline": "before final analysis",
            })

        recommendations.append({
            "recommendation_id": "rec_statistical_inference",
            "agent_id": agent_id,
            "field_name": "analysis",
            "priority": "low",
            "recommendation": "For formal inference, consider bootstrap confidence intervals or permutation tests on the lift estimate.",
            "timeline": "2-4 weeks",
        })

        # ----------------------------
        # Executive summary
        # ----------------------------
        incremental_lift = lift_analysis["lift"]["incremental_lift_per_customer"]
        pct_lift = lift_analysis["lift"]["percentage_lift"]
        total_lift = lift_analysis["lift"]["total_incremental_lift"]

        executive_summary = [
            {
                "summary_id": "exec_synthetic_lift",
                "title": "Incremental Lift/Customer",
                "value": f"${incremental_lift:,.2f}",
                "status": "excellent" if incremental_lift > 0 else "warning" if incremental_lift == 0 else "critical",
                "description": f"Average incremental value per treatment customer vs synthetic control.",
            },
            {
                "summary_id": "exec_synthetic_pct_lift",
                "title": "Percentage Lift",
                "value": f"{pct_lift:,.1f}%",
                "status": "excellent" if pct_lift >= 5 else "good" if pct_lift > 0 else "warning",
                "description": f"Relative lift compared to control baseline.",
            },
            {
                "summary_id": "exec_synthetic_total_lift",
                "title": "Total Incremental Value",
                "value": f"${total_lift:,.2f}",
                "status": "excellent" if total_lift > 0 else "warning",
                "description": f"Total campaign impact across all {treatment_pre_features.height} treatment customers.",
            },
            {
                "summary_id": "exec_synthetic_confidence",
                "title": "Match Confidence",
                "value": f"{match_confidence:.0f}%",
                "status": "excellent" if match_confidence >= excellent_threshold else "good" if match_confidence >= good_threshold else "warning",
                "description": f"Quality of synthetic control matching (higher is better).",
            },
            {
                "summary_id": "exec_synthetic_treatment_count",
                "title": "Treatment Customers",
                "value": f"{treatment_pre_features.height:,}",
                "status": "good" if treatment_pre_features.height >= 50 else "warning",
                "description": f"Number of customers in treatment group.",
            },
            {
                "summary_id": "exec_synthetic_control_count",
                "title": "Matched Controls",
                "value": f"{matched_control_pre.height:,}",
                "status": "good" if matched_control_pre.height >= treatment_pre_features.height else "warning",
                "description": f"Number of matched synthetic control customers.",
            },
        ]

        # ----------------------------
        # Issue summary
        # ----------------------------
        row_level_issues = _cap_list(row_level_issues, 1000)
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {},
            "affected_rows": len(set(i.get("row_index") for i in row_level_issues if i.get("row_index") is not None)),
            "affected_columns": sorted(list(set(i.get("column") for i in row_level_issues if i.get("column")))),
        }

        for issue in row_level_issues:
            t = issue.get("issue_type", "unknown")
            s = issue.get("severity", "info")
            issue_summary["by_type"][t] = issue_summary["by_type"].get(t, 0) + 1
            issue_summary["by_severity"][s] = issue_summary["by_severity"].get(s, 0) + 1

        # ----------------------------
        # Build data payload
        # ----------------------------
        data = {
            "analysis_configuration": {
                "columns_used": {
                    "customer_id_column": customer_id_column,
                    "transaction_date_column": transaction_date_column,
                    "value_column": value_column,
                },
                "periods": {
                    "pre_period": {
                        "start_date": pre_period_start_date.isoformat(),
                        "end_date": pre_period_end_date.isoformat(),
                        "days": (pre_period_end_date - pre_period_start_date).days + 1,
                    },
                    "treatment_period": {
                        "start_date": treatment_start_date.isoformat(),
                        "end_date": treatment_end_date.isoformat(),
                        "days": (treatment_end_date - treatment_start_date).days + 1,
                    },
                },
            },
            "data_summary": {
                "treatment_file": {
                    "filename": filename,
                    "total_rows": treatment_total,
                    "valid_rows": treatment_valid_count,
                    "unique_customers_pre": treatment_pre_features.height,
                    "unique_customers_post": treatment_post_features.height,
                },
                "baseline_file": {
                    "filename": baseline_filename,
                    "total_rows": baseline_total,
                    "valid_rows": baseline_valid_count,
                    "unique_customers_pre": baseline_pre_features.height,
                    "matched_customers": matched_control_pre.height,
                },
            },
            "matching_diagnostics": match_diagnostics,
            "lift_analysis": lift_analysis,
            "time_series": {
                "treatment": treatment_time_series[:365],  # Cap for response size
                "synthetic_control": control_time_series[:365],
            },
            "quality": {
                "match_confidence_score": match_confidence,
                "quality_status": quality_status,
            },
        }

        ai_analysis_text = "\n".join([
            "SYNTHETIC CONTROL ANALYSIS RESULTS:",
            f"- Pre-period: {pre_period_start_date} to {pre_period_end_date}",
            f"- Treatment period: {treatment_start_date} to {treatment_end_date}",
            f"- Treatment customers: {treatment_pre_features.height}",
            f"- Matched control customers: {matched_control_pre.height}",
            f"- Match confidence: {match_confidence:.1f}/100 ({quality_status})",
            f"- Incremental lift per customer: ${incremental_lift:,.2f}",
            f"- Percentage lift: {pct_lift:.1f}%",
            f"- Total incremental value: ${total_lift:,.2f}",
            f"- Treatment pre-period avg: ${lift_analysis['treatment']['pre_period_avg']:,.2f}",
            f"- Treatment post-period avg: ${lift_analysis['treatment']['post_period_avg']:,.2f}",
            f"- Control pre-period avg: ${lift_analysis['control']['pre_period_avg']:,.2f}",
            f"- Control post-period avg: ${lift_analysis['control']['post_period_avg']:,.2f}",
        ])

        return {
            "status": "success",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "treatment_customers": treatment_pre_features.height,
                "matched_control_customers": matched_control_pre.height,
                "match_confidence": round(match_confidence, 1),
                "incremental_lift_per_customer": round(incremental_lift, 2),
                "percentage_lift": round(pct_lift, 2),
                "total_incremental_lift": round(total_lift, 2),
            },
            "data": data,
            "alerts": alerts,
            "issues": issues,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary,
            "recommendations": recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text,
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }
