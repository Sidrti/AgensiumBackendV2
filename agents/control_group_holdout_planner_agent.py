"""
Control Group Holdout Planner Agent

Computes per-segment sample sizes and timelines for an imbalanced holdout split,
plus aggregate totals and holdout opportunity cost.

Input: No files required (optional file args ignored)
Output: Segment-level and aggregate holdout planning results following Agensium agent response standard.
"""

import math
import time
from typing import Any, Dict, List, Optional, Tuple


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
        if math.isnan(v) or math.isinf(v):
            return default
    except Exception:
        return default
    if min_value is not None:
        v = max(min_value, v)
    if max_value is not None:
        v = min(max_value, v)
    return v


def _z_alpha_from_confidence(confidence_level: float) -> float:
    # Per task.md constants
    mapping = {
        0.9: 1.645,
        0.95: 1.96,
        0.99: 2.57,
    }
    # Tolerate 90/95/99 as ints too
    if confidence_level >= 2:
        confidence_level = confidence_level / 100.0
    # Snap to closest supported value
    closest = min(mapping.keys(), key=lambda k: abs(k - confidence_level))
    return mapping[closest]


def _z_beta_from_power(power: float) -> float:
    mapping = {
        0.8: 0.841,
        0.9: 1.28,
    }
    if power >= 2:
        power = power / 100.0
    closest = min(mapping.keys(), key=lambda k: abs(k - power))
    return mapping[closest]


def _compute_base_n_per_group(z_alpha: float, z_beta: float, p1: float, p2: float) -> Optional[float]:
    # n = ((Z_alpha + Z_beta)^2 * (p1(1-p1) + p2(1-p2))) / (p1 - p2)^2
    diff = p1 - p2
    if abs(diff) < 1e-12:
        return None

    variance = (p1 * (1 - p1)) + (p2 * (1 - p2))
    numerator = (z_alpha + z_beta) ** 2 * variance
    denominator = diff ** 2

    if denominator <= 0:
        return None

    n = numerator / denominator
    if not math.isfinite(n) or n <= 0:
        return None

    # Keep minimum practical size
    return max(30.0, n)


def _imbalance_factor(p_holdout: float) -> Optional[float]:
    # ImbalanceFactor = (1/p + 1/q) / 4
    if p_holdout <= 0 or p_holdout >= 1:
        return None
    q = 1 - p_holdout
    return ((1 / p_holdout) + (1 / q)) / 4


def _fmt_money(value: float) -> str:
    try:
        return f"${value:,.2f}"
    except Exception:
        return "$0.00"


def execute_control_group_holdout_planner_agent(
    file_contents: Optional[bytes] = None,
    filename: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    start_time = time.time()
    parameters = parameters or {}

    agent_id = "control-group-holdout-planner-agent"
    agent_name = "Control Group Holdout Planner Agent"

    # ----------------------------
    # Parse global parameters
    # ----------------------------
    holdout_ratio = _safe_int(parameters.get("holdout_ratio"), 10, 1, 50)
    confidence_level = _safe_float(parameters.get("confidence_level"), 0.95, 0.0, 0.999999)
    statistical_power = _safe_float(parameters.get("statistical_power"), 0.8, 0.0, 0.999999)

    segment_count = _safe_int(parameters.get("segment_count"), 1, 1, 10)

    excellent_threshold = _safe_int(parameters.get("excellent_threshold"), 90, 0, 100)
    good_threshold = _safe_int(parameters.get("good_threshold"), 75, 0, 100)

    z_alpha = _z_alpha_from_confidence(confidence_level)
    z_beta = _z_beta_from_power(statistical_power)

    p_holdout = holdout_ratio / 100.0
    imbalance = _imbalance_factor(p_holdout)

    # ----------------------------
    # Parse segment parameters (1..10)
    # ----------------------------
    segments_inputs: List[Dict[str, Any]] = []

    for i in range(1, 11):
        seg = {
            "segment_index": i,
            "segment_name": parameters.get(f"segment_{i}_name", f"Segment {i}"),
            "daily_traffic": _safe_int(parameters.get(f"segment_{i}_daily_traffic"), 10000, 1, 10**12),
            "baseline_pct": _safe_float(parameters.get(f"segment_{i}_baseline"), 4.5, 0.0, 100.0),
            "lift_pct": _safe_float(parameters.get(f"segment_{i}_lift"), 8.0, 0.0, 500.0),
            "value": _safe_float(parameters.get(f"segment_{i}_value"), 120.0, 0.0, 10**12),
        }
        segments_inputs.append(seg)

    # ----------------------------
    # Compute per-segment outputs
    # ----------------------------
    segments: List[Dict[str, Any]] = []
    alerts: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    row_level_issues: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []

    total_users_required = 0.0
    total_holdout_cost = 0.0
    max_duration_days = 0.0

    underpowered_segments = 0
    computed_segments = 0

    if imbalance is None:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": "Invalid holdout_ratio; must be between 1 and 50.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    for seg in segments_inputs[:segment_count]:
        name = str(seg["segment_name"]) if seg.get("segment_name") is not None else f"Segment {seg['segment_index']}"
        traffic = seg["daily_traffic"]
        baseline_pct = seg["baseline_pct"]
        lift_pct = seg["lift_pct"]
        value = seg["value"]

        p1 = baseline_pct / 100.0
        lift_dec = lift_pct / 100.0
        p2 = p1 * (1 + lift_dec)
        p2 = min(max(p2, 0.0), 0.999999)

        segment_out: Dict[str, Any] = {
            "segment_index": seg["segment_index"],
            "segment_name": name,
            "inputs": {
                "daily_traffic": traffic,
                "baseline_pct": baseline_pct,
                "lift_pct": lift_pct,
                "value": value,
            },
            "constants": {
                "z_alpha": z_alpha,
                "z_beta": z_beta,
                "holdout_ratio_pct": holdout_ratio,
                "p_holdout": p_holdout,
                "q_treatment": 1 - p_holdout,
                "imbalance_factor": imbalance,
            },
            "calculations": {},
            "warnings": [],
            "status": "success",
        }

        # Validate segment
        if traffic <= 0:
            segment_out["status"] = "error"
            segment_out["error"] = "daily_traffic must be > 0"
            issues.append({
                "issue_id": f"issue_invalid_traffic_seg_{seg['segment_index']}",
                "agent_id": agent_id,
                "field_name": f"segment_{seg['segment_index']}_daily_traffic",
                "issue_type": "invalid_input",
                "severity": "high",
                "message": f"{name}: daily traffic must be > 0.",
            })
            segments.append(segment_out)
            continue

        if p1 <= 0 or lift_dec <= 0:
            segment_out["status"] = "error"
            segment_out["error"] = "baseline and lift must be > 0 to compute sample size"
            issues.append({
                "issue_id": f"issue_no_effect_seg_{seg['segment_index']}",
                "agent_id": agent_id,
                "field_name": f"segment_{seg['segment_index']}",
                "issue_type": "insufficient_effect",
                "severity": "high",
                "message": f"{name}: baseline ({baseline_pct}%) and lift ({lift_pct}%) must both be > 0 to compute sample size.",
            })
            segments.append(segment_out)
            continue

        n = _compute_base_n_per_group(z_alpha=z_alpha, z_beta=z_beta, p1=p1, p2=p2)
        if n is None:
            segment_out["status"] = "error"
            segment_out["error"] = "Unable to compute base sample size (n). Check baseline/lift."
            issues.append({
                "issue_id": f"issue_sample_calc_seg_{seg['segment_index']}",
                "agent_id": agent_id,
                "field_name": f"segment_{seg['segment_index']}",
                "issue_type": "calculation_error",
                "severity": "high",
                "message": f"{name}: sample size could not be computed (baseline={baseline_pct}%, lift={lift_pct}%).",
            })
            segments.append(segment_out)
            continue

        # Total required users with imbalanced split
        N = (n * 2.0) * imbalance

        duration_days = N / float(traffic)
        holdout_users = N * p_holdout

        holdout_cost = holdout_users * (p1 * lift_dec) * value

        segment_out["calculations"] = {
            "p1": p1,
            "p2": p2,
            "n_per_group_50_50": float(n),
            "total_users_required": float(N),
            "duration_days": float(duration_days),
            "holdout_users": float(holdout_users),
            "holdout_cost": float(holdout_cost),
        }

        # Warning: small control / under-powered
        if holdout_users < n:
            underpowered_segments += 1
            segment_out["warnings"].append("Small control: holdout users < required per-group n")
            alerts.append({
                "alert_id": f"alert_underpowered_seg_{seg['segment_index']}",
                "severity": "high",
                "category": "power",
                "message": f"{name}: Small control group. Holdout users ({holdout_users:,.0f}) is less than required n per group ({n:,.0f}).",
                "affected_fields_count": 1,
                "recommendation": "Increase holdout ratio, increase traffic, or accept lower confidence/power.",
            })
            row_level_issues.append({
                "row_index": None,
                "column": "global",
                "issue_type": "small_control",
                "severity": "warning",
                "message": f"{name}: Holdout users ({holdout_users:,.0f}) < n per group ({n:,.0f}).",
                "value": None,
            })

        # Aggregate
        computed_segments += 1
        total_users_required += N
        total_holdout_cost += holdout_cost
        max_duration_days = max(max_duration_days, duration_days)

        segments.append(segment_out)

    # ----------------------------
    # Aggregate outputs
    # ----------------------------
    # NOTE: All Agensium agents follow status = success|error.
    # If we couldn't compute any segment, return an error response without a data payload.
    if computed_segments == 0:
        return {
            "status": "error",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "error": "No segments could be computed. Please check baseline/lift/traffic inputs.",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    # Quality score heuristic (simple, like other agents)
    quality_score = 100.0
    if computed_segments == 0:
        quality_score = 0.0
    else:
        if underpowered_segments > 0:
            quality_score -= min(60.0, underpowered_segments * 10.0)
        if holdout_ratio < 5:
            quality_score -= 10.0

    quality_score = max(0.0, min(100.0, quality_score))
    if quality_score >= excellent_threshold:
        quality_status = "excellent"
    elif quality_score >= good_threshold:
        quality_status = "good"
    else:
        quality_status = "needs_improvement"

    # Recommendations
    if underpowered_segments > 0:
        recommendations.append({
            "recommendation_id": "rec_increase_control",
            "agent_id": agent_id,
            "field_name": "holdout_ratio",
            "priority": "high",
            "recommendation": "One or more segments have a small control group. Consider increasing holdout_ratio or consolidating segments.",
            "timeline": "immediate",
        })

    recommendations.append({
        "recommendation_id": "rec_validate_assumptions",
        "agent_id": agent_id,
        "field_name": "lift",
        "priority": "medium",
        "recommendation": "Validate baseline and expected lift assumptions with historical data; sample size is highly sensitive to small lifts.",
        "timeline": "before launch",
    })

    # Executive summary cards
    executive_summary = [
        {
            "summary_id": "exec_total_users_required",
            "title": "Total Users Required",
            "value": f"{total_users_required:,.0f}" if computed_segments else "N/A",
            "status": "excellent" if computed_segments and underpowered_segments == 0 else "warning" if computed_segments else "critical",
            "description": "Sum of total required users across all computed segments.",
        },
        {
            "summary_id": "exec_max_duration",
            "title": "Max Duration (Days)",
            "value": f"{max_duration_days:,.1f}" if computed_segments else "N/A",
            "status": "good" if computed_segments and max_duration_days <= 30 else "warning" if computed_segments else "critical",
            "description": "Duration of the slowest segment (parallel bottleneck).",
        },
        {
            "summary_id": "exec_total_holdout_cost",
            "title": "Total Holdout Cost",
            "value": _fmt_money(total_holdout_cost) if computed_segments else "N/A",
            "status": "info",
            "description": "Estimated opportunity cost of keeping users in control instead of treatment.",
        },
        {
            "summary_id": "exec_underpowered_segments",
            "title": "Under-Powered Segments",
            "value": f"{underpowered_segments}",
            "status": "success" if underpowered_segments == 0 else "warning",
            "description": "Segments where holdout users are smaller than required n per group.",
        },
    ]

    # Issue summary
    row_level_issues = row_level_issues[:1000]
    issue_summary = {
        "total_issues": len(row_level_issues),
        "by_type": {},
        "by_severity": {},
        "affected_rows": 0,
        "affected_columns": sorted(list({i.get("column") for i in row_level_issues if i.get("column")})),
    }
    for i in row_level_issues:
        t = i.get("issue_type", "unknown")
        s = i.get("severity", "info")
        issue_summary["by_type"][t] = issue_summary["by_type"].get(t, 0) + 1
        issue_summary["by_severity"][s] = issue_summary["by_severity"].get(s, 0) + 1

    data: Dict[str, Any] = {
        "global_inputs": {
            "holdout_ratio": holdout_ratio,
            "confidence_level": confidence_level,
            "statistical_power": statistical_power,
            "segment_count": segment_count,
        },
        "constants": {
            "z_alpha": z_alpha,
            "z_beta": z_beta,
            "p_holdout": p_holdout,
            "imbalance_factor": imbalance,
        },
        "segments": segments,
        "aggregate": {
            "total_users_required": float(total_users_required) if computed_segments else None,
            "max_duration_days": float(max_duration_days) if computed_segments else None,
            "total_holdout_cost": float(total_holdout_cost) if computed_segments else None,
            "computed_segments": computed_segments,
            "underpowered_segments": underpowered_segments,
        },
        "quality": {
            "plan_quality_score": round(quality_score, 1),
            "quality_status": quality_status,
        },
    }

    # Three-object parameter structure
    defaults: Dict[str, Any] = {
        "holdout_ratio": 10,
        "confidence_level": 0.95,
        "statistical_power": 0.8,
        "segment_count": 1,
        "excellent_threshold": 90,
        "good_threshold": 75,
    }
    for i in range(1, 11):
        defaults[f"segment_{i}_name"] = f"Segment {i}"
        defaults[f"segment_{i}_daily_traffic"] = 10000
        defaults[f"segment_{i}_baseline"] = 4.5
        defaults[f"segment_{i}_lift"] = 8
        defaults[f"segment_{i}_value"] = 120

    overrides: Dict[str, Any] = {
        "holdout_ratio": parameters.get("holdout_ratio"),
        "confidence_level": parameters.get("confidence_level"),
        "statistical_power": parameters.get("statistical_power"),
        "segment_count": parameters.get("segment_count"),
        "excellent_threshold": parameters.get("excellent_threshold"),
        "good_threshold": parameters.get("good_threshold"),
    }
    for i in range(1, 11):
        overrides[f"segment_{i}_name"] = parameters.get(f"segment_{i}_name")
        overrides[f"segment_{i}_daily_traffic"] = parameters.get(f"segment_{i}_daily_traffic")
        overrides[f"segment_{i}_baseline"] = parameters.get(f"segment_{i}_baseline")
        overrides[f"segment_{i}_lift"] = parameters.get(f"segment_{i}_lift")
        overrides[f"segment_{i}_value"] = parameters.get(f"segment_{i}_value")

    final_params: Dict[str, Any] = {
        "holdout_ratio": holdout_ratio,
        "confidence_level": confidence_level,
        "statistical_power": statistical_power,
        "segment_count": segment_count,
        "excellent_threshold": excellent_threshold,
        "good_threshold": good_threshold,
    }
    for i in range(1, 11):
        final_params[f"segment_{i}_name"] = segments_inputs[i - 1]["segment_name"]
        final_params[f"segment_{i}_daily_traffic"] = segments_inputs[i - 1]["daily_traffic"]
        final_params[f"segment_{i}_baseline"] = segments_inputs[i - 1]["baseline_pct"]
        final_params[f"segment_{i}_lift"] = segments_inputs[i - 1]["lift_pct"]
        final_params[f"segment_{i}_value"] = segments_inputs[i - 1]["value"]

    data["defaults"] = defaults
    data["overrides"] = overrides
    data["parameters"] = final_params

    ai_analysis_text = "\n".join([
        "CONTROL GROUP HOLDOUT PLANNER RESULTS:",
        f"- Holdout ratio: {holdout_ratio}%",
        f"- Confidence level: {confidence_level*100:.0f}%",
        f"- Statistical power: {statistical_power*100:.0f}%",
        f"- Segments planned: {segment_count} (computed: {computed_segments})",
        f"- Total users required: {total_users_required:,.0f}" if computed_segments else "- Total users required: N/A",
        f"- Max duration: {max_duration_days:,.1f} days" if computed_segments else "- Max duration: N/A",
        f"- Total holdout cost: {_fmt_money(total_holdout_cost)}" if computed_segments else "- Total holdout cost: N/A",
        f"- Under-powered segments: {underpowered_segments}",
    ])

    return {
        "status": "success",
        "agent_id": agent_id,
        "agent_name": agent_name,
        "execution_time_ms": int((time.time() - start_time) * 1000),
        "summary_metrics": {
            "segments_requested": segment_count,
            "segments_computed": computed_segments,
            "underpowered_segments": underpowered_segments,
            "total_users_required": int(round(total_users_required)) if computed_segments else None,
            "max_duration_days": round(max_duration_days, 2) if computed_segments else None,
            "total_holdout_cost": round(total_holdout_cost, 2) if computed_segments else None,
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
