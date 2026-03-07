"""
Exact Fingerprint Match Agent

Node‑03: Zero‑Tolerance Duplicate Detector

Consumes normalized invoice data and computes deterministic fingerprints
to detect exact duplicates across key invoice fields.

Input: Single CSV file (normalized invoice table)
Output: Exact match clusters, collision diagnostics, alerts/issues/recommendations
        following the Agentsium agent response standard.
"""

import io
import time
import hashlib
from typing import Any, Dict, List, Optional

import polars as pl


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


def _hash_fingerprint(values: List[Any]) -> str:
    """
    Deterministic SHA‑256 fingerprint from a list of canonical field values.
    Nulls are represented as empty strings.
    """
    normalized = ["" if v is None else str(v).strip() for v in values]
    joined = "||".join(normalized)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# ----------------------------
# Main agent entrypoint
# ----------------------------

def execute_exact_fingerprint_match_agent(
    file_contents: Optional[bytes] = None,
    filename: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    start_time = time.time()
    parameters = parameters or {}

    agent_id = "exact-fingerprint-match-agent"
    agent_name = "Exact Fingerprint Match Agent"

    # ----------------------------
    # Parse global parameters
    # ----------------------------
    excellent_threshold = _safe_int(parameters.get("excellent_threshold"), 90, 0, 100)
    good_threshold = _safe_int(parameters.get("good_threshold"), 75, 0, 100)

    max_preview_rows = _safe_int(parameters.get("max_preview_rows"), 50, 1, 500)

    alerts: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    row_level_issues: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []

    # ----------------------------
    # Input validation
    # ----------------------------
    if file_contents is None or filename is None:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": "Exact Fingerprint Match requires a normalized invoice CSV file.",
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

    # ----------------------------
    # Required canonical fields
    # ----------------------------
    required_fields = [
        "invoice_id",
        "invoice_date",
        "vendor_name",
        "total_amount",
    ]

    missing_fields = [f for f in required_fields if f not in df.columns]

    for f in missing_fields:
        issues.append({
            "issue_id": f"missing_{f}",
            "agent_id": agent_id,
            "field_name": f,
            "issue_type": "missing_field",
            "severity": "high",
            "message": f"Missing required canonical field '{f}' for fingerprinting.",
        })

    if missing_fields:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": f"Missing required fields: {', '.join(missing_fields)}",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "issues": issues,
        }

    # ----------------------------
    # Compute fingerprints
    # ----------------------------
    fp_fields = ["invoice_id", "invoice_date", "vendor_name", "total_amount"]

    fingerprints = []
    for row in df.select(fp_fields + ["row_index"]).iter_rows(named=True):
        values = [row[f] for f in fp_fields]
        fp = _hash_fingerprint(values)
        fingerprints.append(fp)

    df = df.with_columns(pl.Series("fingerprint", fingerprints))

    # ----------------------------
    # Group by fingerprint
    # ----------------------------
    grouped = df.group_by("fingerprint").agg([
        pl.count().alias("count"),
        pl.col("row_index").alias("rows"),
        pl.col("invoice_id").alias("invoice_ids"),
        pl.col("vendor_name").alias("vendors"),
        pl.col("total_amount").alias("amounts"),
    ])

    # Extract clusters with >1 record
    duplicate_clusters = grouped.filter(pl.col("count") > 1)

    duplicate_count = duplicate_clusters.height
    total_rows = df.height

    # ----------------------------
    # Collision diagnostics
    # ----------------------------
    collision_risk = 0.0
    if total_rows > 0:
        collision_risk = (duplicate_count / total_rows) * 100.0

    # ----------------------------
    # Quality scoring
    # ----------------------------
    quality_score = 100.0

    if duplicate_count == 0:
        quality_score -= 10.0  # no duplicates found may indicate upstream normalization issues

    if collision_risk > 10:
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
    if duplicate_count > 0:
        recommendations.append({
            "recommendation_id": "rec_review_exact_duplicates",
            "agent_id": agent_id,
            "field_name": "fingerprint",
            "priority": "high",
            "recommendation": "Review exact duplicate clusters. These represent invoices that match perfectly across all canonical fields.",
            "timeline": "immediate",
        })

    if collision_risk > 5:
        recommendations.append({
            "recommendation_id": "rec_expand_fingerprint_fields",
            "agent_id": agent_id,
            "field_name": "fingerprint",
            "priority": "medium",
            "recommendation": "Collision rate is elevated. Consider adding PO number or line_amount into the fingerprint.",
            "timeline": "next sprint",
        })

    # ----------------------------
    # Executive summary cards
    # ----------------------------
    executive_summary = [
        {
            "summary_id": "exec_total_rows",
            "title": "Rows Processed",
            "value": f"{total_rows:,}",
            "status": "info",
            "description": "Total normalized invoice rows analyzed.",
        },
        {
            "summary_id": "exec_duplicate_clusters",
            "title": "Exact Duplicate Clusters",
            "value": f"{duplicate_count:,}",
            "status": "warning" if duplicate_count > 0 else "success",
            "description": "Number of fingerprint groups with more than one invoice.",
        },
        {
            "summary_id": "exec_collision_risk",
            "title": "Collision Risk",
            "value": f"{collision_risk:.2f}%",
            "status": "warning" if collision_risk > 5 else "good",
            "description": "Percentage of rows that share a fingerprint with at least one other row.",
        },
        {
            "summary_id": "exec_quality_score",
            "title": "Quality Score",
            "value": f"{quality_score:.1f}",
            "status": quality_status,
            "description": "Overall fingerprinting quality and collision health.",
        },
    ]

    # ----------------------------
    # Issue summary
    # ----------------------------
    row_level_issues = row_level_issues[:1000]
    issue_summary: Dict[str, Any] = {
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
        "max_preview_rows": 50,
    }
    overrides = {
        "excellent_threshold": parameters.get("excellent_threshold"),
        "good_threshold": parameters.get("good_threshold"),
        "max_preview_rows": parameters.get("max_preview_rows"),
    }
    final_params = {
        "excellent_threshold": excellent_threshold,
        "good_threshold": good_threshold,
        "max_preview_rows": max_preview_rows,
    }

    # ----------------------------
    # Data payload
    # ----------------------------
    preview_df = df.head(max_preview_rows)
    normalized_preview = preview_df.to_dicts()

    data = {
        "file_metadata": {
            "filename": filename,
            "rows": total_rows,
            "columns": df.width,
        },
        "fingerprint_fields": fp_fields,
        "duplicate_clusters": duplicate_clusters.to_dicts(),
        "collision_risk_pct": collision_risk,
        "normalized_preview": normalized_preview,
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
        "duplicate_clusters": duplicate_count,
        "collision_risk_pct": round(collision_risk, 2),
        "quality_score": round(quality_score, 1),
    }

    # ----------------------------
    # AI analysis text
    # ----------------------------
    ai_analysis_text = "\n".join([
        "EXACT FINGERPRINT MATCH RESULTS:",
        f"- Rows processed: {total_rows:,}",
        f"- Exact duplicate clusters: {duplicate_count:,}",
        f"- Collision risk: {collision_risk:.2f}%",
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
