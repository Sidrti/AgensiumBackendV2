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
                    "dataset_stability": "warning" if overall_drift_score > 0.1 else "stable"
                }
            }
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
