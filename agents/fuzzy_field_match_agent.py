"""
Fuzzy Field Match Agent

Node‑04: Cognitive Near‑Match

Detects near‑duplicate invoices using fuzzy string similarity, numeric tolerance
matching, and weighted multi‑field scoring. Designed to catch duplicates that
are not exact matches but differ due to OCR noise, typos, formatting, or vendor
system inconsistencies.

Input: Single CSV file (normalized invoice table)
Output: Fuzzy match pairs, similarity scores, mismatch diagnostics,
        alerts/issues/recommendations following Agentsium agent response standard.
"""

import io
import time
from typing import Any, Dict, List, Optional, Tuple

import polars as pl
from rapidfuzz import fuzz


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


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _fmt_money(value: float) -> str:
    try:
        return f"${value:,.2f}"
    except Exception:
        return "$0.00"


def _string_sim(a: Optional[str], b: Optional[str]) -> float:
    if a is None or b is None:
        return 0.0
    return fuzz.token_sort_ratio(str(a), str(b))


def _numeric_sim(a: Optional[float], b: Optional[float], tolerance: float = 0.01) -> float:
    if a is None or b is None:
        return 0.0
    if a == 0 and b == 0:
        return 100.0
    diff = abs(a - b)
    if diff <= tolerance * max(abs(a), abs(b), 1.0):
        return 100.0
    return max(0.0, 100.0 - (diff * 10))


# ----------------------------
# Main agent entrypoint
# ----------------------------

def execute_fuzzy_field_match_agent(
    file_contents: Optional[bytes] = None,
    filename: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    start_time = time.time()
    parameters = parameters or {}

    agent_id = "fuzzy-field-match-agent"
    agent_name = "Fuzzy Field Match Agent"

    # ----------------------------
    # Parse global parameters
    # ----------------------------
    excellent_threshold = _safe_int(parameters.get("excellent_threshold"), 90)
    good_threshold = _safe_int(parameters.get("good_threshold"), 75)
    similarity_threshold = _safe_int(parameters.get("similarity_threshold"), 85, 1, 100)
    max_pairs = _safe_int(parameters.get("max_pairs"), 500, 10, 5000)
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
            "error": "Fuzzy Field Match requires a normalized invoice CSV file.",
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
    # Compute fuzzy similarity pairs
    # ----------------------------
    rows = df.to_dicts()
    n = len(rows)

    fuzzy_pairs = []
    count = 0

    for i in range(n):
        if count >= max_pairs:
            break
        for j in range(i + 1, n):
            if count >= max_pairs:
                break

            a = rows[i]
            b = rows[j]

            sim_vendor = _string_sim(a["vendor_name"], b["vendor_name"])
            sim_invoice_id = _string_sim(a["invoice_id"], b["invoice_id"])
            sim_date = _string_sim(str(a["invoice_date"]), str(b["invoice_date"]))
            sim_amount = _numeric_sim(a["total_amount"], b["total_amount"])

            weighted = (
                sim_vendor * 0.35 +
                sim_invoice_id * 0.35 +
                sim_date * 0.10 +
                sim_amount * 0.20
            )

            if weighted >= similarity_threshold:
                fuzzy_pairs.append({
                    "row_a": a["row_index"],
                    "row_b": b["row_index"],
                    "invoice_id_a": a["invoice_id"],
                    "invoice_id_b": b["invoice_id"],
                    "vendor_a": a["vendor_name"],
                    "vendor_b": b["vendor_name"],
                    "similarity_vendor": round(sim_vendor, 1),
                    "similarity_invoice_id": round(sim_invoice_id, 1),
                    "similarity_date": round(sim_date, 1),
                    "similarity_amount": round(sim_amount, 1),
                    "weighted_similarity": round(weighted, 1),
                })
                count += 1

    fuzzy_pairs_sorted = sorted(fuzzy_pairs, key=lambda x: -x["weighted_similarity"])

    # ----------------------------
    # Quality scoring
    # ----------------------------
    quality_score = 100.0

    if len(fuzzy_pairs_sorted) == 0:
        quality_score -= 20.0

    if len(fuzzy_pairs_sorted) > max_pairs * 0.8:
        quality_score -= 10.0

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
    if len(fuzzy_pairs_sorted) > 0:
        recommendations.append({
            "recommendation_id": "rec_review_fuzzy_matches",
            "agent_id": agent_id,
            "field_name": "weighted_similarity",
            "priority": "high",
            "recommendation": "Review fuzzy match pairs. These represent invoices that are not exact duplicates but are highly similar.",
            "timeline": "immediate",
        })

    if len(fuzzy_pairs_sorted) == 0:
        recommendations.append({
            "recommendation_id": "rec_adjust_threshold",
            "agent_id": agent_id,
            "field_name": "similarity_threshold",
            "priority": "medium",
            "recommendation": "No fuzzy matches detected. Consider lowering similarity_threshold or improving normalization.",
            "timeline": "next sprint",
        })

    # ----------------------------
    # Executive summary
    # ----------------------------
    total_rows = df.height
    fuzzy_count = len(fuzzy_pairs_sorted)

    executive_summary = [
        {
            "summary_id": "exec_rows",
            "title": "Rows Processed",
            "value": f"{total_rows:,}",
            "status": "info",
            "description": "Total normalized invoice rows analyzed.",
        },
        {
            "summary_id": "exec_fuzzy_pairs",
            "title": "Fuzzy Match Pairs",
            "value": f"{fuzzy_count:,}",
            "status": "warning" if fuzzy_count > 0 else "success",
            "description": "Number of invoice pairs exceeding the similarity threshold.",
        },
        {
            "summary_id": "exec_similarity_threshold",
            "title": "Similarity Threshold",
            "value": f"{similarity_threshold}%",
            "status": "info",
            "description": "Minimum weighted similarity required to flag a near‑match.",
        },
        {
            "summary_id": "exec_quality",
            "title": "Match Quality Score",
            "value": f"{quality_score:.1f}",
            "status": quality_status,
            "description": "Overall fuzzy matching health.",
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
        "similarity_threshold": 85,
        "max_pairs": 500,
        "max_preview_rows": 50,
    }
    overrides = {
        "excellent_threshold": parameters.get("excellent_threshold"),
        "good_threshold": parameters.get("good_threshold"),
        "similarity_threshold": parameters.get("similarity_threshold"),
        "max_pairs": parameters.get("max_pairs"),
        "max_preview_rows": parameters.get("max_preview_rows"),
    }
    final_params = {
        "excellent_threshold": excellent_threshold,
        "good_threshold": good_threshold,
        "similarity_threshold": similarity_threshold,
        "max_pairs": max_pairs,
        "max_preview_rows": max_preview_rows,
    }

    # ----------------------------
    # Data payload
    # ----------------------------
    data = {
        "fuzzy_pairs": fuzzy_pairs_sorted[:max_preview_rows],
        "similarity_threshold": similarity_threshold,
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
        "fuzzy_pairs": fuzzy_count,
        "quality_score": round(quality_score, 1),
    }

    # ----------------------------
    # AI analysis text
    # ----------------------------
    ai_analysis_text = "\n".join([
        "FUZZY FIELD MATCH RESULTS:",
        f"- Rows processed: {total_rows:,}",
        f"- Fuzzy match pairs: {fuzzy_count:,}",
        f"- Similarity threshold: {similarity_threshold}%",
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
