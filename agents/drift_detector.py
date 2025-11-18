"""
Drift Detector Agent

Detects changes (drift) between baseline and current datasets.
Input: Baseline file and primary file
Output: Uniform drift detection structure matching API specification
"""

import pandas as pd
import numpy as np
import io
import time
from typing import Dict, Any, Optional
from scipy.stats import ks_2samp, chi2_contingency, wasserstein_distance


def detect_drift(
    baseline_contents: bytes,
    baseline_filename: str,
    current_contents: bytes,
    current_filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Detect drift between baseline and current datasets.
    
    Args:
        baseline_contents: Baseline file bytes
        baseline_filename: Baseline filename
        current_contents: Current file bytes (primary)
        current_filename: Current filename
        parameters: Agent parameters matching tool.json (statistical_test, significance_level, min_sample_size)
        
    Returns:
        Uniform output structure matching API_SPECIFICATION.js response format
    """
    
    start_time = time.time()
    parameters = parameters or {}
    
    # Get parameters with defaults (matching tool.json)
    statistical_test = parameters.get("statistical_test", "kolmogorov_smirnov")
    significance_level = parameters.get("significance_level", 0.05)
    min_sample_size = parameters.get("min_sample_size", 100)
    
    try:
        # Read files
        def read_file(contents, filename):
            if filename.endswith('.csv'):
                return pd.read_csv(io.BytesIO(contents))
            elif filename.endswith('.json'):
                return pd.read_json(io.BytesIO(contents))
            elif filename.endswith(('.xlsx', '.xls')):
                return pd.read_excel(io.BytesIO(contents))
            else:
                raise ValueError(f"Unsupported file format: {filename}")
        
        baseline_df = read_file(baseline_contents, baseline_filename)
        current_df = read_file(current_contents, current_filename)
        
        # Detect column-level drift
        field_drift_details = []
        drift_detected_count = 0
        drift_severity_high = 0
        drift_severity_medium = 0
        drift_severity_low = 0
        psi_scores = []
        
        # Check for missing/new columns
        baseline_cols = set(baseline_df.columns)
        current_cols = set(current_df.columns)
        
        # Common columns - check for data distribution drift
        common_cols = baseline_cols & current_cols
        
        for col in common_cols:
            baseline_col = baseline_df[col].dropna()
            current_col = current_df[col].dropna()
            
            # Skip if insufficient sample size
            if len(baseline_col) < min_sample_size or len(current_col) < min_sample_size:
                continue
            
            # Get statistics
            if baseline_col.dtype in ['int64', 'float64', 'int32', 'float32']:
                # Numeric field drift detection
                baseline_mean = float(baseline_col.mean())
                baseline_median = float(baseline_col.median())
                baseline_std = float(baseline_col.std())
                baseline_min = float(baseline_col.min())
                baseline_max = float(baseline_col.max())
                
                current_mean = float(current_col.mean())
                current_median = float(current_col.median())
                current_std = float(current_col.std())
                current_min = float(current_col.min())
                current_max = float(current_col.max())
                
                # Calculate statistical metrics
                change_in_mean = abs(current_mean - baseline_mean)
                change_in_variance = abs(current_std - baseline_std)
                change_in_median = abs(current_median - baseline_median)
                
                # Apply statistical test
                drift_score = 0
                p_value = 1.0
                
                if statistical_test == "kolmogorov_smirnov":
                    statistic, p_value = ks_2samp(baseline_col, current_col)
                    drift_score = float(statistic)
                elif statistical_test == "wasserstein":
                    drift_score = float(wasserstein_distance(baseline_col, current_col))
                    p_value = 0.01 if drift_score > 0.3 else 0.99
                
                # Calculate PSI (Population Stability Index)
                psi_score = _calculate_psi(baseline_col, current_col)
                psi_scores.append(psi_score)
                
                # JS Divergence approximation
                js_divergence = _calculate_js_divergence(baseline_col, current_col)
                
                # Wasserstein distance
                wasserstein_dist = float(wasserstein_distance(baseline_col, current_col)) if len(baseline_col) > 0 and len(current_col) > 0 else 0
                
                drift_detected = p_value < significance_level or psi_score > 0.1
                severity = "high" if psi_score > 0.25 else "medium" if psi_score > 0.1 else "low"
                
                if drift_detected:
                    drift_detected_count += 1
                    if severity == "high":
                        drift_severity_high += 1
                    elif severity == "medium":
                        drift_severity_medium += 1
                    else:
                        drift_severity_low += 1
                
                field_drift_details.append({
                    "field_id": col,
                    "field_name": col,
                    "baseline_statistics": {
                        "mean": baseline_mean,
                        "median": baseline_median,
                        "stddev": baseline_std,
                        "min": baseline_min,
                        "max": baseline_max,
                        "distribution": "normal"
                    },
                    "current_statistics": {
                        "mean": current_mean,
                        "median": current_median,
                        "stddev": current_std,
                        "min": current_min,
                        "max": current_max,
                        "distribution": "normal"
                    },
                    "drift_analysis": {
                        "drift_detected": drift_detected,
                        "drift_type": "distribution_shift",
                        "severity": severity,
                        "statistical_test": statistical_test,
                        "p_value": round(p_value, 6),
                        "psi_score": round(psi_score, 4),
                        "js_divergence": round(js_divergence, 6),
                        "wasserstein_distance": round(wasserstein_dist, 4),
                        "change_in_mean": round(change_in_mean, 4),
                        "change_in_variance": round(change_in_variance, 4),
                        "change_in_median": round(change_in_median, 4)
                    },
                    "drift_interpretation": {
                        "message": f"Distribution {'has shifted significantly' if drift_detected else 'is stable'} from baseline",
                        "explanation": f"Mean {'increased' if current_mean > baseline_mean else 'decreased'} by {change_in_mean:.2f} units",
                        "business_impact": f"Model predictions may be {'biased' if drift_detected else 'stable'} with {'this' if drift_detected else 'the'} data distribution"
                    },
                    "issue_severity": severity if drift_detected else "low"
                })
            else:
                # Categorical field drift detection
                baseline_dist = baseline_col.value_counts(normalize=True)
                current_dist = current_col.value_counts(normalize=True)
                
                # PSI for categorical
                psi_score = _calculate_psi_categorical(baseline_dist, current_dist)
                psi_scores.append(psi_score)
                
                drift_detected = psi_score > 0.1
                severity = "high" if psi_score > 0.25 else "medium" if psi_score > 0.1 else "low"
                
                if drift_detected:
                    drift_detected_count += 1
                    if severity == "high":
                        drift_severity_high += 1
                    elif severity == "medium":
                        drift_severity_medium += 1
                    else:
                        drift_severity_low += 1
                
                field_drift_details.append({
                    "field_id": col,
                    "field_name": col,
                    "baseline_statistics": {
                        "unique_values": len(baseline_dist),
                        "distribution": "categorical"
                    },
                    "current_statistics": {
                        "unique_values": len(current_dist),
                        "distribution": "categorical"
                    },
                    "drift_analysis": {
                        "drift_detected": drift_detected,
                        "drift_type": "distribution_shift",
                        "severity": severity,
                        "statistical_test": statistical_test,
                        "psi_score": round(psi_score, 4)
                    },
                    "drift_interpretation": {
                        "message": f"Category distribution {'has shifted significantly' if drift_detected else 'is stable'} from baseline",
                        "explanation": f"PSI score: {psi_score:.4f}",
                        "business_impact": f"Data patterns have {'changed' if drift_detected else 'remained'} consistent"
                    },
                    "issue_severity": severity if drift_detected else "low"
                })
        
        # Overall drift metrics
        overall_drift_score = drift_detected_count / max(len(common_cols), 1)
        average_psi_score = np.mean(psi_scores) if psi_scores else 0
        drift_percentage = (drift_detected_count / len(common_cols) * 100) if len(common_cols) > 0 else 0
        dataset_stability = "warning" if overall_drift_score > 0.1 else "stable"
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        if dataset_stability == "warning":
            alerts.append({
                "alert_id": "alert_drift_001",
                "severity": "high",
                "category": "drift",
                "message": f"Distribution drift in {drift_detected_count}/{len(common_cols)} fields ({drift_percentage:.1f}% affected)",
                "affected_fields_count": drift_detected_count,
                "recommendation": f"{drift_detected_count} field(s) showing drift. Retrain ML models with current data."
            })
        
        # Add severity-based alerts
        if drift_severity_high > 0:
            alerts.append({
                "alert_id": "alert_drift_high_severity",
                "severity": "critical",
                "category": "drift_high_severity",
                "message": f"{drift_severity_high} field(s) with high-severity drift detected",
                "affected_fields_count": drift_severity_high,
                "recommendation": f"Immediate attention required for {drift_severity_high} field(s) with significant distribution changes"
            })
        
        if average_psi_score > 0.25:
            alerts.append({
                "alert_id": "alert_drift_psi_high",
                "severity": "critical",
                "category": "drift_psi",
                "message": f"Average PSI score is {average_psi_score:.4f} (>0.25 indicates significant drift)",
                "affected_fields_count": drift_detected_count,
                "recommendation": "Model retraining strongly recommended due to significant population shift"
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Add field drift issues
        for field in field_drift_details:
            if field.get("drift_analysis", {}).get("drift_detected", False):
                field_name = field.get("field_name")
                field_id = field.get("field_id")
                drift_analysis = field.get("drift_analysis", {})
                psi_score = drift_analysis.get("psi_score", 0)
                severity = drift_analysis.get("severity", "medium")
                
                issues.append({
                    "issue_id": f"issue_drift_{field_id}",
                    "agent_id": "drift-detector",
                    "field_name": field_name,
                    "issue_type": "distribution_drift",
                    "severity": severity,
                    "message": f"Significant distribution drift detected (PSI: {psi_score:.4f})"
                })
                
                # Add specific drift type issues
                change_in_mean = drift_analysis.get("change_in_mean", 0)
                change_in_variance = drift_analysis.get("change_in_variance", 0)
                
                if change_in_mean > 0:
                    # Determine if mean shift is significant (>10% of baseline)
                    baseline_mean = field.get("baseline_statistics", {}).get("mean", 0)
                    if baseline_mean != 0 and (change_in_mean / abs(baseline_mean)) > 0.1:
                        issues.append({
                            "issue_id": f"issue_drift_mean_{field_id}",
                            "agent_id": "drift-detector",
                            "field_name": field_name,
                            "issue_type": "mean_shift",
                            "severity": "high" if (change_in_mean / abs(baseline_mean)) > 0.25 else "medium",
                            "message": f"Mean shifted by {change_in_mean:.2f} ({(change_in_mean / abs(baseline_mean) * 100):.1f}%)"
                        })
                
                if change_in_variance > 0:
                    baseline_std = field.get("baseline_statistics", {}).get("stddev", 0)
                    if baseline_std != 0 and (change_in_variance / abs(baseline_std)) > 0.2:
                        issues.append({
                            "issue_id": f"issue_drift_variance_{field_id}",
                            "agent_id": "drift-detector",
                            "field_name": field_name,
                            "issue_type": "variance_shift",
                            "severity": "medium",
                            "message": f"Variance shifted by {change_in_variance:.2f} ({(change_in_variance / abs(baseline_std) * 100):.1f}%)"
                        })
        
        # Check for missing/new columns
        missing_cols = baseline_cols - current_cols
        new_cols = current_cols - baseline_cols
        
        if missing_cols:
            for col in missing_cols:
                issues.append({
                    "issue_id": f"issue_drift_missing_col_{col}",
                    "agent_id": "drift-detector",
                    "field_name": col,
                    "issue_type": "missing_column",
                    "severity": "critical",
                    "message": f"Column '{col}' present in baseline but missing in current dataset"
                })
        
        if new_cols:
            for col in new_cols:
                issues.append({
                    "issue_id": f"issue_drift_new_col_{col}",
                    "agent_id": "drift-detector",
                    "field_name": col,
                    "issue_type": "new_column",
                    "severity": "warning",
                    "message": f"New column '{col}' present in current dataset but not in baseline"
                })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        recommendations = []
        
        # Drift recommendations
        if dataset_stability == "warning":
            drifted_fields = [f for f in field_drift_details if f.get("drift_analysis", {}).get("drift_detected", False)]
            recommendations.append({
                "recommendation_id": "rec_drift_001",
                "agent_id": "drift-detector",
                "field_name": f"{len(drifted_fields)} fields",
                "priority": "high",
                "recommendation": f"Retrain ML models. {len(drifted_fields)} field(s) show significant distribution drift.",
                "timeline": "1 week"
            })
        
        # High-severity drift fields
        high_severity_fields = [f for f in field_drift_details if f.get("drift_analysis", {}).get("severity") == "high"][:3]
        for field in high_severity_fields:
            field_name = field.get("field_name")
            field_id = field.get("field_id")
            psi_score = field.get("drift_analysis", {}).get("psi_score", 0)
            
            recommendations.append({
                "recommendation_id": f"rec_drift_high_{field_id}",
                "agent_id": "drift-detector",
                "field_name": field_name,
                "priority": "critical",
                "recommendation": f"Investigate {field_name} - High drift detected (PSI: {psi_score:.4f}). Review data collection process.",
                "timeline": "immediate"
            })
        
        # Model monitoring recommendation
        if drift_detected_count > 0:
            recommendations.append({
                "recommendation_id": "rec_drift_monitoring",
                "agent_id": "drift-detector",
                "field_name": "all fields",
                "priority": "medium",
                "recommendation": f"Implement continuous monitoring for {drift_detected_count} drifting field(s) to detect future changes",
                "timeline": "2-3 weeks"
            })
        
        # Schema change recommendations
        if missing_cols:
            recommendations.append({
                "recommendation_id": "rec_drift_missing_cols",
                "agent_id": "drift-detector",
                "field_name": ", ".join(list(missing_cols)[:3]),
                "priority": "critical",
                "recommendation": f"{len(missing_cols)} column(s) missing from current dataset. Update data pipeline or impute missing columns",
                "timeline": "immediate"
            })
        
        if new_cols:
            recommendations.append({
                "recommendation_id": "rec_drift_new_cols",
                "agent_id": "drift-detector",
                "field_name": ", ".join(list(new_cols)[:3]),
                "priority": "medium",
                "recommendation": f"{len(new_cols)} new column(s) detected. Review schema changes and update models if needed",
                "timeline": "1-2 weeks"
            })
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = []
        
        # Only add if drift detected
        if drift_detected_count > 0:
            executive_summary.append({
                "summary_id": "exec_drift",
                "title": "Distribution Drift",
                "value": f"{drift_detected_count}/{len(common_cols)}",
                "status": "critical" if drift_severity_high > 0 else "warning",
                "description": f"{drift_detected_count} field(s) with drift detected - {dataset_stability.upper()}"
            })
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_text_parts = []
        
        if drift_detected_count > 0:
            ai_analysis_text_parts.append(f"DRIFT DETECTION: {drift_detected_count}/{len(common_cols)} fields showing distribution drift ({drift_percentage:.1f}%)")
            ai_analysis_text_parts.append(f"- Average PSI score: {average_psi_score:.4f}")
            ai_analysis_text_parts.append(f"- Dataset stability: {dataset_stability.upper()}")
            
            if drift_severity_high > 0:
                ai_analysis_text_parts.append(f"- {drift_severity_high} field(s) with HIGH severity drift")
            if drift_severity_medium > 0:
                ai_analysis_text_parts.append(f"- {drift_severity_medium} field(s) with MEDIUM severity drift")
            
            ai_analysis_text_parts.append("- Model retraining recommended due to significant drift")
        else:
            ai_analysis_text_parts.append(f"DRIFT DETECTION: No significant drift detected. Dataset is stable.")
        
        ai_analysis_text = "\n".join(ai_analysis_text_parts)
        
        return {
            "status": "success",
            "agent_id": "drift-detector",
            "agent_name": "DriftDetector",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "fields_analyzed": len(common_cols),
                "drift_detected_count": drift_detected_count,
                "drift_severity_high": drift_severity_high,
                "drift_severity_medium": drift_severity_medium,
                "drift_severity_low": drift_severity_low,
                "average_psi_score": round(average_psi_score, 4)
            },
            "data": {
                "fields": field_drift_details,
                "drift_summary": {
                    "overall_drift_score": round(overall_drift_score, 4),
                    "drift_percentage": round(drift_percentage, 2),
                    "fields_with_drift": drift_detected_count,
                    "dataset_stability": dataset_stability
                }
            },
            "alerts": alerts,
            "issues": issues,
            "recommendations": recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _calculate_psi(baseline, current, bins=10):
    """Calculate Population Stability Index"""
    def _psi_bin(baseline_bin, current_bin):
        if current_bin == 0:
            current_bin = 0.0001
        if baseline_bin == 0:
            baseline_bin = 0.0001
        return (current_bin - baseline_bin) * np.log(current_bin / baseline_bin)
    
    baseline_counts = pd.cut(baseline, bins=bins, duplicates='drop').value_counts(normalize=True).sort_index()
    current_counts = pd.cut(current, bins=bins, duplicates='drop').value_counts(normalize=True).sort_index()
    
    psi = 0
    for i in range(len(baseline_counts)):
        baseline_bin = baseline_counts.iloc[i]
        current_bin = current_counts.iloc[i] if i < len(current_counts) else 0
        psi += _psi_bin(baseline_bin, current_bin)
    
    return abs(psi)


def _calculate_psi_categorical(baseline_dist, current_dist):
    """Calculate PSI for categorical distributions"""
    def _psi_component(baseline_bin, current_bin):
        if current_bin == 0:
            current_bin = 0.0001
        if baseline_bin == 0:
            baseline_bin = 0.0001
        return (current_bin - baseline_bin) * np.log(current_bin / baseline_bin)
    
    psi = 0
    all_categories = set(baseline_dist.index) | set(current_dist.index)
    
    for cat in all_categories:
        baseline_bin = baseline_dist.get(cat, 0)
        current_bin = current_dist.get(cat, 0)
        psi += _psi_component(baseline_bin, current_bin)
    
    return abs(psi)


def _calculate_js_divergence(baseline, current):
    """Calculate Jensen-Shannon divergence"""
    # Create bins for both distributions
    all_data = pd.concat([baseline, current])
    
    if len(all_data) == 0:
        return 0.0
    
    # Create appropriate number of bins based on data characteristics
    n_bins = min(10, int(np.sqrt(len(all_data))))
    if n_bins < 2:
        n_bins = 2
    
    try:
        bins = np.histogram_bin_edges(all_data, bins=n_bins)
        
        baseline_hist, _ = np.histogram(baseline, bins=bins)
        current_hist, _ = np.histogram(current, bins=bins)
        
        # Normalize to probabilities
        baseline_hist = baseline_hist / (baseline_hist.sum() + 1e-10)
        current_hist = current_hist / (current_hist.sum() + 1e-10)
        
        # Calculate JS divergence
        m = 0.5 * (baseline_hist + current_hist)
        
        # KL divergence component 1
        kl_1 = 0.0
        for i in range(len(baseline_hist)):
            if baseline_hist[i] > 0 and m[i] > 0:
                kl_1 += baseline_hist[i] * np.log(baseline_hist[i] / m[i])
        
        # KL divergence component 2
        kl_2 = 0.0
        for i in range(len(current_hist)):
            if current_hist[i] > 0 and m[i] > 0:
                kl_2 += current_hist[i] * np.log(current_hist[i] / m[i])
        
        # JS divergence is sqrt of average KL divergences
        js_div = np.sqrt(0.5 * (kl_1 + kl_2))
        
        return float(js_div)
    except:
        return 0.0
