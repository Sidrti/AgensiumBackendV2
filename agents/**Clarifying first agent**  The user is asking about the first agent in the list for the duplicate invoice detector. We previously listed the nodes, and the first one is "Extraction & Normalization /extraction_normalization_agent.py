"""
Extraction & Normalization Agent

Node-01: Fast OCR Stream

Normalizes raw invoice-like tabular data into a canonical schema, parses dates and amounts,
and produces field-level coverage and quality metrics.

Input: Single CSV file (export from OCR or AP system)
Output: Normalized sample, field mapping, coverage stats, and issues following Agentsium agent response standard.
"""

import io
import time
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from .agent_utils import normalize_column_names


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


def _safe_float(value: Any, default: float, min_value: Optional[float] = None, max_value: Optional[float] = None) -> float:
    try:
        if value is None:
            return default
        v = float(value)
        if v != v or v == float("inf") or v == float("-inf"):
            return default
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


def _resolve_column(candidates: List[str], available: List[str]) -> Optional[str]:
    """
    Resolve a column name from a list of candidate aliases using case-insensitive matching
    and the shared normalize_column_names helper.
    """
    if not available:
        return None

    # Direct case-insensitive match
    lower_map = {c.lower(): c for c in available}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]

    # Fallback to normalize_column_names for fuzzy-ish matching
    for cand in candidates:
        normalized = normalize_column_names([cand], available, case_sensitive=False)
        if normalized:
            return normalized[0]

    return None


def _parse_date_column(df: pl.DataFrame, raw_col: str, out_col: str, row_level_issues: List[Dict[str, Any]]) -> pl.Series:
    """
    Parse a date-like column into pl.Date, recording row-level issues for failures.
    """
    s = df[raw_col]

    if s.dtype in (pl.Date, pl.Datetime):
        parsed = s.cast(pl.Date, strict=False)
    else:
        parsed = (
            s.cast(pl.Utf8, strict=False)
             .str.strip_chars()
             .str.to_datetime(strict=False)
             .cast(pl.Date, strict=False)
        )

    # Record issues where raw is non-null but parsed is null
    bad = df.with_columns(parsed.alias(out_col)).filter(
        pl.col(raw_col).is_not_null() & pl.col(out_col).is_null()
    )

    for r in bad.select(["row_index", raw_col]).head(200).iter_rows(named=True):
        row_level_issues.append({
            "row_index": int(r["row_index"]),
            "column": raw_col,
            "issue_type": "invalid_date",
            "severity": "high",
            "message": "Date could not be parsed",
            "value": str(r.get(raw_col)),
        })

    return parsed


def _parse_amount_column(df: pl.DataFrame, raw_col: str, out_col: str, row_level_issues: List[Dict[str, Any]]) -> pl.Series:
    """
    Parse an amount-like column into Float64, recording row-level issues for failures.
    """
    s = df[raw_col]
    parsed = s.cast(pl.Float64, strict=False)
    parsed = pl.when(parsed.is_finite()).then(parsed).otherwise(None)

    bad = df.with_columns(parsed.alias(out_col)).filter(
        pl.col(raw_col).is_not_null() & pl.col(out_col).is_null()
    )

    for r in bad.select(["row_index", raw_col]).head(200).iter_rows(named=True):
        row_level_issues.append({
            "row_index": int(r["row_index"]),
            "column": raw_col,
            "issue_type": "invalid_amount",
            "severity": "high",
            "message": "Amount could not be parsed",
            "value": str(r.get(raw_col)),
        })

    return parsed


# ----------------------------
# Main agent entrypoint
# ----------------------------

def execute_extraction_normalization_agent(
    file_contents: Optional[bytes] = None,
    filename: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    start_time = time.time()
    parameters = parameters or {}

    agent_id = "extraction-normalization-agent"
    agent_name = "Extraction & Normalization Agent"

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
    # Basic input validation
    # ----------------------------
    if file_contents is None or filename is None:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": "Extraction & Normalization requires a primary CSV file.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    if not filename.lower().endswith(".csv"):
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": f"Unsupported file format: {filename}. Only CSV is supported for this agent.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    try:
        df_raw = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
    except Exception as e:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": f"Failed to parse CSV: {str(e)}",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    if df_raw.height == 0 or df_raw.width == 0:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": "Input file is empty or has no columns.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    # Add row_index for row-level issues
    df_working = df_raw.with_row_index("row_index")

    # ----------------------------
    # Canonical schema & mapping
    # ----------------------------
    available_cols = df_working.columns

    canonical_schema: Dict[str, List[str]] = {
        "invoice_id": ["invoice_id", "invoice number", "invoice_no", "inv_id", "inv_number"],
        "invoice_date": ["invoice_date", "inv_date", "date", "document_date"],
        "due_date": ["due_date", "payment_due_date", "terms_date"],
        "vendor_name": ["vendor_name", "supplier_name", "payee", "vendor"],
        "vendor_id": ["vendor_id", "supplier_id", "vendor code", "supplier code"],
        "po_number": ["po_number", "purchase_order", "po", "purchase_order_number"],
        "currency": ["currency", "currency_code", "curr"],
        "line_amount": ["line_amount", "amount", "net_amount", "subtotal"],
        "tax_amount": ["tax_amount", "tax", "vat_amount"],
        "total_amount": ["total_amount", "invoice_total", "gross_amount", "total"],
    }

    resolved_mapping: Dict[str, Optional[str]] = {}
    for canonical, aliases in canonical_schema.items():
        resolved_mapping[canonical] = _resolve_column(aliases, available_cols)

    # Track missing critical fields
    critical_fields = ["invoice_id", "invoice_date", "vendor_name", "total_amount"]
    missing_critical = [f for f in critical_fields if resolved_mapping.get(f) is None]

    for f in missing_critical:
        issues.append({
            "issue_id": f"issue_missing_{f}",
            "agent_id": agent_id,
            "field_name": f,
            "issue_type": "missing_field",
            "severity": "high",
            "message": f"Could not resolve a column for canonical field '{f}'.",
        })

    # ----------------------------
    # Build normalized frame
    # ----------------------------
    normalized_cols: List[pl.Series] = []
    normalization_stats: Dict[str, Any] = {
        "field_coverage": {},
        "date_parse_success_rate": {},
        "amount_parse_success_rate": {},
    }

    # Always keep row_index for traceability
    normalized_cols.append(df_working["row_index"])

    # Non-date, non-amount fields
    simple_fields = ["invoice_id", "vendor_name", "vendor_id", "po_number", "currency"]
    date_fields = ["invoice_date", "due_date"]
    amount_fields = ["line_amount", "tax_amount", "total_amount"]

    # Simple fields: just alias
    for field in simple_fields:
        src = resolved_mapping.get(field)
        if src is not None:
            s = df_working[src].cast(pl.Utf8, strict=False)
            normalized_cols.append(s.alias(field))

            non_null = s.drop_nulls().len()
            coverage = (non_null / df_working.height) * 100.0 if df_working.height > 0 else 0.0
            normalization_stats["field_coverage"][field] = round(coverage, 2)
        else:
            normalization_stats["field_coverage"][field] = 0.0

    # Date fields
    for field in date_fields:
        src = resolved_mapping.get(field)
        if src is not None:
            parsed = _parse_date_column(df_working, src, field, row_level_issues)
            normalized_cols.append(parsed.alias(field))

            non_null_raw = df_working[src].drop_nulls().len()
            non_null_parsed = parsed.drop_nulls().len()
            coverage = (non_null_parsed / df_working.height) * 100.0 if df_working.height > 0 else 0.0
            success_rate = (non_null_parsed / non_null_raw) * 100.0 if non_null_raw > 0 else 0.0

            normalization_stats["field_coverage"][field] = round(coverage, 2)
            normalization_stats["date_parse_success_rate"][field] = round(success_rate, 2)
        else:
            normalization_stats["field_coverage"][field] = 0.0
            normalization_stats["date_parse_success_rate"][field] = 0.0

    # Amount fields
    for field in amount_fields:
        src = resolved_mapping.get(field)
        if src is not None:
            parsed = _parse_amount_column(df_working, src, field, row_level_issues)
            normalized_cols.append(parsed.alias(field))

            non_null_raw = df_working[src].drop_nulls().len()
            non_null_parsed = parsed.drop_nulls().len()
            coverage = (non_null_parsed / df_working.height) * 100.0 if df_working.height > 0 else 0.0
            success_rate = (non_null_parsed / non_null_raw) * 100.0 if non_null_raw > 0 else 0.0

            normalization_stats["field_coverage"][field] = round(coverage, 2)
            normalization_stats["amount_parse_success_rate"][field] = round(success_rate, 2)
        else:
            normalization_stats["field_coverage"][field] = 0.0
            normalization_stats["amount_parse_success_rate"][field] = 0.0

    normalized_df = pl.DataFrame(normalized_cols)

    # ----------------------------
    # Aggregate metrics
    # ----------------------------
    total_rows = df_working.height
    normalized_fields = [c for c in normalized_df.columns if c != "row_index"]
    normalized_field_count = len(normalized_fields)

    # Define "valid row" as having invoice_id + total_amount non-null
    valid_rows_df = normalized_df.filter(
        pl.col("invoice_id").is_not_null() & (pl.col("invoice_id") != "") &
        pl.col("total_amount").is_not_null()
    ) if ("invoice_id" in normalized_df.columns and "total_amount" in normalized_df.columns) else pl.DataFrame()

    valid_rows = valid_rows_df.height

    # Average parse success for dates and amounts
    date_rates = list(normalization_stats["date_parse_success_rate"].values()) or [0.0]
    amount_rates = list(normalization_stats["amount_parse_success_rate"].values()) or [0.0]
    avg_date_success = sum(date_rates) / len(date_rates)
    avg_amount_success = sum(amount_rates) / len(amount_rates)

    # ----------------------------
    # Quality scoring
    # ----------------------------
    quality_score = 100.0

    # Penalize missing critical fields
    quality_score -= min(40.0, 10.0 * len(missing_critical))

    # Penalize low valid row rate
    if total_rows > 0:
        valid_rate = (valid_rows / total_rows) * 100.0
        if valid_rate < 80:
            quality_score -= 20.0
        if valid_rate < 50:
            quality_score -= 20.0

    # Penalize poor parsing
    if avg_date_success < 80:
        quality_score -= 10.0
    if avg_amount_success < 80:
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
    if missing_critical:
        recommendations.append({
            "recommendation_id": "rec_add_critical_fields",
            "agent_id": agent_id,
            "field_name": ",".join(missing_critical),
            "priority": "high",
            "recommendation": f"Map or capture missing critical fields: {', '.join(missing_critical)}. "
                              f"These are required for robust duplicate detection and routing.",
            "timeline": "before production",
        })

    if avg_date_success < 90:
        recommendations.append({
            "recommendation_id": "rec_improve_date_formats",
            "agent_id": agent_id,
            "field_name": "date_fields",
            "priority": "medium",
            "recommendation": "Standardize invoice and due date formats at the source or in OCR templates to improve parse success.",
            "timeline": "next sprint",
        })

    if avg_amount_success < 95:
        recommendations.append({
            "recommendation_id": "rec_improve_amount_cleaning",
            "agent_id": agent_id,
            "field_name": "amount_fields",
            "priority": "medium",
            "recommendation": "Ensure numeric fields are not polluted with currency symbols or text before ingestion.",
            "timeline": "next sprint",
        })

    # ----------------------------
    # Executive summary cards
    # ----------------------------
    valid_rate = (valid_rows / total_rows) * 100.0 if total_rows > 0 else 0.0

    executive_summary = [
        {
            "summary_id": "exec_rows_processed",
            "title": "Rows Processed",
            "value": f"{total_rows:,}",
            "status": "info",
            "description": "Total invoice-like records ingested for normalization.",
        },
        {
            "summary_id": "exec_valid_rows",
            "title": "Valid Normalized Rows",
            "value": f"{valid_rows:,} ({valid_rate:.1f}%)",
            "status": "excellent" if valid_rate >= 90 else "good" if valid_rate >= 75 else "warning",
            "description": "Rows with both invoice_id and total_amount successfully normalized.",
        },
        {
            "summary_id": "exec_normalized_fields",
            "title": "Normalized Fields",
            "value": normalized_field_count,
            "status": "good" if normalized_field_count >= 6 else "warning",
            "description": "Number of canonical fields successfully mapped and normalized.",
        },
        {
            "summary_id": "exec_avg_date_success",
            "title": "Date Parse Success",
            "value": f"{avg_date_success:.1f}%",
            "status": "excellent" if avg_date_success >= 95 else "good" if avg_date_success >= 85 else "warning",
            "description": "Average parse success rate across date fields.",
        },
        {
            "summary_id": "exec_avg_amount_success",
            "title": "Amount Parse Success",
            "value": f"{avg_amount_success:.1f}%",
            "status": "excellent" if avg_amount_success >= 98 else "good" if avg_amount_success >= 90 else "warning",
            "description": "Average parse success rate across amount fields.",
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
        "affected_columns": sorted(list({i.get("column") for i in row_level_issues if i.get("column")})),
    }
    affected_rows_set = set()
    for i in row_level_issues:
        t = i.get("issue_type", "unknown")
        s = i.get("severity", "info")
        issue_summary["by_type"][t] = issue_summary["by_type"].get(t, 0) + 1
        issue_summary["by_severity"][s] = issue_summary["by_severity"].get(s, 0) + 1
        if i.get("row_index") is not None:
            affected_rows_set.add(i["row_index"])
    issue_summary["affected_rows"] = len(affected_rows_set)

    # ----------------------------
    # Defaults / overrides / final parameters
    # ----------------------------
    defaults: Dict[str, Any] = {
        "excellent_threshold": 90,
        "good_threshold": 75,
        "max_preview_rows": 50,
    }
    overrides: Dict[str, Any] = {
        "excellent_threshold": parameters.get("excellent_threshold"),
        "good_threshold": parameters.get("good_threshold"),
        "max_preview_rows": parameters.get("max_preview_rows"),
    }
    final_params: Dict[str, Any] = {
        "excellent_threshold": excellent_threshold,
        "good_threshold": good_threshold,
        "max_preview_rows": max_preview_rows,
    }

    # ----------------------------
    # Data payload
    # ----------------------------
    preview_df = normalized_df.head(max_preview_rows)
    normalized_preview = preview_df.to_dicts()

    data: Dict[str, Any] = {
        "file_metadata": {
            "filename": filename,
            "rows": total_rows,
            "columns": df_raw.width,
        },
        "original_columns": df_raw.columns,
        "canonical_mapping": resolved_mapping,
        "normalized_preview": normalized_preview,
        "normalization_stats": normalization_stats,
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
    summary_metrics: Dict[str, Any] = {
        "rows_processed": total_rows,
        "valid_rows": valid_rows,
        "normalized_field_count": normalized_field_count,
        "avg_date_parse_success": round(avg_date_success, 2),
        "avg_amount_parse_success": round(avg_amount_success, 2),
        "missing_critical_fields": len(missing_critical),
    }

    # ----------------------------
    # AI analysis text
    # ----------------------------
    ai_analysis_text = "\n".join([
        "EXTRACTION & NORMALIZATION RESULTS:",
        f"- Rows processed: {total_rows:,}",
        f"- Valid normalized rows: {valid_rows:,} ({valid_rate:.1f}%)",
        f"- Normalized fields: {normalized_field_count}",
        f"- Avg date parse success: {avg_date_success:.1f}%",
        f"- Avg amount parse success: {avg_amount_success:.1f}%",
        f"- Missing critical fields: {len(missing_critical)} ({', '.join(missing_critical) if missing_critical else 'none'})",
        f"- Plan quality score: {quality_score:.1f} ({quality_status})",
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
