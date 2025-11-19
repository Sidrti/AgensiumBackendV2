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
        missing_cols = baseline_cols - current_cols
        new_cols = current_cols - baseline_cols
        
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
        
        # ==================== GENERATE ROW-LEVEL-ISSUES ====================
        row_level_issues = []
        
        for col in common_cols:
            baseline_col = baseline_df[col].dropna()
            current_col = current_df[col].dropna()
            
            # Skip if insufficient data
            if len(baseline_col) < min_sample_size or len(current_col) < min_sample_size:
                continue
            
            # Get drift analysis for this field
            field_drift = next((f for f in field_drift_details if f.get("field_id") == col), None)
            if not field_drift or not field_drift.get("drift_analysis", {}).get("drift_detected"):
                continue
            
            # For numeric columns: identify rows with values outside baseline range
            if baseline_col.dtype in ['int64', 'float64', 'int32', 'float32']:
                baseline_mean = baseline_col.mean()
                baseline_std = baseline_col.std()
                baseline_min = baseline_col.quantile(0.05)  # 5th percentile
                baseline_max = baseline_col.quantile(0.95)  # 95th percentile
                current_mean = current_col.mean()
                current_std = current_col.std()
                
                # Calculate z-scores based on baseline distribution
                current_z_scores = (current_df[col] - baseline_mean) / (baseline_std + 1e-10)
                
                # Issue 1: Values far outside baseline range (z-score > 2)
                outlier_mask = (np.abs(current_z_scores) > 2) & (current_df[col].notna())
                for row_idx in current_df[outlier_mask].index:
                    row_value = current_df.loc[row_idx, col]
                    z_score = (row_value - baseline_mean) / (baseline_std + 1e-10)
                    row_level_issues.append({
                        "row_index": int(row_idx),
                        "column": col,
                        "issue_type": "distribution_shift",
                        "severity": "warning",
                        "message": f"Value {row_value} is outside baseline distribution range (z-score: {z_score:.2f}). Baseline mean: {baseline_mean:.2f}",
                        "value": float(row_value),
                        "bounds": {
                            "lower": float(baseline_min),
                            "upper": float(baseline_max)
                        },
                        "z_score": float(z_score)
                    })
                
                # Issue 2: Values from shifted distribution (different mean/std)
                mean_shift_significant = abs(current_mean - baseline_mean) > baseline_std * 0.5
                
                if mean_shift_significant:
                    # Flag rows that align more with current distribution (far from baseline)
                    shift_threshold = baseline_mean + (1.5 * baseline_std)
                    shifted_mask = (current_df[col] > shift_threshold) & (current_df[col].notna())
                    
                    for row_idx in current_df[shifted_mask].index:
                        row_value = current_df.loc[row_idx, col]
                        row_level_issues.append({
                            "row_index": int(row_idx),
                            "column": col,
                            "issue_type": "value_range_change",
                            "severity": "info",
                            "message": f"Value {row_value} consistent with shifted distribution (baseline mean: {baseline_mean:.2f}, current mean: {current_mean:.2f})",
                            "value": float(row_value),
                            "baseline_mean": float(baseline_mean),
                            "current_mean": float(current_mean)
                        })
            else:
                # For categorical columns: identify rows with values not in baseline
                baseline_categories = set(baseline_col.unique())
                current_categories = set(current_df[col].dropna().unique())
                new_categories = current_categories - baseline_categories
                
                if new_categories:
                    for category in new_categories:
                        category_mask = (current_df[col] == category) & (current_df[col].notna())
                        for row_idx in current_df[category_mask].index:
                            row_level_issues.append({
                                "row_index": int(row_idx),
                                "column": col,
                                "issue_type": "distribution_shift",
                                "severity": "warning",
                                "message": f"Category '{category}' not present in baseline data",
                                "value": str(category)
                            })
        
        # Cap row-level-issues at 1000
        row_level_issues = row_level_issues[:1000]
        
        # Calculate issue summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {},
            "affected_rows": len(set(issue["row_index"] for issue in row_level_issues)),
            "affected_columns": sorted(list(set(issue["column"] for issue in row_level_issues)))
        }
        
        # Count by type
        for issue in row_level_issues:
            issue_type = issue["issue_type"]
            issue_summary["by_type"][issue_type] = issue_summary["by_type"].get(issue_type, 0) + 1
        
        # Count by severity
        for issue in row_level_issues:
            severity = issue["severity"]
            issue_summary["by_severity"][severity] = issue_summary["by_severity"].get(severity, 0) + 1
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # Alert 1: Overall drift detection
        if dataset_stability == "warning":
            alerts.append({
                "alert_id": "alert_drift_001_overall",
                "severity": "high",
                "category": "drift",
                "message": f"Distribution drift in {drift_detected_count}/{len(common_cols)} fields ({drift_percentage:.1f}% affected)",
                "affected_fields_count": drift_detected_count,
                "recommendation": f"{drift_detected_count} field(s) showing drift. Retrain ML models with current data."
            })
        
        # Alert 2: High-severity drift fields
        if drift_severity_high > 0:
            alerts.append({
                "alert_id": "alert_drift_high_severity",
                "severity": "critical",
                "category": "drift_high_severity",
                "message": f"{drift_severity_high} field(s) with high-severity drift detected (PSI > 0.25)",
                "affected_fields_count": drift_severity_high,
                "recommendation": f"CRITICAL: Immediate attention required for {drift_severity_high} field(s) with significant distribution changes. Investigate data source."
            })
        
        # Alert 3: High average PSI score
        if average_psi_score > 0.25:
            alerts.append({
                "alert_id": "alert_drift_psi_critical",
                "severity": "critical",
                "category": "drift_psi",
                "message": f"Average PSI score is {average_psi_score:.4f} (>0.25 indicates significant drift across multiple fields)",
                "affected_fields_count": drift_detected_count,
                "recommendation": "Model retraining strongly recommended due to significant population shift. Verify data pipeline integrity."
            })
        
        # Alert 4: Medium-severity drift
        if drift_severity_medium > 0:
            alerts.append({
                "alert_id": "alert_drift_medium_severity",
                "severity": "high",
                "category": "drift_medium_severity",
                "message": f"{drift_severity_medium} field(s) with medium-severity drift detected (0.1 < PSI <= 0.25)",
                "affected_fields_count": drift_severity_medium,
                "recommendation": f"Review {drift_severity_medium} field(s) with moderate distribution changes. Monitor for escalation."
            })
        
        # Alert 5: Missing columns (schema drift)
        if missing_cols:
            alerts.append({
                "alert_id": "alert_drift_missing_columns",
                "severity": "critical",
                "category": "schema_mismatch",
                "message": f"Schema drift: {len(missing_cols)} column(s) missing from current dataset ({', '.join(list(missing_cols)[:3])}...)",
                "affected_fields_count": len(missing_cols),
                "recommendation": f"Critical: {len(missing_cols)} baseline column(s) are missing. Update data pipeline or impute missing columns."
            })
        
        # Alert 6: New columns (schema expansion)
        if new_cols:
            alerts.append({
                "alert_id": "alert_drift_new_columns",
                "severity": "medium",
                "category": "schema_change",
                "message": f"Schema expansion: {len(new_cols)} new column(s) present in current dataset ({', '.join(list(new_cols)[:3])}...)",
                "affected_fields_count": len(new_cols),
                "recommendation": f"Review {len(new_cols)} new column(s). Update baseline or refine feature selection if not intentional."
            })
        
        # Alert 7: Significant mean shifts
        high_mean_shift_fields = [f for f in field_drift_details if f.get("drift_analysis", {}).get("change_in_mean", 0) > 0 and 
                                  abs(f.get("drift_analysis", {}).get("change_in_mean", 0) / max(f.get("baseline_statistics", {}).get("mean", 1), 0.001)) > 0.25]
        if len(high_mean_shift_fields) > 0:
            alerts.append({
                "alert_id": "alert_drift_mean_shift",
                "severity": "high",
                "category": "distribution_shift",
                "message": f"{len(high_mean_shift_fields)} field(s) show mean shift >25% (centrality change)",
                "affected_fields_count": len(high_mean_shift_fields),
                "recommendation": f"Investigate {len(high_mean_shift_fields)} field(s) for mean shifts. Check for data source changes or seasonal effects."
            })
        
        # Alert 8: Significant variance shifts
        high_variance_shift_fields = [f for f in field_drift_details if f.get("drift_analysis", {}).get("change_in_variance", 0) > 0 and
                                      abs(f.get("drift_analysis", {}).get("change_in_variance", 0) / max(f.get("baseline_statistics", {}).get("stddev", 1), 0.001)) > 0.5]
        if len(high_variance_shift_fields) > 0:
            alerts.append({
                "alert_id": "alert_drift_variance_shift",
                "severity": "high",
                "category": "distribution_spread",
                "message": f"{len(high_variance_shift_fields)} field(s) show variance shift >50% (spread change)",
                "affected_fields_count": len(high_variance_shift_fields),
                "recommendation": f"Investigate {len(high_variance_shift_fields)} field(s) for increased/decreased spread. May indicate data quality degradation."
            })
        
        # Alert 9: Systematic drift detection
        if drift_detected_count > 0 and drift_detected_count >= len(common_cols) * 0.3:
            alerts.append({
                "alert_id": "alert_drift_systematic",
                "severity": "high",
                "category": "systematic_drift",
                "message": f"Systematic drift: {drift_percentage:.1f}% of fields affected (suggests common cause, not random variation)",
                "affected_fields_count": drift_detected_count,
                "recommendation": "Investigate for systematic causes: data source changes, collection period changes, or environmental shifts."
            })
        
        # Alert 10: Data quality signal (stable data)
        if drift_detected_count == 0 and len(common_cols) > 0:
            alerts.append({
                "alert_id": "alert_drift_stable",
                "severity": "low",
                "category": "quality_validation",
                "message": f"Data distribution is stable: No significant drift detected across {len(common_cols)} fields",
                "affected_fields_count": 0,
                "recommendation": "Data quality is stable. Current ML models remain valid. Continue routine monitoring."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Add field drift issues (limit to 100)
        for field in field_drift_details[:100]:
            if field.get("drift_analysis", {}).get("drift_detected", False):
                field_name = field.get("field_name")
                field_id = field.get("field_id")
                drift_analysis = field.get("drift_analysis", {})
                psi_score = drift_analysis.get("psi_score", 0)
                severity = drift_analysis.get("severity", "medium")
                
                # Issue 1: Main drift detection
                issues.append({
                    "issue_id": f"issue_drift_{field_id}_detected",
                    "agent_id": "drift-detector",
                    "field_name": field_name,
                    "issue_type": "distribution_drift",
                    "severity": severity,
                    "message": f"Significant distribution drift detected (PSI: {psi_score:.4f})"
                })
                
                # Issue 2: Mean shift (>10% is significant)
                change_in_mean = drift_analysis.get("change_in_mean", 0)
                if change_in_mean > 0:
                    baseline_mean = field.get("baseline_statistics", {}).get("mean", 0)
                    if baseline_mean != 0:
                        mean_shift_pct = (change_in_mean / abs(baseline_mean)) * 100
                        if mean_shift_pct > 10:
                            issues.append({
                                "issue_id": f"issue_drift_mean_{field_id}",
                                "agent_id": "drift-detector",
                                "field_name": field_name,
                                "issue_type": "mean_shift",
                                "severity": "critical" if mean_shift_pct > 50 else "high" if mean_shift_pct > 25 else "medium",
                                "message": f"Mean shifted by {change_in_mean:.2f} ({mean_shift_pct:.1f}% change)"
                            })
                
                # Issue 3: Variance shift (>20% is significant)
                change_in_variance = drift_analysis.get("change_in_variance", 0)
                if change_in_variance > 0:
                    baseline_std = field.get("baseline_statistics", {}).get("stddev", 0)
                    if baseline_std != 0:
                        var_shift_pct = (change_in_variance / abs(baseline_std)) * 100
                        if var_shift_pct > 20:
                            issues.append({
                                "issue_id": f"issue_drift_variance_{field_id}",
                                "agent_id": "drift-detector",
                                "field_name": field_name,
                                "issue_type": "variance_shift",
                                "severity": "high" if var_shift_pct > 50 else "medium",
                                "message": f"Variance shifted by {change_in_variance:.2f} ({var_shift_pct:.1f}% spread increase)"
                            })
                
                # Issue 4: Statistical significance
                p_value = drift_analysis.get("p_value", 1.0)
                if p_value < 0.001:
                    issues.append({
                        "issue_id": f"issue_drift_statistical_{field_id}",
                        "agent_id": "drift-detector",
                        "field_name": field_name,
                        "issue_type": "distribution_drift",
                        "severity": "critical",
                        "message": f"Statistically significant drift (p-value: {p_value:.6f} << 0.05)"
                    })
                
                # Issue 5: Wasserstein distance
                wasserstein = drift_analysis.get("wasserstein_distance", 0)
                if wasserstein > 1.0:
                    issues.append({
                        "issue_id": f"issue_drift_wasserstein_{field_id}",
                        "agent_id": "drift-detector",
                        "field_name": field_name,
                        "issue_type": "distribution_drift",
                        "severity": "high",
                        "message": f"Large Wasserstein distance: {wasserstein:.4f} (data distribution very different)"
                    })
        
        # Missing/New columns issues
        missing_cols = baseline_cols - current_cols
        new_cols = current_cols - baseline_cols
        
        # Issue 6: Missing columns
        if missing_cols:
            for col in list(missing_cols)[:10]:
                issues.append({
                    "issue_id": f"issue_drift_missing_{col}",
                    "agent_id": "drift-detector",
                    "field_name": col,
                    "issue_type": "missing_column",
                    "severity": "critical",
                    "message": f"Schema mismatch: Column '{col}' in baseline but missing in current dataset"
                })
        
        # Issue 7: New columns
        if new_cols:
            for col in list(new_cols)[:10]:
                issues.append({
                    "issue_id": f"issue_drift_new_{col}",
                    "agent_id": "drift-detector",
                    "field_name": col,
                    "issue_type": "new_column",
                    "severity": "warning",
                    "message": f"Schema expansion: New column '{col}' present in current dataset but not in baseline"
                })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        recommendations = []
        
        # Recommendation 1: Model retraining
        if dataset_stability == "warning" or drift_detected_count > 0:
            drifted_fields = [f for f in field_drift_details if f.get("drift_analysis", {}).get("drift_detected", False)]
            recommendations.append({
                "recommendation_id": "rec_drift_retrain_models",
                "agent_id": "drift-detector",
                "field_name": f"{len(drifted_fields)} fields",
                "priority": "critical" if drift_severity_high > 0 else "high",
                "recommendation": f"Retrain ML models using current data. {len(drifted_fields)} field(s) show significant distribution drift. Current models may be biased.",
                "timeline": "1 week" if drift_severity_high > 0 else "2 weeks"
            })
        
        # Recommendation 2: Investigate high-severity fields
        high_severity_fields = [f for f in field_drift_details if f.get("drift_analysis", {}).get("severity") == "high"][:3]
        if high_severity_fields:
            field_names = ", ".join([f.get("field_name") for f in high_severity_fields])
            recommendations.append({
                "recommendation_id": "rec_drift_investigate_high_fields",
                "agent_id": "drift-detector",
                "field_name": field_names,
                "priority": "critical",
                "recommendation": f"Investigate root cause for high drift in: {field_names}. Check data collection process, source systems, and business logic changes.",
                "timeline": "immediate"
            })
        
        # Recommendation 3: Data source validation
        if drift_detected_count > 0 and drift_detected_count >= len(common_cols) * 0.3:
            recommendations.append({
                "recommendation_id": "rec_drift_source_validation",
                "agent_id": "drift-detector",
                "field_name": "all fields",
                "priority": "high",
                "recommendation": "Validate data pipeline integrity. Systematic drift across multiple fields suggests common cause: source system changes, data integration issues, or environmental shifts.",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 4: Schema alignment (missing columns)
        if missing_cols:
            recommendations.append({
                "recommendation_id": "rec_drift_missing_columns",
                "agent_id": "drift-detector",
                "field_name": ", ".join(list(missing_cols)[:3]),
                "priority": "critical",
                "recommendation": f"CRITICAL: {len(missing_cols)} baseline column(s) missing from current dataset. Update data pipeline to include missing fields or recalibrate baseline.",
                "timeline": "immediate"
            })
        
        # Recommendation 5: Schema expansion review
        if new_cols:
            recommendations.append({
                "recommendation_id": "rec_drift_new_columns_review",
                "agent_id": "drift-detector",
                "field_name": ", ".join(list(new_cols)[:3]),
                "priority": "medium",
                "recommendation": f"Review {len(new_cols)} new column(s): {', '.join(list(new_cols)[:3])}. Update baseline if intentional, or filter if spurious.",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 6: Drift monitoring setup
        if drift_detected_count > 0:
            recommendations.append({
                "recommendation_id": "rec_drift_continuous_monitoring",
                "agent_id": "drift-detector",
                "field_name": "all fields",
                "priority": "medium",
                "recommendation": f"Establish continuous drift monitoring for {drift_detected_count} drifting field(s). Set up automated alerts for PSI > 0.1 or p-value < 0.05.",
                "timeline": "2-3 weeks"
            })
        
        # Recommendation 7: Mean shift investigation
        high_mean_shifts = [f for f in field_drift_details if f.get("drift_analysis", {}).get("change_in_mean", 0) > 0 and
                           abs(f.get("drift_analysis", {}).get("change_in_mean", 0) / max(f.get("baseline_statistics", {}).get("mean", 1), 0.001)) > 0.25]
        if high_mean_shifts:
            recommendations.append({
                "recommendation_id": "rec_drift_mean_shift_analysis",
                "agent_id": "drift-detector",
                "field_name": ", ".join([f.get("field_name") for f in high_mean_shifts[:3]]),
                "priority": "high",
                "recommendation": f"Analyze {len(high_mean_shifts)} field(s) with >25% mean shifts. Evaluate for seasonality, business changes, or data quality issues.",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 8: Variance shift investigation
        high_var_shifts = [f for f in field_drift_details if f.get("drift_analysis", {}).get("change_in_variance", 0) > 0 and
                          abs(f.get("drift_analysis", {}).get("change_in_variance", 0) / max(f.get("baseline_statistics", {}).get("stddev", 1), 0.001)) > 0.5]
        if high_var_shifts:
            recommendations.append({
                "recommendation_id": "rec_drift_variance_shift_analysis",
                "agent_id": "drift-detector",
                "field_name": ", ".join([f.get("field_name") for f in high_var_shifts[:3]]),
                "priority": "high",
                "recommendation": f"Investigate {len(high_var_shifts)} field(s) with >50% variance shifts. May indicate data quality degradation or new data patterns.",
                "timeline": "2-3 weeks"
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
                },
                "overrides": {
                    "statistical_test": statistical_test,
                    "significance_level": significance_level,
                    "min_sample_size": min_sample_size
                }
            },
            "alerts": alerts,
            "issues": issues,
            "recommendations": recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary
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
