"""
Classification & Validation Agent

Node‑02: Data Integrity

Performs structural and field‑level validation on normalized invoices and assigns
basic classifications (PO vs Non‑PO, credit memo vs invoice, single vs multi‑line).
Produces a data integrity score and early‑stage issues before deeper matching.

Input: Single CSV file (normalized invoice table)
Output: Row‑level classifications, integrity issues, integrity score, alerts/issues/recommendations
"""

import io
import time
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


# ----------------------------
# Main agent entrypoint
# ----------------------------

def execute_classification_validation_agent(
    file_contents: Optional[bytes] = None,
    filename: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    start_time = time.time()
    parameters = parameters or {}

    agent_id = "classification-validation-agent"
    agent_name = "Classification & Validation Agent"

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
            "error": "Classification & Validation requires a normalized invoice CSV file.",
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
    # Field casting / validation
    # ----------------------------
    # Try to cast invoice_date to Date
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

    # Try to cast total_amount to Float
    try:
        df = df.with_columns(
            pl.col("total_amount").cast(pl.Float64, strict=False)
        )
    except Exception:
        issues.append({
            "issue_id": "invalid_amount_format",
            "agent_id": agent_id,
            "field_name": "total_amount",
            "issue_type": "invalid_format",
            "severity": "high",
            "message": "Could not parse total_amount into a numeric value.",
        })

    # ----------------------------
    # Row-level classification
    # ----------------------------
    has_po = "po_number" in df.columns
    has_line_id = "line_id" in df.columns

    classifications: List[Dict[str, Any]] = []
    integrity_penalties = 0
    max_penalty = max(df.height * 2, 1)

    for row in df.to_dicts():
        idx = row["row_index"]
        inv_id = row["invoice_id"]
        vendor = row["vendor_name"]
        amount = _safe_float(row.get("total_amount"))

        # Basic type classification
        po_type = "PO" if has_po and row.get("po_number") not in (None, "", "NA") else "Non‑PO"
        credit_type = "Credit Memo" if amount < 0 else "Invoice"

        # Multi-line vs single-line (heuristic: presence of line_id duplicates)
        line_type = "Unknown"
        if has_line_id:
            line_type = "Line‑Level"
        else:
            line_type = "Header‑Only"

        # Structural checks
        row_issues = []

        if inv_id in (None, "", "NA"):
            row_issues.append("missing_invoice_id")
            integrity_penalties += 2

        if vendor in (None, "", "NA"):
            row_issues.append("missing_vendor_name")
            integrity_penalties += 2

        if amount == 0.0:
            row_issues.append("zero_amount")
            integrity_penalties += 1

        if row.get("invoice_date") is None:
            row_issues.append("missing_invoice_date")
            integrity_penalties += 2

        if row_issues:
            row_level_issues.append({
                "row_index": idx,
                "invoice_id": inv_id,
                "vendor_name": vendor,
                "issue_type": "data_integrity",
                "issues": row_issues,
            })

        classifications.append({
            "row_index": idx,
            "invoice_id": inv_id,
            "vendor_name": vendor,
            "total_amount": amount,
            "po_type": po_type,
            "document_type": credit_type,
            "structure_type": line_type,
        })

    # ----------------------------
    # Data integrity scoring
    # ----------------------------
    integrity_score = 100.0
    if integrity_penalties > 0:
        penalty_ratio = min(1.0, integrity_penalties / float(max_penalty))
        integrity_score = max(0.0, 100.0 * (1.0 - penalty_ratio))

    if integrity_score >= excellent_threshold:
        integrity_status = "excellent"
    elif integrity_score >= good_threshold:
        integrity_status = "good"
    else:
        integrity_status = "needs_improvement"

    # ----------------------------
    # Recommendations
    # ----------------------------
    if integrity_score < good_threshold:
        recommendations.append({
            "recommendation_id": "rec_improve_data_integrity",
            "agent_id": agent_id,
            "field_name": "data_integrity",
            "priority": "high",
            "recommendation": "Data integrity issues detected. Review missing fields, invalid dates, and zero‑amount invoices.",
            "timeline": "immediate",
        })

    if integrity_score >= excellent_threshold:
        recommendations.append({
            "recommendation_id": "rec_trust_upstream",
            "agent_id": agent_id,
            "field_name": "data_integrity",
            "priority": "medium",
            "recommendation": "High data integrity. Upstream extraction and normalization appear stable.",
            "timeline": "next sprint",
        })

    # ----------------------------
    # Executive summary
    # ----------------------------
    total_rows = df.height
    rows_with_issues = len({r["row_index"] for r in row_level_issues})

    executive_summary = [
        {
            "summary_id": "exec_rows",
            "title": "Rows Analyzed",
            "value": f"{total_rows:,}",
            "status": "info",
            "description": "Total normalized invoice rows validated.",
        },
        {
            "summary_id": "exec_rows_with_issues",
            "title": "Rows with Integrity Issues",
            "value": f"{rows_with_issues:,}",
            "status": "warning" if rows_with_issues > 0 else "success",
            "description": "Rows with missing or malformed key fields.",
        },
        {
            "summary_id": "exec_integrity_score",
            "title": "Data Integrity Score",
            "value": f"{integrity_score:.1f}",
            "status": integrity_status,
            "description": "Overall structural and field‑level data integrity.",
        },
    ]

    # ----------------------------
    # Issue summary
    # ----------------------------
    issue_summary = {
        "total_issues": len(row_level_issues),
        "by_type": {
            "data_integrity": len(row_level_issues),
        } if row_level_issues else {},
        "by_severity": {},
        "affected_rows": rows_with_issues,
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
    data = {
        "classifications": classifications[:max_preview_rows],
        "integrity_score": round(int integrity_score, 1) if isinstance(integrity_score, float) else integrity_score,
        "integrity_status": integrity_status,
        "defaults": defaults,
        "overrides": overrides,
        "parameters": final_params,
    }

    # ----------------------------
    # Summary metrics
    # ----------------------------
    summary_metrics = {
        "rows_processed": total_rows,
        "rows_with_issues": rows_with_issues,
        "integrity_score": round(integrity_score, 1),
    }

    # ----------------------------
    # AI analysis text
    # ----------------------------
    ai_analysis_text = "\n".join([
        "CLASSIFICATION & VALIDATION RESULTS:",
        f"- Rows processed: {total_rows:,}",
        f"- Rows with integrity issues: {rows_with_issues:,}",
        f"- Data integrity score: {integrity_score:.1f} ({integrity_status})",
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
