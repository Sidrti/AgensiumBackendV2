"""
Experimental Design Agent

Calculates statistically valid A/B test sample sizes using baseline rate,
minimum detectable lift, and significance level to prevent underpowered experiments.

Input: CSV file (optional primary for population size reference)
Output: Required sample sizes for control/test groups, feasibility warnings,
        alerts/issues/recommendations following Agensium agent response standard.
"""

import io
import time
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import polars as pl

from .agent_utils import normalize_column_names


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


def _cap_list(items: List[Dict[str, Any]], limit: int = 1000) -> List[Dict[str, Any]]:
    """Cap list to specified limit."""
    return items[:limit] if len(items) > limit else items


def _normal_cdf(z: float) -> float:
    """Calculate the cumulative distribution function of the standard normal distribution."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _normal_ppf(p: float) -> float:
    """Calculate the percent point function (inverse CDF) of the standard normal distribution."""
    # Approximation using Abramowitz and Stegun formula 26.2.23
    if p <= 0:
        return float('-inf')
    if p >= 1:
        return float('inf')
    if p == 0.5:
        return 0.0
    
    # Constants for approximation
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    
    if p < 0.5:
        t = math.sqrt(-2 * math.log(p))
        z = -((c0 + c1 * t + c2 * t ** 2) / (1 + d1 * t + d2 * t ** 2 + d3 * t ** 3) - t)
    else:
        t = math.sqrt(-2 * math.log(1 - p))
        z = (c0 + c1 * t + c2 * t ** 2) / (1 + d1 * t + d2 * t ** 2 + d3 * t ** 3) - t
    
    return z


def _calculate_sample_size_proportions(
    baseline_rate: float,
    min_detectable_lift_pct: float,
    significance_level: float,
    power: float = 0.8
) -> Dict[str, Any]:
    """
    Calculate required sample size for A/B test using two-tailed test for proportions.
    
    Uses the Evan Miller / standard power analysis approach:
    n = (Z_alpha/2 + Z_beta)^2 * (p1(1-p1) + p2(1-p2)) / (p2 - p1)^2
    
    Args:
        baseline_rate: Control group conversion rate (p1), 0-1
        min_detectable_lift_pct: Minimum detectable lift as percentage (e.g., 5 = 5%)
        significance_level: Confidence level (0.9, 0.95, or 0.99)
        power: Statistical power (default 0.8 = 80%)
    
    Returns:
        Dictionary with sample size calculations
    """
    # Convert lift percentage to absolute difference
    p1 = baseline_rate
    lift_decimal = min_detectable_lift_pct / 100.0  # e.g., 5% -> 0.05
    p2 = p1 * (1 + lift_decimal)  # Expected treatment rate
    
    # Ensure p2 is within bounds
    p2 = min(p2, 0.999)
    
    # Calculate alpha (two-tailed) and beta
    alpha = 1 - significance_level
    beta = 1 - power
    
    # Z-scores
    z_alpha = _normal_ppf(1 - alpha / 2)  # Two-tailed
    z_beta = _normal_ppf(1 - beta)
    
    # Effect size (absolute difference)
    effect_size = abs(p2 - p1)
    
    if effect_size < 1e-10:
        return {
            "error": "Effect size too small to detect",
            "sample_size_per_group": float('inf'),
            "total_sample_size": float('inf')
        }
    
    # Pooled standard error approach (commonly used)
    p_pooled = (p1 + p2) / 2
    se_pooled = math.sqrt(2 * p_pooled * (1 - p_pooled))
    
    # Standard error under alternative
    se_alt = math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    
    # Sample size calculation (per group)
    numerator = (z_alpha * se_pooled + z_beta * se_alt) ** 2
    denominator = effect_size ** 2
    
    n_per_group = math.ceil(numerator / denominator)
    
    # Minimum practical sample size
    n_per_group = max(n_per_group, 30)
    
    return {
        "control_group_size": n_per_group,
        "test_group_size": n_per_group,
        "total_sample_size": n_per_group * 2,
        "expected_control_rate": round(p1, 6),
        "expected_treatment_rate": round(p2, 6),
        "absolute_effect_size": round(effect_size, 6),
        "relative_lift_pct": round(min_detectable_lift_pct, 2),
        "z_alpha": round(z_alpha, 4),
        "z_beta": round(z_beta, 4),
        "statistical_power": round(power, 2),
        "significance_level": round(significance_level, 2),
        "alpha": round(alpha, 4)
    }


def execute_experimental_design_agent(
    file_contents: Optional[bytes],
    filename: Optional[str],
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute experimental design analysis."""

    start_time = time.time()
    parameters = parameters or {}

    # ----------------------------
    # Parse parameters (defaults aligned to analyze_my_data_tool.json)
    # ----------------------------
    significance_level = _safe_float(parameters.get("significance_level"), 0.95, 0.8, 0.999)
    baseline_rate = _safe_float(parameters.get("baseline_rate"), 0.02, 0.0001, 0.9999)
    min_detectable_lift = _safe_float(parameters.get("min_detectable_lift"), 5.0, 0.1, 100.0)
    total_population_size = parameters.get("total_population_size")
    
    if total_population_size is not None:
        total_population_size = _safe_int(total_population_size, 0, 0, 100000000)
        if total_population_size == 0:
            total_population_size = None
    
    excellent_threshold = _safe_int(parameters.get("excellent_threshold"), 90, 0, 100)
    good_threshold = _safe_int(parameters.get("good_threshold"), 75, 0, 100)

    agent_id = "experimental-design-agent"
    agent_name = "Experimental Design Agent"

    try:
        # ----------------------------
        # Optional: Load CSV for population size inference
        # ----------------------------
        dataset_population = None
        dataset_stats = {}
        row_level_issues: List[Dict[str, Any]] = []
        
        if file_contents and filename:
            if filename.lower().endswith(".csv"):
                try:
                    df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
                    dataset_population = df.height
                    dataset_stats = {
                        "rows": df.height,
                        "columns": df.width,
                        "column_names": df.columns[:20],  # Cap for response size
                    }
                    
                    # If no population size provided, use dataset size
                    if total_population_size is None and dataset_population > 0:
                        total_population_size = dataset_population
                        
                except Exception as e:
                    row_level_issues.append({
                        "row_index": None,
                        "column": None,
                        "issue_type": "file_parse_warning",
                        "severity": "low",
                        "message": f"Could not parse CSV for population inference: {str(e)}",
                        "value": filename,
                    })

        # ----------------------------
        # Calculate sample sizes
        # ----------------------------
        sample_calc = _calculate_sample_size_proportions(
            baseline_rate=baseline_rate,
            min_detectable_lift_pct=min_detectable_lift,
            significance_level=significance_level,
            power=0.8  # Standard 80% power
        )
        
        if "error" in sample_calc:
            return {
                "status": "error",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": sample_calc["error"],
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }
        
        control_size = sample_calc["control_group_size"]
        test_size = sample_calc["test_group_size"]
        total_required = sample_calc["total_sample_size"]

        # ----------------------------
        # Feasibility assessment
        # ----------------------------
        is_feasible = True
        feasibility_status = "feasible"
        feasibility_message = "Experiment is feasible with the available population."
        feasibility_utilization = None
        
        if total_population_size is not None and total_population_size > 0:
            feasibility_utilization = round((total_required / total_population_size) * 100, 2)
            
            if total_required > total_population_size:
                is_feasible = False
                feasibility_status = "infeasible"
                shortfall = total_required - total_population_size
                feasibility_message = f"Required sample size ({total_required:,}) exceeds available population ({total_population_size:,}) by {shortfall:,} users."
            elif feasibility_utilization > 80:
                feasibility_status = "marginal"
                feasibility_message = f"Experiment requires {feasibility_utilization}% of available population. Consider reducing lift requirement or increasing population."
            elif feasibility_utilization > 50:
                feasibility_status = "tight"
                feasibility_message = f"Experiment requires {feasibility_utilization}% of available population. Feasible but leaves limited room for error."
        else:
            feasibility_message = "No population size provided. Please verify you have sufficient audience before running the experiment."

        # ----------------------------
        # Quality score
        # ----------------------------
        # Score based on: feasibility, reasonable parameters
        quality_score = 100.0
        
        if not is_feasible:
            quality_score -= 50
        elif feasibility_status == "marginal":
            quality_score -= 25
        elif feasibility_status == "tight":
            quality_score -= 10
            
        if baseline_rate < 0.005:
            quality_score -= 10  # Very low baseline makes detection harder
        if min_detectable_lift < 2:
            quality_score -= 10  # Very small lift is hard to detect reliably
        if min_detectable_lift > 50:
            quality_score -= 5  # Very large lift may indicate unrealistic expectations
            
        quality_score = max(0.0, min(100.0, quality_score))
        
        if quality_score >= excellent_threshold:
            quality_status = "excellent"
        elif quality_score >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"

        # ----------------------------
        # Alerts
        # ----------------------------
        alerts: List[Dict[str, Any]] = []
        
        if not is_feasible:
            alerts.append({
                "alert_id": "alert_experiment_infeasible",
                "severity": "critical",
                "category": "feasibility",
                "message": f"Experiment is NOT feasible. Required sample ({total_required:,}) exceeds population ({total_population_size:,}).",
                "affected_fields_count": 0,
                "recommendation": "Lower the minimum detectable lift, reduce confidence level, or acquire more audience.",
            })
        elif feasibility_status == "marginal":
            alerts.append({
                "alert_id": "alert_experiment_marginal",
                "severity": "high",
                "category": "feasibility",
                "message": f"Experiment feasibility is marginal. Requires {feasibility_utilization}% of available population.",
                "affected_fields_count": 0,
                "recommendation": "Consider reducing lift requirement or extending test duration to accumulate more users.",
            })
        
        if baseline_rate < 0.005:
            alerts.append({
                "alert_id": "alert_low_baseline",
                "severity": "medium",
                "category": "parameter_quality",
                "message": f"Baseline rate ({baseline_rate*100:.2f}%) is very low, requiring larger samples for reliable detection.",
                "affected_fields_count": 1,
                "recommendation": "Ensure baseline rate is accurate. Consider focusing on higher-baseline metrics.",
            })
        
        if total_population_size is None:
            alerts.append({
                "alert_id": "alert_no_population",
                "severity": "medium",
                "category": "data_completeness",
                "message": "No population size provided. Cannot assess experiment feasibility.",
                "affected_fields_count": 1,
                "recommendation": "Provide total_population_size parameter or upload a dataset for automatic inference.",
            })

        # ----------------------------
        # Issues
        # ----------------------------
        issues: List[Dict[str, Any]] = []
        
        issues.append({
            "issue_id": "issue_experiment_design_quality",
            "agent_id": agent_id,
            "field_name": "experiment_design",
            "issue_type": "design_assessment",
            "severity": "low" if quality_status in ["excellent", "good"] else "medium",
            "message": f"Experiment design quality score: {quality_score:.1f}/100 ({quality_status}).",
        })
        
        if min_detectable_lift > 30:
            issues.append({
                "issue_id": "issue_high_lift_expectation",
                "agent_id": agent_id,
                "field_name": "min_detectable_lift",
                "issue_type": "parameter_warning",
                "severity": "low",
                "message": f"Minimum detectable lift ({min_detectable_lift}%) is high. You may be missing smaller but meaningful effects.",
            })
        
        if significance_level < 0.9:
            issues.append({
                "issue_id": "issue_low_confidence",
                "agent_id": agent_id,
                "field_name": "significance_level",
                "issue_type": "parameter_warning",
                "severity": "medium",
                "message": f"Significance level ({significance_level}) is below standard (0.95). Higher false positive risk.",
            })

        # ----------------------------
        # Recommendations
        # ----------------------------
        recommendations: List[Dict[str, Any]] = []
        
        if not is_feasible:
            recommendations.append({
                "recommendation_id": "rec_reduce_lift",
                "agent_id": agent_id,
                "field_name": "min_detectable_lift",
                "priority": "high",
                "recommendation": f"Reduce minimum detectable lift from {min_detectable_lift}% to a higher value (e.g., {min(min_detectable_lift * 1.5, 20):.0f}%) to reduce required sample size.",
                "timeline": "immediate",
            })
            recommendations.append({
                "recommendation_id": "rec_reduce_confidence",
                "agent_id": agent_id,
                "field_name": "significance_level",
                "priority": "medium",
                "recommendation": "Consider using 90% confidence instead of 95% if the business risk of false positives is acceptable.",
                "timeline": "immediate",
            })
        
        recommendations.append({
            "recommendation_id": "rec_experiment_duration",
            "agent_id": agent_id,
            "field_name": "experiment_planning",
            "priority": "medium",
            "recommendation": f"Plan experiment duration based on required {total_required:,} users. If daily traffic is N, run for at least {total_required}/N days plus buffer.",
            "timeline": "before launch",
        })
        
        recommendations.append({
            "recommendation_id": "rec_randomization",
            "agent_id": agent_id,
            "field_name": "experiment_execution",
            "priority": "medium",
            "recommendation": "Ensure proper randomization using user ID hashing or dedicated experimentation platform.",
            "timeline": "before launch",
        })
        
        recommendations.append({
            "recommendation_id": "rec_multiple_metrics",
            "agent_id": agent_id,
            "field_name": "metrics",
            "priority": "low",
            "recommendation": "Track secondary metrics (engagement, revenue) alongside primary conversion metric to understand full impact.",
            "timeline": "1-2 weeks",
        })

        # ----------------------------
        # Executive summary
        # ----------------------------
        executive_summary = [
            {
                "summary_id": "exec_experiment_control_size",
                "title": "Control Group Size",
                "value": f"{control_size:,}",
                "status": "good",
                "description": f"Required control group sample size for {significance_level*100:.0f}% confidence.",
            },
            {
                "summary_id": "exec_experiment_test_size",
                "title": "Test Group Size",
                "value": f"{test_size:,}",
                "status": "good",
                "description": f"Required test group sample size to detect {min_detectable_lift}% lift.",
            },
            {
                "summary_id": "exec_experiment_total",
                "title": "Total Sample Required",
                "value": f"{total_required:,}",
                "status": "excellent" if is_feasible else "critical",
                "description": f"Total users needed for statistically valid A/B test.",
            },
            {
                "summary_id": "exec_experiment_feasibility",
                "title": "Feasibility",
                "value": feasibility_status.upper(),
                "status": "excellent" if is_feasible and feasibility_status == "feasible" else "warning" if feasibility_status in ["marginal", "tight"] else "critical",
                "description": feasibility_message,
            },
        ]
        
        if feasibility_utilization is not None:
            executive_summary.append({
                "summary_id": "exec_experiment_utilization",
                "title": "Population Utilization",
                "value": f"{feasibility_utilization}%",
                "status": "excellent" if feasibility_utilization < 30 else "good" if feasibility_utilization < 60 else "warning",
                "description": f"Percentage of available population required for the experiment.",
            })

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
            "experiment_design": {
                "baseline_rate": round(baseline_rate, 6),
                "baseline_rate_pct": round(baseline_rate * 100, 4),
                "min_detectable_lift_pct": round(min_detectable_lift, 2),
                "significance_level": round(significance_level, 2),
                "confidence_pct": round(significance_level * 100, 0),
                "statistical_power": 0.8,
                "power_pct": 80.0,
                "test_type": "two_tailed",
            },
            "sample_size_calculation": {
                "control_group_size": int(control_size),
                "test_group_size": int(test_size),
                "total_sample_size": int(total_required),
                "expected_control_rate": sample_calc["expected_control_rate"],
                "expected_treatment_rate": sample_calc["expected_treatment_rate"],
                "absolute_effect_size": sample_calc["absolute_effect_size"],
                "z_alpha": sample_calc["z_alpha"],
                "z_beta": sample_calc["z_beta"],
            },
            "feasibility": {
                "is_feasible": is_feasible,
                "status": feasibility_status,
                "message": feasibility_message,
                "population_size": total_population_size,
                "utilization_pct": feasibility_utilization,
            },
            "quality": {
                "design_quality_score": round(quality_score, 1),
                "quality_status": quality_status,
            },
            "dataset_info": dataset_stats if dataset_stats else None,
            "defaults": {
                "significance_level": 0.95,
                "baseline_rate": 0.02,
                "min_detectable_lift": 5.0,
                "total_population_size": None,
                "excellent_threshold": 90,
                "good_threshold": 75
            },
            "overrides": {
                "significance_level": parameters.get("significance_level"),
                "baseline_rate": parameters.get("baseline_rate"),
                "min_detectable_lift": parameters.get("min_detectable_lift"),
                "total_population_size": parameters.get("total_population_size"),
                "excellent_threshold": parameters.get("excellent_threshold"),
                "good_threshold": parameters.get("good_threshold")
            },
            "parameters": {
                "significance_level": significance_level,
                "baseline_rate": baseline_rate,
                "min_detectable_lift": min_detectable_lift,
                "total_population_size": total_population_size,
                "excellent_threshold": excellent_threshold,
                "good_threshold": good_threshold
            }
        }

        ai_analysis_text = "\n".join([
            "EXPERIMENTAL DESIGN RESULTS:",
            f"- Baseline conversion rate: {baseline_rate*100:.2f}%",
            f"- Minimum detectable lift: {min_detectable_lift}%",
            f"- Confidence level: {significance_level*100:.0f}%",
            f"- Statistical power: 80%",
            f"- Required control group: {control_size:,} users",
            f"- Required test group: {test_size:,} users",
            f"- Total sample required: {total_required:,} users",
            f"- Feasibility: {feasibility_status.upper()} - {feasibility_message}",
            f"- Design quality score: {quality_score:.1f}/100 ({quality_status})",
        ])

        return {
            "status": "success",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "control_group_size": int(control_size),
                "test_group_size": int(test_size),
                "total_sample_size": int(total_required),
                "is_feasible": is_feasible,
                "population_size": total_population_size,
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
