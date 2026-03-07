"""
Payment Exception Routing Agent

Node‑07: Workflow Decision Engine

Consumes upstream signals from the duplicate‑invoice pipeline and assigns each invoice
to a routing category:
- AUTO_APPROVE
- AUTO_HOLD
- REQUIRE_REVIEW
- ESCALATE

Input: Single CSV file (normalized invoice table)
       Optional JSON-like signals from previous agents (exact, fuzzy, semantic, behavioral, reconciliation)

Output: Routing decisions, risk scores, workflow actions, alerts/issues/recommendations
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


def _risk_bucket(score: float) -> str:
    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _route_from_risk(score: float) -> str:
    if score >= 80:
        return "ESCALATE"
    if score >= 50:
        return "REQUIRE_REVIEW"
    if score >= 20:
        return "AUTO_HOLD"
    return "AUTO_APPROVE"


# ----------------------------
# Main agent entrypoint
# ----------------------------

def execute_payment_exception_routing_agent(
    file_contents: Optional[bytes] = None,
    filename: Optional[str] = None,
    signals: Optional[Dict[str, Any]] = None,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    start_time = time.time()
    parameters = parameters or {}
    signals = signals or {}

    agent_id = "payment-exception-routing-agent"
    agent_name = "Payment Exception Routing Agent"

    excellent_threshold = _safe_int(parameters.get("excellent_threshold"), 90)
    good_threshold = _safe_int(parameters.get("good_threshold"), 75)
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
            "error": "Routing agent requires a normalized invoice CSV file.",
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

    if df.height == 0:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": "Input file is empty.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    df = df.with_row_index("row_index")

    # ----------------------------
    # Required fields
    # ----------------------------
    required_fields
