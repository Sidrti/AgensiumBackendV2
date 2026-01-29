"""
Customer Segmentation Agent

Classifies customers into value-based or behavior-based segments using
either value quantiles or weighted RFM modeling.

Input: CSV file (primary)
Output: Segmentation summaries, per-customer segment assignments (sampled),
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


def _now_utc_date() -> date:
    return datetime.utcnow().date()


def _parse_iso_date(value: Any) -> Optional[date]:
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
            # ISO 8601 date
            return datetime.fromisoformat(s).date()
        except Exception:
            return None
    return None


def _resolve_column(requested: Optional[str], available: List[str]) -> Optional[str]:
    if not requested:
        return None
    # Try exact first
    if requested in available:
        return requested
    # Try normalized
    normalized = normalize_column_names([requested], available, case_sensitive=False)
    return normalized[0] if normalized else None


def _safe_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        v = float(value)
        if np.isnan(v) or np.isinf(v):
            return default
        return v
    except Exception:
        return default


def _cap_list(items: List[Dict[str, Any]], limit: int = 1000) -> List[Dict[str, Any]]:
    return items[:limit] if len(items) > limit else items


def _quantile_edges(values: np.ndarray, bins: int) -> np.ndarray:
    """Compute quantile edges for binning. Returns monotonic edges (excluding min/max padding)."""
    if bins <= 1:
        return np.array([], dtype=float)
    # percentiles excluding 0 and 100
    percentiles = [100 * i / bins for i in range(1, bins)]
    edges = np.nanpercentile(values, percentiles)
    # Ensure strictly increasing edges (ties possible). We'll de-duplicate safely.
    edges = np.unique(edges)
    return edges


def _bin_to_scores(
    values: pl.Series,
    *,
    bins: int,
    higher_is_better: bool,
    null_score: int = 1,
) -> pl.Series:
    """Bin numeric series into 1..bins scores using quantile edges."""
    if bins < 2:
        bins = 2

    arr = values.to_numpy()
    if arr.size == 0:
        return pl.Series(name=values.name, values=[])

    edges = _quantile_edges(arr.astype(float), bins)

    # np.digitize returns 0..len(edges)
    # With edges=[e1,e2,...], bin_idx increases with value.
    bin_idx = np.digitize(arr.astype(float), edges, right=True) + 1  # 1..(len(edges)+1)
    # If edges de-duped, effective bins may be < requested; clamp.
    bin_idx = np.clip(bin_idx, 1, bins)

    if not higher_is_better:
        # Lower values should map to higher scores.
        bin_idx = (bins + 1) - bin_idx

    # Handle NaN -> null_score
    nan_mask = np.isnan(arr.astype(float))
    if nan_mask.any():
        bin_idx = bin_idx.astype(int)
        bin_idx[nan_mask] = int(null_score)

    return pl.Series(values.name, bin_idx.astype(int))


def _segment_labels(segment_count: int, mode: str) -> Tuple[List[str], List[str]]:
    """Return (labels, descriptions) aligned with segment_id 1..segment_count."""
    segment_count = max(2, min(int(segment_count), 10))

    if segment_count == 5:
        if mode == "rfm":
            labels = ["Champions", "Loyal", "Potential", "At Risk", "Lost"]
            desc = [
                "High value, frequent, and very recent customers.",
                "Strong repeat customers with good value.",
                "Decent customers who could be nurtured to grow.",
                "Previously engaged customers showing signs of churn.",
                "Low engagement and low value customers.",
            ]
        else:
            labels = ["Top Value", "High Value", "Mid Value", "Low Value", "Lowest Value"]
            desc = [
                "Highest total value customers.",
                "Above-average total value customers.",
                "Average total value customers.",
                "Below-average total value customers.",
                "Lowest total value customers.",
            ]
        return labels, desc

    labels = [f"Segment {i}" for i in range(1, segment_count + 1)]
    if mode == "rfm":
        desc = [
            "Higher composite RFM score" if i <= max(1, segment_count // 3) else
            "Mid composite RFM score" if i <= max(2, (2 * segment_count) // 3) else
            "Lower composite RFM score"
            for i in range(1, segment_count + 1)
        ]
    else:
        desc = [
            "Higher total value" if i <= max(1, segment_count // 3) else
            "Mid total value" if i <= max(2, (2 * segment_count) // 3) else
            "Lower total value"
            for i in range(1, segment_count + 1)
        ]
    return labels, desc


def execute_customer_segmentation_agent(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute customer segmentation analysis."""

    start_time = time.time()
    parameters = parameters or {}

    # ----------------------------
    # Parse parameters (defaults aligned to analyze_my_data_tool.json)
    # ----------------------------
    mode = (parameters.get("mode") or "rfm").strip().lower()
    timeframe = (parameters.get("timeframe") or "last_12_months").strip().lower()

    custom_start_date = _parse_iso_date(parameters.get("custom_start_date"))
    custom_end_date = _parse_iso_date(parameters.get("custom_end_date"))

    metric = (parameters.get("metric") or "revenue").strip().lower()
    segment_count = _safe_int(parameters.get("segment_count"), 5)
    segment_count = max(2, min(segment_count, 10))

    customer_id_column = parameters.get("customer_id_column")
    transaction_date_column = parameters.get("transaction_date_column")
    value_column = parameters.get("value_column")

    rfm_recency_weight = _safe_int(parameters.get("rfm_recency_weight"), 33)
    rfm_frequency_weight = _safe_int(parameters.get("rfm_frequency_weight"), 33)
    rfm_monetary_weight = _safe_int(parameters.get("rfm_monetary_weight"), 34)
    rfm_bins = _safe_int(parameters.get("rfm_bins"), 5)
    rfm_bins = max(2, min(rfm_bins, 10))

    excellent_threshold = _safe_int(parameters.get("excellent_threshold"), 90)
    good_threshold = _safe_int(parameters.get("good_threshold"), 75)

    agent_id = "customer-segmentation-agent"
    agent_name = "Customer Segmentation Agent"

    try:
        # ----------------------------
        # Input validation
        # ----------------------------
        if not filename.lower().endswith(".csv"):
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"Unsupported file format: {filename}. Only CSV is supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        required_error = validate_required_parameters(
            parameters,
            ["customer_id_column", "transaction_date_column", "value_column"],
        )
        if required_error:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": required_error,
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        if mode not in {"value", "rfm"}:
            mode = "rfm"

        if timeframe not in {"ytd", "last_12_months", "custom"}:
            timeframe = "last_12_months"

        if timeframe == "custom":
            if not custom_start_date or not custom_end_date:
                return {
                    "status": "error",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "error": "custom_start_date and custom_end_date are required when timeframe=custom (YYYY-MM-DD)",
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                }
            if custom_start_date > custom_end_date:
                return {
                    "status": "error",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "error": "custom_start_date cannot be after custom_end_date",
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                }

        # ----------------------------
        # Load CSV
        # ----------------------------
        try:
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        if df.height == 0 or df.width == 0:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "File is empty or has no columns",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # Resolve columns (case-insensitive)
        customer_id_col = _resolve_column(customer_id_column, df.columns)
        txn_date_col = _resolve_column(transaction_date_column, df.columns)
        value_col = _resolve_column(value_column, df.columns)

        missing_cols = [
            c for c, resolved in [
                ("customer_id_column", customer_id_col),
                ("transaction_date_column", txn_date_col),
                ("value_column", value_col),
            ]
            if resolved is None
        ]
        if missing_cols:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"Selected column(s) not found in dataset: {', '.join(missing_cols)}",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # ----------------------------
        # Standardize required fields
        # ----------------------------
        working = df.select([
            pl.col(customer_id_col).alias("customer_id"),
            pl.col(txn_date_col).alias("transaction_date_raw"),
            pl.col(value_col).alias("value_raw"),
        ]).with_row_index("row_index")

        # Customer id -> string
        working = working.with_columns(
            pl.col("customer_id").cast(pl.Utf8, strict=False)
        )

        # Date parsing
        if working["transaction_date_raw"].dtype in (pl.Date, pl.Datetime):
            parsed_date = pl.col("transaction_date_raw").cast(pl.Date, strict=False)
        else:
            parsed_date = (
                pl.col("transaction_date_raw")
                .cast(pl.Utf8, strict=False)
                .str.strip_chars()
                .str.to_datetime(strict=False)
                .cast(pl.Date, strict=False)
            )

        # Value parsing
        parsed_value = pl.col("value_raw").cast(pl.Float64, strict=False)
        # Treat non-finite numeric values (inf/-inf/NaN) as invalid -> null.
        # This avoids quantile/aggregation instability while keeping strict=False behavior.
        parsed_value = pl.when(parsed_value.is_finite()).then(parsed_value).otherwise(None)

        working = working.with_columns([
            parsed_date.alias("transaction_date"),
            parsed_value.alias("value"),
        ])

        # ----------------------------
        # Row-level issues (pre-filter)
        # ----------------------------
        row_level_issues: List[Dict[str, Any]] = []

        null_id_rows = working.filter(pl.col("customer_id").is_null() | (pl.col("customer_id") == ""))
        for r in null_id_rows.select(["row_index", "customer_id"]).head(400).iter_rows(named=True):
            row_level_issues.append({
                "row_index": int(r["row_index"]),
                "column": customer_id_col,
                "issue_type": "missing_customer_id",
                "severity": "critical",
                "message": "Missing customer identifier",
                "value": r.get("customer_id"),
            })

        bad_date_rows = working.filter(pl.col("transaction_date").is_null() & pl.col("transaction_date_raw").is_not_null())
        for r in bad_date_rows.select(["row_index", "transaction_date_raw"]).head(400).iter_rows(named=True):
            row_level_issues.append({
                "row_index": int(r["row_index"]),
                "column": txn_date_col,
                "issue_type": "invalid_date",
                "severity": "high",
                "message": "Transaction date could not be parsed",
                "value": str(r.get("transaction_date_raw")),
            })

        bad_value_rows = working.filter(pl.col("value").is_null() & pl.col("value_raw").is_not_null())
        for r in bad_value_rows.select(["row_index", "value_raw"]).head(400).iter_rows(named=True):
            row_level_issues.append({
                "row_index": int(r["row_index"]),
                "column": value_col,
                "issue_type": "invalid_numeric",
                "severity": "high",
                "message": "Value could not be parsed as numeric",
                "value": str(r.get("value_raw")),
            })

        # Enforce cap at 1000 later

        # ----------------------------
        # Filter valid rows
        # ----------------------------
        valid = working.filter(
            pl.col("customer_id").is_not_null() & (pl.col("customer_id") != "") &
            pl.col("transaction_date").is_not_null() &
            pl.col("value").is_not_null()
        )

        total_rows = working.height
        valid_rows = valid.height
        invalid_rows = total_rows - valid_rows

        if valid_rows == 0:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "No valid rows after parsing required fields (customer_id, transaction_date, value)",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # Determine analysis end date from data
        end_dt = valid.select(pl.col("transaction_date").max()).item()
        if end_dt is None:
            end_dt = _now_utc_date()
        if isinstance(end_dt, datetime):
            end_dt = end_dt.date()

        if timeframe == "last_12_months":
            start_dt = end_dt - timedelta(days=365)
        elif timeframe == "ytd":
            start_dt = date(end_dt.year, 1, 1)
        else:  # custom
            start_dt = custom_start_date or (end_dt - timedelta(days=365))
            end_dt = custom_end_date or end_dt

        valid = valid.filter((pl.col("transaction_date") >= pl.lit(start_dt)) & (pl.col("transaction_date") <= pl.lit(end_dt)))

        # After timeframe filter
        filtered_rows = valid.height
        if filtered_rows == 0:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "No rows remain after applying timeframe filter",
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

        # ----------------------------
        # Aggregate to customer level
        # ----------------------------
        customers = (
            valid.group_by("customer_id")
            .agg([
                pl.count().alias("frequency"),
                pl.sum("value").alias("monetary"),
                pl.max("transaction_date").alias("last_purchase_date"),
                pl.min("transaction_date").alias("first_purchase_date"),
                pl.mean("value").alias("avg_order_value"),
            ])
        )

        # Recency in days (lower is better)
        customers = customers.with_columns([
            (pl.lit(end_dt).cast(pl.Date) - pl.col("last_purchase_date")).dt.total_days().cast(pl.Int32).alias("recency_days"),
            (pl.lit(end_dt).cast(pl.Date) - pl.col("first_purchase_date")).dt.total_days().cast(pl.Int32).alias("tenure_days"),
        ])

        customer_count = customers.height
        if customer_count < segment_count:
            # Still proceed, but warn and reduce segment_count to customer_count
            segment_count = max(2, min(segment_count, customer_count))

        # ----------------------------
        # Segmentation logic
        # ----------------------------
        segmentation_details: Dict[str, Any] = {
            "mode": mode,
            "timeframe": timeframe,
            "analysis_window": {
                "start_date": start_dt.isoformat(),
                "end_date": end_dt.isoformat(),
            },
            "columns_used": {
                "customer_id_column": customer_id_col,
                "transaction_date_column": txn_date_col,
                "value_column": value_col,
            },
            "metric": metric,
        }

        if mode == "value":
            score_series = customers.get_column("monetary")
            scores = _bin_to_scores(score_series, bins=segment_count, higher_is_better=True)
            customers = customers.with_columns([
                scores.alias("segment_bucket"),
            ])
            # segment_id = 1 is highest value
            customers = customers.with_columns([
                (segment_count + 1 - pl.col("segment_bucket")).cast(pl.Int32).alias("segment_id")
            ])
            segmentation_details["scoring"] = {
                "value_metric": "monetary",
                "segment_count": segment_count,
            }
        else:
            # Validate weights
            w_sum = max(0, rfm_recency_weight) + max(0, rfm_frequency_weight) + max(0, rfm_monetary_weight)
            if w_sum <= 0:
                rfm_recency_weight, rfm_frequency_weight, rfm_monetary_weight = 33, 33, 34
                w_sum = 100

            # Compute component scores 1..rfm_bins
            r_score = _bin_to_scores(customers.get_column("recency_days"), bins=rfm_bins, higher_is_better=False)
            f_score = _bin_to_scores(customers.get_column("frequency"), bins=rfm_bins, higher_is_better=True)
            m_score = _bin_to_scores(customers.get_column("monetary"), bins=rfm_bins, higher_is_better=True)

            customers = customers.with_columns([
                r_score.alias("r_score"),
                f_score.alias("f_score"),
                m_score.alias("m_score"),
            ])

            # Weighted score in 0..100
            weighted = (
                (pl.col("r_score") * max(0, rfm_recency_weight)) +
                (pl.col("f_score") * max(0, rfm_frequency_weight)) +
                (pl.col("m_score") * max(0, rfm_monetary_weight))
            ) / float(w_sum)

            # Normalize: component scores span [1, rfm_bins]
            customers = customers.with_columns([
                (((weighted - 1.0) / max(1.0, float(rfm_bins - 1))) * 100.0)
                .clip(0.0, 100.0)
                .alias("rfm_score")
            ])

            # Segment into segment_count buckets using rfm_score
            seg_bucket = _bin_to_scores(customers.get_column("rfm_score"), bins=segment_count, higher_is_better=True)
            # Note: Polars cannot reference a newly created column within the same with_columns call.
            customers = customers.with_columns([
                seg_bucket.alias("segment_bucket"),
            ])
            customers = customers.with_columns([
                (segment_count + 1 - pl.col("segment_bucket")).cast(pl.Int32).alias("segment_id"),
            ])

            segmentation_details["scoring"] = {
                "rfm_bins": rfm_bins,
                "weights": {
                    "recency": rfm_recency_weight,
                    "frequency": rfm_frequency_weight,
                    "monetary": rfm_monetary_weight,
                    "sum": w_sum,
                },
                "segment_count": segment_count,
            }

        # Attach labels
        labels, descriptions = _segment_labels(segment_count, mode)
        label_df = pl.DataFrame({
            "segment_id": list(range(1, segment_count + 1)),
            "segment_label": labels,
            "segment_description": descriptions,
        })
        customers = customers.join(label_df, on="segment_id", how="left")

        # ----------------------------
        # Segment summaries
        # ----------------------------
        total_value = customers.select(pl.sum("monetary")).item() or 0.0
        total_value = float(total_value)

        segment_summary = (
            customers.group_by(["segment_id", "segment_label", "segment_description"])
            .agg([
                pl.count().alias("customer_count"),
                pl.sum("monetary").alias("total_value"),
                pl.mean("monetary").alias("avg_value"),
                pl.mean("frequency").alias("avg_frequency"),
                pl.mean("recency_days").alias("avg_recency_days"),
            ])
            .with_columns([
                (pl.col("total_value") / max(total_value, 1e-9) * 100.0).alias("value_share_pct"),
            ])
            .sort("segment_id")
        )

        # Top customers sample
        sample_customers = (
            customers.sort(["segment_id", "monetary"], descending=[False, True])
            .select([
                "customer_id",
                "segment_id",
                "segment_label",
                "frequency",
                "monetary",
                "recency_days",
                "avg_order_value",
                "last_purchase_date",
            ])
            .head(500)
        )

        # ----------------------------
        # Quality / scoring status
        # ----------------------------
        invalid_rate = (invalid_rows / total_rows * 100.0) if total_rows > 0 else 0.0
        timeframe_retained_rate = (filtered_rows / max(valid_rows, 1) * 100.0) if valid_rows > 0 else 0.0

        quality_score = max(0.0, 100.0 - invalid_rate)
        if quality_score >= excellent_threshold:
            quality_status = "excellent"
        elif quality_score >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"

        # ----------------------------
        # Alerts, issues, recommendations
        # ----------------------------
        alerts: List[Dict[str, Any]] = []
        issues: List[Dict[str, Any]] = []
        recommendations: List[Dict[str, Any]] = []

        if invalid_rate > 10:
            alerts.append({
                "alert_id": "alert_segmentation_invalid_rows",
                "severity": "high" if invalid_rate <= 25 else "critical",
                "category": "data_quality",
                "message": f"{invalid_rate:.1f}% of rows were invalid for segmentation (missing/invalid ID, date, or value).",
                "affected_fields_count": 3,
                "recommendation": "Fix parsing issues and missing values (use Type Fixer / Null Handler) before trusting segments.",
            })

        if customer_count < 50:
            alerts.append({
                "alert_id": "alert_segmentation_small_population",
                "severity": "medium",
                "category": "data_volume",
                "message": f"Only {customer_count} customers available for segmentation. Segment stability may be low.",
                "affected_fields_count": 0,
                "recommendation": "Use a longer timeframe or collect more transactions to improve stability.",
            })

        if mode == "rfm":
            w_sum_check = rfm_recency_weight + rfm_frequency_weight + rfm_monetary_weight
            if w_sum_check != 100:
                issues.append({
                    "issue_id": "issue_segmentation_weights_sum",
                    "agent_id": agent_id,
                    "field_name": "parameters",
                    "issue_type": "invalid_parameter",
                    "severity": "medium",
                    "message": f"RFM weights sum to {w_sum_check}, not 100. The agent normalizes by the sum.",
                })

        # Column-level issues
        issues.append({
            "issue_id": "issue_segmentation_quality",
            "agent_id": agent_id,
            "field_name": "dataset",
            "issue_type": "segmentation_quality",
            "severity": "low" if quality_status in ["excellent", "good"] else "high",
            "message": f"Segmentation input quality score: {quality_score:.1f}/100 ({quality_status}).",
        })

        if timeframe_retained_rate < 25:
            recommendations.append({
                "recommendation_id": "rec_segmentation_timeframe",
                "agent_id": agent_id,
                "field_name": txn_date_col,
                "priority": "high",
                "recommendation": "Timeframe filter retained a small fraction of valid rows. Consider using a longer window (last_12_months) or verify transaction dates.",
                "timeline": "immediate",
            })

        recommendations.append({
            "recommendation_id": "rec_segmentation_activation",
            "agent_id": agent_id,
            "field_name": "segments",
            "priority": "medium",
            "recommendation": "Use segment summaries to target actions: reward top segments, nurture mid segments, and run win-back campaigns for at-risk/lost segments.",
            "timeline": "1-2 weeks",
        })

        # Executive summary cards
        top_segment = segment_summary.row(0, named=True) if segment_summary.height > 0 else {}
        top_share = float(top_segment.get("value_share_pct", 0.0) or 0.0)
        exec_status = "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "warning"

        executive_summary = [
            {
                "summary_id": "exec_segmentation_customers",
                "title": "Customers Segmented",
                "value": str(customer_count),
                "status": "good" if customer_count >= 50 else "warning",
                "description": f"Computed segments for {customer_count} unique customers.",
            },
            {
                "summary_id": "exec_segmentation_top_share",
                "title": "Top Segment Value Share",
                "value": f"{top_share:.1f}%",
                "status": "excellent" if top_share >= 50 else "good" if top_share >= 30 else "fair",
                "description": "Share of total value contributed by the highest-ranked segment.",
            },
            {
                "summary_id": "exec_segmentation_input_quality",
                "title": "Input Quality",
                "value": f"{quality_score:.1f}",
                "status": exec_status,
                "description": f"Invalid rows: {invalid_rows} ({invalid_rate:.1f}%).",
            },
        ]

        # ----------------------------
        # Issue summary aggregation
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
        segment_rows = [
            {
                **{k: _convert_numpy_types(v) for k, v in row.items()},
            }
            for row in segment_summary.iter_rows(named=True)
        ]
        sample_rows = [
            {
                **{k: _convert_numpy_types(v) for k, v in row.items()},
            }
            for row in sample_customers.iter_rows(named=True)
        ]

        data = {
            "segmentation": segmentation_details,
            "quality": {
                "input_quality_score": round(float(quality_score), 1),
                "quality_status": quality_status,
                "invalid_rows": int(invalid_rows),
                "invalid_rate_pct": round(float(invalid_rate), 2),
                "valid_rows": int(valid_rows),
                "rows_after_timeframe": int(filtered_rows),
                "timeframe_retained_rate_pct": round(float(timeframe_retained_rate), 2),
            },
            "segment_summary": segment_rows,
            "customer_segments_sample": sample_rows,
            "overrides": {
                "mode": mode,
                "timeframe": timeframe,
                "custom_start_date": str(custom_start_date) if custom_start_date else None,
                "custom_end_date": str(custom_end_date) if custom_end_date else None,
                "metric": metric,
                "segment_count": segment_count,
                "customer_id_column": customer_id_column,
                "transaction_date_column": transaction_date_column,
                "value_column": value_column,
                "rfm_recency_weight": rfm_recency_weight,
                "rfm_frequency_weight": rfm_frequency_weight,
                "rfm_monetary_weight": rfm_monetary_weight,
                "rfm_bins": rfm_bins,
                "excellent_threshold": excellent_threshold,
                "good_threshold": good_threshold
            }
        }

        ai_analysis_text = "\n".join([
            "CUSTOMER SEGMENTATION RESULTS:",
            f"- Mode: {mode.upper()} | Segments: {segment_count}",
            f"- Analysis window: {start_dt.isoformat()} to {end_dt.isoformat()}",
            f"- Customers segmented: {customer_count}",
            f"- Total value ({metric}): {total_value:.2f}",
            f"- Input quality score: {quality_score:.1f}/100 ({quality_status}), invalid rows: {invalid_rate:.1f}%",
            f"- Top segment share of value: {top_share:.1f}%",
        ])

        return {
            "status": "success",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_processed": int(filtered_rows),
                "total_customers": int(customer_count),
                "segments_produced": int(segment_count),
                "invalid_rows": int(invalid_rows),
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
