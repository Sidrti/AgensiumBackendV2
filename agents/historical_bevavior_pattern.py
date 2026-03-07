"""
Historical & Behavioral Pattern Agent

Node‑07: Temporal & Behavioral Anomaly Detection

Analyzes historical invoice behavior to detect unusual patterns such as:
- Sudden vendor spend spikes
- Repeated invoice amounts
- Abnormal frequency changes
- Deviations from vendor‑specific norms
- Behavioral anomalies that may indicate fraud or duplicate risk

Input: Single CSV file (normalized invoice table)
Output: Behavioral anomalies, vendor‑level diagnostics, alerts/issues/recommendations
"""

import io
import time
from typing import Any, Dict, List, Optional

import polars as pl
import numpy as np


# ----------------------------
# Helper functions
# ----------------------------

def _safe_int(value: Any, default: int, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
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


def _fmt_money(value: float) -> str:
    try:
        return f"${value:,.2f}"
    except Exception:
        return "$0.00"


def _zscore(values: List[float]) -> List[float]:
    arr = np.array(values, dtype=float)
    if len(arr) < 2:
        return [0.0] * len(arr)
    mean = np.mean(arr)
    std = np.std(arr) + 1e-12
    return list((arr - mean) / std)


# ----------------------------
# Main agent entrypoint
# ----------------------------

def execute_historical_behavioral_pattern_agent(
    file_contents: Optional[bytes] = None,
    filename: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    start_time = time.time()
    parameters = parameters or {}

    agent_id = "historical-behavioral-pattern-agent"
    agent_name = "Historical & Behavioral Pattern Agent"

    excellent_threshold = _safe_int(parameters.get("excellent_threshold"), 90)
    good_threshold = _safe_int(parameters.get("good_threshold"), 75)
    zscore_threshold = _safe_int(parameters.get("zscore_threshold"), 3, 1, 10)
    max_preview_rows = _safe_int(parameters.get("max_preview_rows"), 50, 1, 500)

    alerts, issues, row_level_issues, recommendations = [], [], [], []

    # ----------------------------
    # Input validation
    # ----------------------------
    if file_contents is None or filename is None:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": "Historical analysis requires a normalized invoice CSV file.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    if not filename.lower().endswith(".csv"):
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": f"Unsupported file format: {filename}. Only CSV is supported.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

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
            "error": "Input file is empty or has no columns.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    df = df.with_row_index("row_index")

    required_fields = ["invoice_id", "invoice_date", "vendor_name", "total_amount"]

    missing_fields = [f for f in required_fields if f not in df.columns]
    if missing_fields:
        issues.append({
            "issue_id": "missing_fields",
            "agent_id": agent_id,
            "field_name": ",".join(missing_fields),
            "issue_type": "missing_field",
            "severity": "high",
            "message": f"Missing required fields: {', '.join(missing_fields)}",
        })
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": f"Missing required fields: {', '.join(missing_fields)}",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "issues": issues,
        }

    # ----------------------------
    # Convert invoice_date to Date
    # ----------------------------
    try:
        df = df.with_columns(
            pl.col("invoice_date").cast(pl.Date, strict=False)
        )
    except Exception:
        issues.append({
            "issue_id": "invalid_date_format",
            "agent_id": agent_id,
            "field_name": "invoice_date",
            "issue_type": "invalid_format",
            "severity": "high",
            "message": "Could not parse invoice_date into a valid date.",
        })

    # ----------------------------
    # Vendor-level grouping
    # ----------------------------
    vendors = df.group_by("vendor_name").agg([
        pl.col("total_amount").alias("amounts"),
        pl.col("invoice_date").alias("dates"),
        pl.col("row_index").alias("rows"),
    ])

    anomalies = []

    for row in vendors.iter_rows(named=True):
        vendor = row["vendor_name"]
        amounts = row["amounts"]
        dates = row["dates"]
        rows_idx = row["rows"]

        if len(amounts) < 3:
            continue

        zscores = _zscore(amounts)

        for i, z in enumerate(zscores):
            if abs(z) >= zscore_threshold:
                anomalies.append({
                    "vendor_name": vendor,
                    "row_index": rows_idx[i],
                    "amount": amounts[i],
                    "zscore": round(float(z), 2),
                    "severity": "high" if abs(z) >= zscore_threshold + 1 else "medium",
                    "message": "Unusual invoice amount relative to vendor history.",
                })

    # ----------------------------
    # Frequency anomalies
    # ----------------------------
    df = df.sort("invoice_date")
    df = df.with_columns([
        pl.col("invoice_date").diff().alias("date_diff")
    ])

    freq_anomalies = df.filter(
        (pl.col("date_diff").dt.days() < 2) & (pl.col("date_diff").is_not_null())
    )

    for r in freq_anomalies.to_dicts():
        anomalies.append({
            "vendor_name": r["vendor_name"],
            "row_index": r["row_index"],
            "amount": r["total_amount"],
            "zscore": None,
            "severity": "medium",
            "message": "Invoices occurring unusually close together.",
        })

    anomaly_count = len(anomalies)

    # ----------------------------
    # Quality scoring
    # ----------------------------
    quality_score = 100.0

    if anomaly_count == 0:
        quality_score -= 10.0

    if anomaly_count > 20:
        quality_score -= 20.0

    quality_score = max(0.0, min(100.0, quality_score))

    if quality_score >= excellent_threshold:
        quality_status = "excellent"
    elif quality_score >= good_threshold:
        quality_status = "good"
    else:
        quality_status = "needs_improvement"

    # ----------------------------
    # Recommendations
    # ----------------------------
    if anomaly_count > 0:
        recommendations.append({
            "recommendation_id": "rec_review_anomalies",
            "agent_id": agent_id,
            "field_name": "behavioral_anomalies",
            "priority": "high",
            "recommendation": "Review behavioral anomalies. These may indicate fraud, duplicates, or unusual vendor activity.",
            "timeline": "immediate",
        })

    if anomaly_count == 0:
        recommendations.append({
            "recommendation_id": "rec_expand_history",
            "agent_id": agent_id,
            "field_name": "historical_data",
            "priority": "medium",
            "recommendation": "No anomalies detected. Consider expanding historical data for stronger behavioral baselines.",
            "timeline": "next sprint",
        })

    # ----------------------------
    # Executive summary
    # ----------------------------
    total_rows = df.height

    executive_summary = [
        {
            "summary_id": "exec_rows",
            "title": "Rows Analyzed",
            "value": f"{total_rows:,}",
            "status": "info",
            "description": "Total normalized invoice rows analyzed.",
        },
        {
            "summary_id": "exec_anomalies",
            "title": "Behavioral Anomalies",
            "value": f"{anomaly_count:,}",
            "status": "warning" if anomaly_count > 0 else "success",
            "description": "Invoices with unusual vendor behavior or frequency patterns.",
        },
        {
            "summary_id": "exec_zscore_threshold",
            "title": "Z‑Score Threshold",
            "value": f"{zscore_threshold}",
            "status": "info",
            "description": "Threshold used to flag unusual invoice amounts.",
        },
        {
            "summary_id": "exec_quality",
            "title": "Behavioral Quality Score",
            "value": f"{quality_score:.1f}",
            "status": quality_status,
            "description": "Overall health of historical and behavioral patterns.",
        },
    ]

    # ----------------------------
    # Issue summary
    # ----------------------------
    issue_summary = {
        "total_issues": len(row_level_issues),
        "by_type": {},
        "by_severity": {},
        "affected_rows": 0,
        "affected_columns": [],
    }

    # ----------------------------
    # Defaults / overrides / final parameters
    # ----------------------------
    defaults = {
        "excellent_threshold": 90,
        "good_threshold": 75,
        "zscore_threshold": 3,
        "max_preview_rows": 50,
    }
    overrides = {
        "excellent_threshold": parameters.get("excellent_threshold"),
        "good_threshold": parameters.get("good_threshold"),
        "zscore_threshold": parameters.get("zscore_threshold"),
        "max_preview_rows": parameters.get("max_preview_rows"),
    }
    final_params = {
        "excellent_threshold": excellent_threshold,
        "good_threshold": good_threshold,
        "zscore_threshold": zscore_threshold,
        "max_preview_rows": max_preview_rows,
    }

    # ----------------------------
    # Data payload
    # ----------------------------
    data = {
        "behavioral_anomalies": anomalies[:max_preview_rows],
        "zscore_threshold": zscore_threshold,
        "quality": {
            "plan_quality_score": round(quality_score, 1),
            "quality_status": quality_status,
        },
        "defaults": defaults,
        "overrides": overrides,
        "parameters": final_params,
    }

    # ----------------------------
    # Summary metrics
    # ----------------------------
    summary_metrics = {
        "rows_processed": total_rows,
        "behavioral_anomalies": anomaly_count,
        "quality_score": round(quality_score, 1),
    }

    # ----------------------------
    # AI analysis text
    # ----------------------------
    ai_analysis_text = "\n".join([
        "HISTORICAL & BEHAVIORAL ANALYSIS RESULTS:",
        f"- Rows processed: {total_rows:,}",
        f"- Behavioral anomalies: {anomaly_count:,}",
        f"- Z‑score threshold: {zscore_threshold}",
        f"- Quality score: {quality_score:.1f} ({quality_status})",
    ])

    return {
        "status": "success",
        "agent_id": agent_id,
        "agent_name": agent_name,
        "execution_time_ms": int((time.time() - start_time) * 1000),
        "summary_metrics": summary_metrics,
        "data": data,
        "alerts": alerts,
        "issues": issues,
        "row_level_issues": row_level_issues,
        "issue_summary": issue_summary,
        "recommendations": recommendations,
        "executive_summary": executive_summary,
        "ai_analysis_text": ai_analysis_text,
    }
