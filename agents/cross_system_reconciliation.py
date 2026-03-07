"""
Cross‑System Reconciliation Agent

Node‑03: Ledger Alignment

Compares invoices across multiple systems (OCR, AP, ERP, Vendor feeds) and identifies:
- Missing invoices in one or more systems
- Field‑level mismatches (amount, date, vendor, PO)
- Cross‑system alignment clusters
- Reconciliation quality metrics

Input: Two or more CSV files
Output: Reconciliation clusters, mismatches, missing records, alerts/issues/recommendations
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


def _fmt_money(value: float) -> str:
    try:
        return f"${value:,.2f}"
    except Exception:
        return "$0.00"


def _load_csv(contents: Optional[bytes], filename: Optional[str]) -> Optional[pl.DataFrame]:
    if contents is None or filename is None:
        return None
    if not filename.lower().endswith(".csv"):
        return None
    try:
        df = pl.read_csv(io.BytesIO(contents), ignore_errors=True, infer_schema_length=10000)
        return df.with_row_index("row_index")
    except Exception:
        return None


# ----------------------------
# Main agent entrypoint
# ----------------------------

def execute_cross_system_reconciliation_agent(
    primary_contents: Optional[bytes] = None,
    primary_filename: Optional[str] = None,
    secondary_contents: Optional[bytes] = None,
    secondary_filename: Optional[str] = None,
    tertiary_contents: Optional[bytes] = None,
    tertiary_filename: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    start_time = time.time()
    parameters = parameters or {}

    agent_id = "cross-system-reconciliation-agent"
    agent_name = "Cross‑System Reconciliation Agent"

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
    # Load CSVs
    # ----------------------------
    df_primary = _load_csv(primary_contents, primary_filename)
    df_secondary = _load_csv(secondary_contents, secondary_filename)
    df_tertiary = _load_csv(tertiary_contents, tertiary_filename)

    systems = {
        "primary": df_primary,
        "secondary": df_secondary,
        "tertiary": df_tertiary,
    }

    loaded_systems = {k: v for k, v in systems.items() if v is not None}

    if len(loaded_systems) < 2:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": "At least two CSV files are required for reconciliation.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    # ----------------------------
    # Required canonical fields
    # ----------------------------
    required_fields = ["invoice_id", "invoice_date", "vendor_name", "total_amount"]

    for sys_name, df in loaded_systems.items():
        missing = [f for f in required_fields if f not in df.columns]
        if missing:
            issues.append({
                "issue_id": f"missing_fields_{sys_name}",
                "agent_id": agent_id,
                "field_name": ",".join(missing),
                "issue_type": "missing_field",
                "severity": "high",
                "message": f"{sys_name} file missing required fields: {', '.join(missing)}",
            })
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"{sys_name} missing required fields: {', '.join(missing)}",
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "issues": issues,
            }

    # ----------------------------
    # Build unified key index
    # ----------------------------
    def _key(df: pl.DataFrame) -> pl.Series:
        return df["invoice_id"].cast(pl.Utf8, strict=False).str.strip()

    primary_keys = set(_key(df_primary))
    secondary_keys = set(_key(df_secondary)) if df_secondary is not None else set()
    tertiary_keys = set(_key(df_tertiary)) if df_tertiary is not None else set()

    # Missing in system
    missing_in_secondary = sorted(list(primary_keys - secondary_keys))
    missing_in_primary = sorted(list(secondary_keys - primary_keys)) if df_secondary is not None else []

    missing_in_tertiary = []
    if df_tertiary is not None:
        missing_in_tertiary = sorted(list(primary_keys - tertiary_keys))

    # ----------------------------
    # Field‑level mismatches
    # ----------------------------
    mismatch_records = []

    def _compare_field(field: str):
        if df_secondary is None:
            return
        joined = df_primary.join(
            df_secondary,
            left_on="invoice_id",
            right_on="invoice_id",
            how="inner",
            suffix="_sec"
        )
        for row in joined.iter_rows(named=True):
            a = row[field]
            b = row.get(f"{field}_sec")
            if a != b:
                mismatch_records.append({
                    "invoice_id": row["invoice_id"],
                    "field": field,
                    "primary_value": a,
                    "secondary_value": b,
                })

    for f in required_fields:
        _compare_field(f)

    # ----------------------------
    # Reconciliation clusters
    # ----------------------------
    clusters = []

    for inv in sorted(primary_keys):
        cluster = {"invoice_id": inv, "systems": {}}
        for sys_name, df in loaded_systems.items():
            match = df.filter(pl.col("invoice_id") == inv)
            if match.height > 0:
                cluster["systems"][sys_name] = match.to_dicts()
            else:
                cluster["systems"][sys_name] = None
        clusters.append(cluster)

    # ----------------------------
    # Quality scoring
    # ----------------------------
    quality_score = 100.0

    if missing_in_secondary:
        quality_score -= min(30.0, len(missing_in_secondary) * 2)

    if missing_in_primary:
        quality_score -= min(20.0, len(missing_in_primary) * 2)

    if mismatch_records:
        quality_score -= min(30.0, len(mismatch_records) * 1.5)

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
    if missing_in_secondary:
        recommendations.append({
            "recommendation_id": "rec_missing_in_secondary",
            "agent_id": agent_id,
            "field_name": "invoice_id",
            "priority": "high",
            "recommendation": "Invoices exist in primary but not in secondary. Investigate ingestion gaps.",
            "timeline": "immediate",
        })

    if mismatch_records:
        recommendations.append({
            "recommendation_id": "rec_field_mismatches",
            "agent_id": agent_id,
            "field_name": "invoice_fields",
            "priority": "high",
            "recommendation": "Field‑level mismatches detected across systems. Validate source‑of‑truth rules.",
            "timeline": "next sprint",
        })

    # ----------------------------
    # Executive summary
    # ----------------------------
    total_primary = df_primary.height
    missing_sec_count = len(missing_in_secondary)
    mismatch_count = len(mismatch_records)

    executive_summary = [
        {
            "summary_id": "exec_primary_rows",
            "title": "Primary System Rows",
            "value": f"{total_primary:,}",
            "status": "info",
            "description": "Total invoices in the primary system.",
        },
        {
            "summary_id": "exec_missing_secondary",
            "title": "Missing in Secondary",
            "value": f"{missing_sec_count:,}",
            "status": "warning" if missing_sec_count > 0 else "success",
            "description": "Invoices present in primary but missing in secondary.",
        },
        {
            "summary_id": "exec_mismatches",
            "title": "Field‑Level Mismatches",
            "value": f"{mismatch_count:,}",
            "status": "warning" if mismatch_count > 0 else "success",
            "description": "Invoices with inconsistent fields across systems.",
        },
        {
            "summary_id": "exec_quality",
            "title": "Reconciliation Quality",
            "value": f"{quality_score:.1f}",
            "status": quality_status,
            "description": "Overall cross‑system alignment health.",
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
        "missing_in_secondary": missing_in_secondary,
        "missing_in_primary": missing_in_primary,
        "missing_in_tertiary": missing_in_tertiary,
        "mismatch_records": mismatch_records,
        "clusters": clusters[:max_preview_rows],
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
        "primary_rows": total_primary,
        "missing_in_secondary": missing_sec_count,
        "field_mismatches": mismatch_count,
        "quality_score": round(quality_score, 1),
    }

    # ----------------------------
    # AI analysis text
    # ----------------------------
    ai_analysis_text = "\n".join([
        "CROSS‑SYSTEM RECONCILIATION RESULTS:",
        f"- Primary rows: {total_primary:,}",
        f"- Missing in secondary: {missing_sec_count:,}",
        f"- Field mismatches: {mismatch_count:,}",
        f"- Reconciliation quality: {quality_score:.1f} ({quality_status})",
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
