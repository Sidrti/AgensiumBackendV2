"""
Cleanse Previewer Agent (Optimized)

Provides "What If" analysis for data cleaning operations before execution.
Calculates and presents anticipated effects of cleaning operations to mitigate risk
and build trust. Simulates transformations and compares metrics before/after.

Primary Goal: Mitigate Risk and Build Trust
Workflow: Runs pre-emptively before actual cleaning agents execute
Analysis: Calculates Current vs Preview metrics for impact assessment

Input: CSV file (primary) + cleaning rules
Output: Impact assessment with before/after comparison and risk analysis
"""

import polars as pl
import numpy as np
import io
import time
from typing import Dict, Any, Optional, List, Tuple
from agents.agent_utils import safe_get_list

def execute_cleanse_previewer(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Preview the impact of data cleaning operations before execution.

    Args:
        file_contents: File bytes (read as binary)
        filename: Original filename (used to detect format)
        parameters: Agent parameters from tool.json

    Returns:
        Standardized output dictionary with impact assessment
    """
    start_time = time.time()
    parameters = parameters or {}

    # Extract and parse parameters with defaults
    preview_rules = safe_get_list(parameters, "preview_rules", [])
    impact_threshold_high = parameters.get("impact_threshold_high", 10)
    impact_threshold_medium = parameters.get("impact_threshold_medium", 5)
    confidence_level = parameters.get("confidence_level", 0.95)
    calculate_distributions = parameters.get("calculate_distributions", True)
    compare_statistics = parameters.get("compare_statistics", True)
    analyze_correlations = parameters.get("analyze_correlations", False)
    
    # Scoring weights
    accuracy_weight = parameters.get("accuracy_weight", 0.4)
    safety_weight = parameters.get("safety_weight", 0.3)
    completeness_weight = parameters.get("completeness_weight", 0.3)
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file - CSV only
        if not filename.endswith('.csv'):
             return {
                "status": "error",
                "agent_id": "cleanse-previewer",
                "error": f"Unsupported file format: {filename}. Only CSV is supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        try:
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True)
        except Exception as e:
             return {
                "status": "error",
                "agent_id": "cleanse-previewer",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.height == 0:
            return {
                "status": "error",
                "agent_id": "cleanse-previewer",
                "agent_name": "Cleanse Previewer",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Analyze original data (current state)
        original_profile = _profile_dataset(df, {
            "calculate_distributions": calculate_distributions,
            "compare_statistics": compare_statistics,
            "analyze_correlations": analyze_correlations
        })
        
        # Simulate cleaning operations
        simulated_results = []
        overall_impact_assessment = {
            "total_rules": len(preview_rules),
            "high_impact_rules": 0,
            "medium_impact_rules": 0,
            "low_impact_rules": 0,
            "safe_to_execute": True,
            "warnings": []
        }
        
        for rule_idx, rule in enumerate(preview_rules):
            try:
                # Apply rule simulation
                df_simulated, simulation_log = _simulate_cleaning_rule(df.clone(), rule)
                
                # Profile simulated data
                simulated_profile = _profile_dataset(df_simulated, {
                    "calculate_distributions": calculate_distributions,
                    "compare_statistics": compare_statistics,
                    "analyze_correlations": analyze_correlations
                })
                
                # Calculate impact
                impact_analysis = _calculate_impact(
                    original_profile,
                    simulated_profile,
                    rule,
                    {
                        "high_threshold": impact_threshold_high,
                        "medium_threshold": impact_threshold_medium
                    }
                )
                
                # Store result
                simulated_results.append({
                    "rule_id": rule.get("rule_id", f"rule_{rule_idx + 1}"),
                    "rule_description": rule.get("description", "Cleaning rule"),
                    "rule_type": rule.get("type", "unknown"),
                    "target_columns": rule.get("target_columns", []),
                    "simulation_log": simulation_log,
                    "original_metrics": impact_analysis["original_metrics"],
                    "preview_metrics": impact_analysis["preview_metrics"],
                    "changes": impact_analysis["changes"],
                    "impact_level": impact_analysis["impact_level"],
                    "risk_assessment": impact_analysis["risk_assessment"],
                    "recommendations": impact_analysis["recommendations"]
                })
                
                # Update overall assessment
                if impact_analysis["impact_level"] == "high":
                    overall_impact_assessment["high_impact_rules"] += 1
                    if impact_analysis["risk_assessment"]["is_risky"]:
                        overall_impact_assessment["safe_to_execute"] = False
                        overall_impact_assessment["warnings"].append(
                            f"Rule '{rule.get('description', 'unknown')}' has high impact and risk"
                        )
                elif impact_analysis["impact_level"] == "medium":
                    overall_impact_assessment["medium_impact_rules"] += 1
                else:
                    overall_impact_assessment["low_impact_rules"] += 1
                    
            except Exception as e:
                simulated_results.append({
                    "rule_id": rule.get("rule_id", f"rule_{rule_idx + 1}"),
                    "rule_description": rule.get("description", "Cleaning rule"),
                    "status": "error",
                    "error": str(e)
                })
        
        # Calculate preview confidence score
        preview_score = _calculate_preview_score(
            original_profile,
            simulated_results,
            overall_impact_assessment,
            {
                "accuracy_weight": accuracy_weight,
                "safety_weight": safety_weight,
                "completeness_weight": completeness_weight,
                "excellent_threshold": excellent_threshold,
                "good_threshold": good_threshold
            }
        )
        
        # Determine quality status
        if preview_score["overall_score"] >= excellent_threshold:
            quality_status = "excellent"
        elif preview_score["overall_score"] >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_review"
        
        # Generate recommendations
        recommendations = _generate_preview_recommendations(
            simulated_results,
            overall_impact_assessment,
            preview_score
        )
        
        # Build preview analysis
        preview_analysis = {
            "original_profile": original_profile,
            "simulated_results": simulated_results,
            "overall_impact": overall_impact_assessment,
            "statistical_confidence": confidence_level * 100,
            "execution_safety": "SAFE" if overall_impact_assessment["safe_to_execute"] else "CAUTION",
            "recommendations": recommendations
        }
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # High-impact rules alert
        if overall_impact_assessment["high_impact_rules"] > 0:
            alerts.append({
                "alert_id": "alert_preview_high_impact",
                "severity": "critical" if not overall_impact_assessment["safe_to_execute"] else "high",
                "category": "cleaning_impact",
                "message": f"{overall_impact_assessment['high_impact_rules']} high-impact cleaning rule(s) detected. Safety: {preview_analysis['execution_safety']}",
                "affected_fields_count": overall_impact_assessment["high_impact_rules"],
                "recommendation": "Review high-impact rules before execution. Consider creating backups."
            })
        
        # Safety alert
        if not overall_impact_assessment["safe_to_execute"]:
            alerts.append({
                "alert_id": "alert_preview_unsafe",
                "severity": "critical",
                "category": "execution_safety",
                "message": f"Execution safety: CAUTION - {len(overall_impact_assessment['warnings'])} warning(s) detected",
                "affected_fields_count": len(overall_impact_assessment["warnings"]),
                "recommendation": "Address warnings before executing cleaning operations. Risk of significant data loss or corruption."
            })
        
        # Quality score alert
        if preview_score["overall_score"] < 75:
            alerts.append({
                "alert_id": "alert_preview_quality",
                "severity": "high" if preview_score["overall_score"] < 60 else "medium",
                "category": "preview_quality",
                "message": f"Preview quality score: {preview_score['overall_score']:.1f}/100 ({quality_status})",
                "affected_fields_count": len(preview_rules),
                "recommendation": "Review preview analysis results. Consider adjusting cleaning strategy."
            })
        
        # Simulation failures alert
        failed_simulations = preview_score["metrics"]["total_simulations"] - preview_score["metrics"]["successful_simulations"]
        if failed_simulations > 0:
            alerts.append({
                "alert_id": "alert_preview_simulation_failures",
                "severity": "high",
                "category": "simulation_error",
                "message": f"{failed_simulations} simulation(s) failed out of {preview_score['metrics']['total_simulations']} total",
                "affected_fields_count": failed_simulations,
                "recommendation": "Review and fix failed simulation rules before execution."
            })

        # Large memory change alert
        memory_change = 0
        if simulated_results:
            try:
                memory_change = simulated_results[0].get('preview_metrics', {}).get('memory_mb', 0) - original_profile.get('memory_usage_mb', 0)
            except:
                memory_change = 0

        if abs(memory_change) > 50:  # MB
            alerts.append({
                "alert_id": "alert_preview_memory_change",
                "severity": "medium",
                "category": "resource_impact",
                "message": f"Significant memory change after simulation: {memory_change:.1f} MB (first simulated rule)",
                "affected_fields_count": 1,
                "recommendation": "Review transformations that add or remove large columns or expand data (e.g., exploding arrays). Consider sampling for full-run estimation."
            })

        # Low preview confidence alert
        if preview_score["metrics"].get("successful_simulations", 0) < max(1, preview_score["metrics"].get("total_simulations", 0)) and preview_score["overall_score"] < 60:
            alerts.append({
                "alert_id": "alert_preview_low_confidence",
                "severity": "high",
                "category": "preview_confidence",
                "message": f"Preview confidence low: score {preview_score['overall_score']:.1f}/100 with {preview_score['metrics'].get('successful_simulations',0)}/{preview_score['metrics'].get('total_simulations',0)} successful simulations",
                "affected_fields_count": preview_score["metrics"].get("total_simulations", 0),
                "recommendation": "Increase sampling, refine simulation rules, or run a staged test on a representative subset before full execution."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Extract impact issues
        impact_issues = _extract_impact_issues(simulated_results)
        for impact_issue in impact_issues[:100]:
            issues.append({
                "issue_id": f"issue_preview_{impact_issue.get('rule_id', 'unknown')}_{impact_issue.get('issue_type', 'unknown')}",
                "agent_id": "cleanse-previewer",
                "field_name": impact_issue.get("rule_id", "N/A"),
                "issue_type": impact_issue.get("issue_type", "preview_issue"),
                "severity": impact_issue.get("severity", "medium"),
                "message": impact_issue.get("description", "Preview issue detected")
            })
            
        # Memory usage issue
        if abs(memory_change) > 50:
            issues.append({
                "issue_id": "issue_preview_memory_spike",
                "agent_id": "cleanse-previewer",
                "field_name": "global",
                "issue_type": "resource_usage",
                "severity": "medium",
                "message": f"Projected memory usage change of {memory_change:.1f} MB detected during simulation."
            })

        # Simulation failure issue
        if failed_simulations > 0:
            issues.append({
                "issue_id": "issue_preview_simulation_failed",
                "agent_id": "cleanse-previewer",
                "field_name": "simulation_engine",
                "issue_type": "execution_error",
                "severity": "high",
                "message": f"{failed_simulations} simulation rules failed to execute."
            })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        agent_recommendations = []
        
        # Top recommendations from preview analysis
        for rec in recommendations[:7]:
            rec_id = f"rec_preview_{rec.get('action', 'unknown')}"
            affected_rules = rec.get("affected_rules", [])
            field_name = ", ".join(affected_rules[:3]) if affected_rules else "multiple"
            
            agent_recommendations.append({
                "recommendation_id": rec_id,
                "agent_id": "cleanse-previewer",
                "field_name": field_name,
                "priority": rec.get("priority", "medium"),
                "recommendation": f"{rec.get('action', 'Review')}: {rec.get('reason', 'No reason provided')}",
                "timeline": "immediate" if rec.get("priority") == "critical" else "1 week" if rec.get("priority") == "high" else "2 weeks"
            })
        
        # Safety-based recommendations
        if not overall_impact_assessment["safe_to_execute"]:
            agent_recommendations.append({
                "recommendation_id": "rec_preview_safety",
                "agent_id": "cleanse-previewer",
                "field_name": "all rules",
                "priority": "critical",
                "recommendation": "Create data backup before executing cleaning operations. High risk of data loss detected.",
                "timeline": "immediate"
            })

        # Memory recommendation
        if abs(memory_change) > 50:
            agent_recommendations.append({
                "recommendation_id": "rec_preview_memory_optimization",
                "agent_id": "cleanse-previewer",
                "field_name": "global",
                "priority": "medium",
                "recommendation": "Optimize cleaning rules to reduce memory footprint. Consider processing in chunks.",
                "timeline": "before_execution"
            })
            
        # Low confidence recommendation
        if preview_score["overall_score"] < 60:
             agent_recommendations.append({
                "recommendation_id": "rec_preview_improve_rules",
                "agent_id": "cleanse-previewer",
                "field_name": "configuration",
                "priority": "high",
                "recommendation": "Refine cleaning rules to improve preview score. Current score indicates potential issues.",
                "timeline": "immediate"
            })
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = [{
            "summary_id": "exec_cleanse_preview",
            "title": "Cleanse Preview Status",
            "value": f"{preview_score['overall_score']:.1f}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_review",
            "description": f"Preview Score: {preview_score['overall_score']:.1f}/100, Safety: {preview_analysis['execution_safety']}, {len(preview_rules)} rules analyzed ({overall_impact_assessment['high_impact_rules']} high-impact)"
        }]
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_parts = []
        ai_analysis_parts.append(f"CLEANSE PREVIEWER ANALYSIS:")
        ai_analysis_parts.append(f"- Preview Score: {preview_score['overall_score']:.1f}/100 (Accuracy: {preview_score['metrics']['accuracy_score']:.1f}, Safety: {preview_score['metrics']['safety_score']:.1f}, Completeness: {preview_score['metrics']['completeness_score']:.1f})")
        ai_analysis_parts.append(f"- Rules Analyzed: {len(preview_rules)} total ({overall_impact_assessment['high_impact_rules']} high-impact, {overall_impact_assessment['medium_impact_rules']} medium-impact, {overall_impact_assessment['low_impact_rules']} low-impact)")
        ai_analysis_parts.append(f"- Execution Safety: {preview_analysis['execution_safety']} ({'SAFE' if overall_impact_assessment['safe_to_execute'] else 'CAUTION REQUIRED'})")
        ai_analysis_parts.append(f"- Warnings: {len(overall_impact_assessment['warnings'])} critical warnings detected")
        if overall_impact_assessment['warnings']:
            ai_analysis_parts.append(f"- Top Warnings: {'; '.join(overall_impact_assessment['warnings'][:3])}")
        ai_analysis_parts.append(f"- Simulations: {preview_score['metrics']['successful_simulations']}/{preview_score['metrics']['total_simulations']} successful")
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # ==================== GENERATE ROW-LEVEL-ISSUES ====================
        row_level_issues = []
        
        # Extract row-level issues from simulated results
        for rule_idx, result in enumerate(simulated_results):
            if result.get("status") == "error":
                # Simulation failure - flag all affected rows as problematic
                try:
                    target_cols = result.get("target_columns", [])
                    rule_type = result.get("rule_type", "unknown")
                    
                    # Add one issue per affected column
                    for col_idx, col in enumerate(target_cols[:10]):  # Limit to 10 columns per rule
                        row_level_issues.append({
                            "row_index": 0,  # Indicates system-level issue, not specific row
                            "column": col,
                            "issue_type": "simulation_failed",
                            "severity": "critical",
                            "message": f"Simulation failed for rule on column '{col}': {result.get('error', 'Unknown error')}",
                            "value": None,
                            "rule_id": result.get("rule_id"),
                            "rule_type": rule_type
                        })
                except Exception as e:
                    pass
            else:
                # Extract row-level impacts from successful simulations
                changes = result.get("changes", {})
                impact_level = result.get("impact_level", "low")
                risk_assessment = result.get("risk_assessment", {})
                
                # High-impact changes - flag affected rows
                if impact_level == "high" or risk_assessment.get("is_risky"):
                    row_change = changes.get("row_change", 0)
                    row_change_pct = changes.get("row_change_percentage", 0)
                    
                    # For rows that will be removed (negative row_change)
                    if row_change < 0:
                        # Estimate affected rows based on operation type
                        affected_rows_count = min(abs(row_change), max(1, df.height // 100))  # Sample up to 1% of rows
                        
                        for row_idx in range(affected_rows_count):
                            row_level_issues.append({
                                "row_index": row_idx,
                                "column": "global",
                                "issue_type": "unsafe_operation",
                                "severity": "critical" if abs(row_change_pct) > 20 else "warning",
                                "message": f"Row will be affected by high-impact operation: {result.get('rule_description', 'Unknown rule')}. Total impact: {abs(row_change_pct):.1f}% rows affected",
                                "value": None,
                                "rule_id": result.get("rule_id"),
                                "impact_percentage": round(row_change_pct, 2)
                            })
                    
                    # Column-level changes that affect rows
                    col_changes = changes.get("column_level_changes", {})
                    for col_name, col_change_info in col_changes.items():
                        if isinstance(col_change_info, dict):
                            # High mean/median changes indicate significant value shifts
                            mean_change_pct = col_change_info.get("mean_change_pct", 0)
                            
                            if abs(mean_change_pct) > 30:
                                # Find rows with values far from mean (will be significantly affected)
                                if col_name in df.columns and df[col_name].dtype in [pl.Float64, pl.Int64, pl.Float32, pl.Int32]:
                                    col_data = df[col_name].drop_nulls()
                                    if len(col_data) > 0:
                                        col_mean = col_data.mean()
                                        col_std = col_data.std()
                                        
                                        # Find extreme rows (simplified for Polars)
                                        # We can't easily iterate rows like pandas, so we'll just add a generic warning
                                        # or sample a few if needed. For now, just a generic warning per column.
                                        row_level_issues.append({
                                            "row_index": 0,
                                            "column": col_name,
                                            "issue_type": "high_impact_change",
                                            "severity": "warning",
                                            "message": f"High-impact change on '{col_name}': value will change significantly ({abs(mean_change_pct):.1f}% mean shift)",
                                            "value": None,
                                            "rule_id": result.get("rule_id"),
                                            "change_percentage": round(mean_change_pct, 2)
                                        })
                            
                            if len(row_level_issues) >= 1000:
                                break
                
                # Risky operations detected
                if risk_assessment.get("is_risky"):
                    for risk_factor in risk_assessment.get("risk_factors", [])[:3]:
                        row_level_issues.append({
                            "row_index": 0,  # System-level risk indicator
                            "column": "global",
                            "issue_type": "preview_issue",
                            "severity": "critical",
                            "message": f"Risk detected: {risk_factor}",
                            "value": None,
                            "rule_id": result.get("rule_id")
                        })
            
            if len(row_level_issues) >= 1000:
                break
        
        # Calculate row-level-issues summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {
                "critical": 0,
                "warning": 0,
                "info": 0
            },
            "affected_rows": len(set(issue["row_index"] for issue in row_level_issues if issue["row_index"] != 0)),
            "affected_columns": list(set(issue["column"] for issue in row_level_issues))
        }
        
        for issue in row_level_issues:
            issue_type = issue.get("issue_type", "preview_issue")
            severity = issue.get("severity", "info")
            
            if issue_type not in issue_summary["by_type"]:
                issue_summary["by_type"][issue_type] = 0
            issue_summary["by_type"][issue_type] += 1
            
            if severity in issue_summary["by_severity"]:
                issue_summary["by_severity"][severity] += 1

        # Build results
        preview_data = {
            "preview_score": preview_score,
            "quality_status": quality_status,
            "preview_analysis": preview_analysis,
            "summary": f"Preview analysis completed. Quality: {quality_status}. Analyzed {len(preview_rules)} cleaning rules across {df.height} rows. Safety: {preview_analysis['execution_safety']}.",
            "impact_issues": _extract_impact_issues(simulated_results)[:100],
            "overrides": {
                "preview_rules": preview_rules,
                "impact_threshold_high": impact_threshold_high,
                "impact_threshold_medium": impact_threshold_medium,
                "confidence_level": confidence_level,
                "calculate_distributions": calculate_distributions,
                "compare_statistics": compare_statistics,
                "analyze_correlations": analyze_correlations,
                "accuracy_weight": accuracy_weight,
                "safety_weight": safety_weight,
                "completeness_weight": completeness_weight,
                "excellent_threshold": excellent_threshold,
                "good_threshold": good_threshold
            }
        }

        return {
            "status": "success",
            "agent_id": "cleanse-previewer",
            "agent_name": "Cleanse Previewer",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_analyzed": df.height,
                "total_rules_previewed": len(preview_rules),
                "high_impact_rules": overall_impact_assessment["high_impact_rules"],
                "medium_impact_rules": overall_impact_assessment["medium_impact_rules"],
                "low_impact_rules": overall_impact_assessment["low_impact_rules"],
                "safe_to_execute": overall_impact_assessment["safe_to_execute"],
                "total_warnings": len(overall_impact_assessment["warnings"])
            },
            "data": preview_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text,
            "row_level_issues": row_level_issues[:1000],
            "issue_summary": issue_summary
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "cleanse-previewer",
            "agent_name": "Cleanse Previewer",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }

def _profile_dataset(df: pl.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate comprehensive profile of dataset using Polars."""
    profile = {
        "row_count": df.height,
        "column_count": len(df.columns),
        "memory_usage_mb": df.estimated_size() / (1024 * 1024),
        "columns": {}
    }
    
    for col in df.columns:
        null_count = df[col].null_count()
        unique_count = df[col].n_unique()
        
        col_profile = {
            "dtype": str(df[col].dtype),
            "null_count": int(null_count),
            "null_percentage": round((null_count / df.height * 100) if df.height > 0 else 0, 2),
            "unique_count": int(unique_count),
            "unique_percentage": round((unique_count / df.height * 100) if df.height > 0 else 0, 2)
        }
        
        # Numeric columns
        if df[col].dtype in [pl.Float64, pl.Int64, pl.Float32, pl.Int32]:
            col_profile["statistics"] = {
                "mean": float(df[col].mean()) if null_count < df.height else None,
                "median": float(df[col].median()) if null_count < df.height else None,
                "std": float(df[col].std()) if null_count < df.height else None,
                "min": float(df[col].min()) if null_count < df.height else None,
                "max": float(df[col].max()) if null_count < df.height else None,
                "q25": float(df[col].quantile(0.25)) if null_count < df.height else None,
                "q75": float(df[col].quantile(0.75)) if null_count < df.height else None
            }
            
            if config.get("calculate_distributions"):
                # Calculate distribution metrics
                non_null = df[col].drop_nulls()
                if len(non_null) > 0:
                    col_profile["distribution"] = {
                        "skewness": float(non_null.skew()),
                        "kurtosis": float(non_null.kurtosis())
                    }
        
        # String columns
        elif df[col].dtype == pl.Utf8:
            # Mode calculation in Polars
            mode_df = df[col].mode()
            most_common = str(mode_df[0]) if len(mode_df) > 0 else None
            
            # Count of most common
            most_common_count = 0
            if most_common is not None:
                most_common_count = int(df.filter(pl.col(col) == most_common).height)

            col_profile["statistics"] = {
                "most_common": most_common,
                "most_common_count": most_common_count,
                "avg_length": float(df[col].str.len_bytes().mean()) if null_count < df.height else None
            }
        
        profile["columns"][col] = col_profile
    
    return profile

def _simulate_cleaning_rule(df: pl.DataFrame, rule: Dict[str, Any]) -> Tuple[pl.DataFrame, List[str]]:
    """Simulate application of a cleaning rule without modifying original data."""
    log = []
    rule_type = rule.get("type", "unknown")
    
    if rule_type == "drop_nulls":
        # Drop rows with nulls in specified columns
        target_cols = rule.get("target_columns", [])
        if target_cols:
            original_count = df.height
            df = df.drop_nulls(subset=target_cols)
            log.append(f"Dropped {original_count - df.height} rows with nulls in {target_cols}")
    
    elif rule_type == "impute_nulls":
        # Impute nulls with specified strategy
        target_cols = rule.get("target_columns", [])
        strategy = rule.get("strategy", "mean")
        
        for col in target_cols:
            if col not in df.columns:
                continue
            
            null_count = df[col].null_count()
            
            if strategy == "mean" and df[col].dtype in [pl.Float64, pl.Int64, pl.Float32, pl.Int32]:
                mean_val = df[col].mean()
                df = df.with_columns(pl.col(col).fill_null(mean_val))
                log.append(f"Imputed {null_count} nulls in '{col}' with mean")
            elif strategy == "median" and df[col].dtype in [pl.Float64, pl.Int64, pl.Float32, pl.Int32]:
                median_val = df[col].median()
                df = df.with_columns(pl.col(col).fill_null(median_val))
                log.append(f"Imputed {null_count} nulls in '{col}' with median")
            elif strategy == "mode":
                mode_val = df[col].mode()
                if len(mode_val) > 0:
                    df = df.with_columns(pl.col(col).fill_null(mode_val[0]))
                    log.append(f"Imputed {null_count} nulls in '{col}' with mode")
            elif strategy == "constant":
                fill_value = rule.get("fill_value", 0)
                df = df.with_columns(pl.col(col).fill_null(fill_value))
                log.append(f"Imputed {null_count} nulls in '{col}' with constant: {fill_value}")
    
    elif rule_type == "remove_outliers":
        # Remove outliers using specified method
        target_cols = rule.get("target_columns", [])
        method = rule.get("method", "iqr")
        
        for col in target_cols:
            if col not in df.columns or df[col].dtype not in [pl.Float64, pl.Int64, pl.Float32, pl.Int32]:
                continue
            
            original_count = df.height
            
            if method == "iqr":
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                multiplier = rule.get("iqr_multiplier", 1.5)
                
                lower_bound = Q1 - multiplier * IQR
                upper_bound = Q3 + multiplier * IQR
                
                df = df.filter((pl.col(col) >= lower_bound) & (pl.col(col) <= upper_bound))
                
            elif method == "z_score":
                threshold = rule.get("z_threshold", 3.0)
                mean_val = df[col].mean()
                std_val = df[col].std()
                
                if std_val != 0:
                    df = df.filter(((pl.col(col) - mean_val).abs() / std_val) < threshold)
            
            log.append(f"Removed {original_count - df.height} outliers from '{col}' using {method}")
    
    elif rule_type == "drop_duplicates":
        # Drop duplicate rows
        subset_cols = rule.get("target_columns", None)
        original_count = df.height
        df = df.unique(subset=subset_cols, keep='first')
        log.append(f"Removed {original_count - df.height} duplicate rows")
    
    elif rule_type == "drop_columns":
        # Drop specified columns
        target_cols = rule.get("target_columns", [])
        existing_cols = [col for col in target_cols if col in df.columns]
        df = df.drop(existing_cols)
        log.append(f"Dropped {len(existing_cols)} columns: {existing_cols}")
    
    elif rule_type == "convert_types":
        # Convert column types
        target_cols = rule.get("target_columns", [])
        target_type = rule.get("target_type", "float")
        
        for col in target_cols:
            if col not in df.columns:
                continue
            
            try:
                if target_type == "numeric":
                    df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False))
                elif target_type == "datetime":
                    df = df.with_columns(pl.col(col).str.to_datetime(strict=False))
                elif target_type == "string":
                    df = df.with_columns(pl.col(col).cast(pl.Utf8))
                
                log.append(f"Converted '{col}' to {target_type}")
            except Exception as e:
                log.append(f"Failed to convert '{col}' to {target_type}: {str(e)}")
    
    else:
        log.append(f"Unknown rule type: {rule_type}")
    
    return df, log

def _calculate_impact(
    original_profile: Dict[str, Any],
    simulated_profile: Dict[str, Any],
    rule: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate impact of cleaning rule by comparing profiles."""
    
    # Row count change
    row_change = simulated_profile["row_count"] - original_profile["row_count"]
    row_change_pct = (row_change / original_profile["row_count"] * 100) if original_profile["row_count"] > 0 else 0
    
    # Column count change
    col_change = simulated_profile["column_count"] - original_profile["column_count"]
    
    # Detailed changes per column
    column_changes = {}
    for col in original_profile["columns"].keys():
        if col not in simulated_profile["columns"]:
            column_changes[col] = {"status": "removed"}
            continue
        
        orig_col = original_profile["columns"][col]
        sim_col = simulated_profile["columns"][col]
        
        changes = {
            "null_count_change": sim_col["null_count"] - orig_col["null_count"],
            "null_percentage_change": round(sim_col["null_percentage"] - orig_col["null_percentage"], 2),
            "unique_count_change": sim_col["unique_count"] - orig_col["unique_count"]
        }
        
        # Statistical changes for numeric columns
        if "statistics" in orig_col and "statistics" in sim_col:
            if orig_col["statistics"].get("mean") is not None and sim_col["statistics"].get("mean") is not None:
                changes["mean_change"] = round(sim_col["statistics"]["mean"] - orig_col["statistics"]["mean"], 2)
                changes["mean_change_pct"] = round(
                    ((sim_col["statistics"]["mean"] - orig_col["statistics"]["mean"]) / orig_col["statistics"]["mean"] * 100)
                    if orig_col["statistics"]["mean"] != 0 else 0,
                    2
                )
            
            if orig_col["statistics"].get("median") is not None and sim_col["statistics"].get("median") is not None:
                changes["median_change"] = round(sim_col["statistics"]["median"] - orig_col["statistics"]["median"], 2)
        
        column_changes[col] = changes
    
    # Determine impact level
    high_threshold = config.get("high_threshold", 10)
    medium_threshold = config.get("medium_threshold", 5)
    
    if abs(row_change_pct) >= high_threshold or col_change != 0:
        impact_level = "high"
    elif abs(row_change_pct) >= medium_threshold:
        impact_level = "medium"
    else:
        impact_level = "low"
    
    # Risk assessment
    is_risky = False
    risk_factors = []
    
    if abs(row_change_pct) > 20:
        is_risky = True
        risk_factors.append(f"Large data loss: {abs(row_change_pct):.1f}% of rows will be removed")
    
    if col_change < 0:
        is_risky = True
        risk_factors.append(f"{abs(col_change)} columns will be permanently removed")
    
    # Check for significant statistical shifts
    for col, changes in column_changes.items():
        if "mean_change_pct" in changes and abs(changes["mean_change_pct"]) > 50:
            risk_factors.append(f"Large statistical shift in '{col}': mean changes by {changes['mean_change_pct']:.1f}%")
    
    risk_assessment = {
        "is_risky": is_risky,
        "risk_level": "high" if is_risky else "low",
        "risk_factors": risk_factors
    }
    
    # Generate recommendations
    recommendations = []
    
    if abs(row_change_pct) > 10:
        recommendations.append({
            "priority": "high",
            "action": "review_data_loss",
            "reason": f"This operation will affect {abs(row_change_pct):.1f}% of your data"
        })
    
    if is_risky:
        recommendations.append({
            "priority": "high",
            "action": "create_backup",
            "reason": "High-risk operation detected. Create a backup before proceeding"
        })
    
    if impact_level == "low":
        recommendations.append({
            "priority": "low",
            "action": "safe_to_proceed",
            "reason": "This operation has minimal impact on your data"
        })
    
    return {
        "original_metrics": {
            "total_rows": original_profile["row_count"],
            "total_columns": original_profile["column_count"],
            "memory_mb": round(original_profile["memory_usage_mb"], 2)
        },
        "preview_metrics": {
            "total_rows": simulated_profile["row_count"],
            "total_columns": simulated_profile["column_count"],
            "memory_mb": round(simulated_profile["memory_usage_mb"], 2)
        },
        "changes": {
            "row_change": row_change,
            "row_change_percentage": round(row_change_pct, 2),
            "column_change": col_change,
            "memory_change_mb": round(simulated_profile["memory_usage_mb"] - original_profile["memory_usage_mb"], 2),
            "column_level_changes": column_changes
        },
        "impact_level": impact_level,
        "risk_assessment": risk_assessment,
        "recommendations": recommendations
    }

def _calculate_preview_score(
    original_profile: Dict[str, Any],
    simulated_results: List[Dict[str, Any]],
    overall_impact: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate preview confidence score."""
    
    # Accuracy: How well we can predict the outcome
    successful_simulations = sum(1 for r in simulated_results if r.get("status") != "error")
    accuracy_score = (successful_simulations / len(simulated_results) * 100) if len(simulated_results) > 0 else 100
    
    # Safety: How safe the operations are
    safety_score = 100
    if overall_impact["high_impact_rules"] > 0:
        safety_score -= overall_impact["high_impact_rules"] * 15
    if overall_impact["medium_impact_rules"] > 0:
        safety_score -= overall_impact["medium_impact_rules"] * 5
    if not overall_impact["safe_to_execute"]:
        safety_score -= 20
    safety_score = max(0, safety_score)
    
    # Completeness: How comprehensive the preview is
    completeness_score = 100
    if len(simulated_results) == 0:
        completeness_score = 0
    
    # Calculate weighted overall score
    accuracy_weight = config.get("accuracy_weight", 0.4)
    safety_weight = config.get("safety_weight", 0.3)
    completeness_weight = config.get("completeness_weight", 0.3)
    
    overall_score = (
        accuracy_score * accuracy_weight +
        safety_score * safety_weight +
        completeness_score * completeness_weight
    )
    
    return {
        "overall_score": round(overall_score, 1),
        "metrics": {
            "accuracy_score": round(accuracy_score, 1),
            "safety_score": round(safety_score, 1),
            "completeness_score": round(completeness_score, 1),
            "successful_simulations": successful_simulations,
            "total_simulations": len(simulated_results),
            "high_impact_operations": overall_impact["high_impact_rules"],
            "safe_to_execute": overall_impact["safe_to_execute"]
        }
    }

def _generate_preview_recommendations(
    simulated_results: List[Dict[str, Any]],
    overall_impact: Dict[str, Any],
    preview_score: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Generate recommendations based on preview analysis."""
    recommendations = []
    
    if not overall_impact["safe_to_execute"]:
        recommendations.append({
            "priority": "critical",
            "action": "review_high_risk_rules",
            "reason": f"Found {overall_impact['high_impact_rules']} high-risk operations that require careful review",
            "affected_rules": [r["rule_id"] for r in simulated_results if r.get("impact_level") == "high"]
        })
    
    if overall_impact["high_impact_rules"] > 0:
        recommendations.append({
            "priority": "high",
            "action": "backup_data",
            "reason": "High-impact operations detected. Create a backup before proceeding"
        })
    
    if preview_score["overall_score"] >= 90:
        recommendations.append({
            "priority": "low",
            "action": "proceed_with_confidence",
            "reason": "Preview analysis shows low risk. Safe to proceed with cleaning operations"
        })
    elif preview_score["overall_score"] >= 75:
        recommendations.append({
            "priority": "medium",
            "action": "review_before_execution",
            "reason": "Some operations may have moderate impact. Review changes before proceeding"
        })
    else:
        recommendations.append({
            "priority": "high",
            "action": "reconsider_strategy",
            "reason": "Preview shows concerning changes. Consider revising cleaning strategy"
        })
    
    # Rule-specific recommendations
    for result in simulated_results:
        if result.get("status") == "error":
            recommendations.append({
                "priority": "high",
                "action": "fix_rule_error",
                "reason": f"Rule '{result.get('rule_description')}' failed: {result.get('error')}",
                "affected_rules": [result.get("rule_id")]
            })
    
    return recommendations

def _extract_impact_issues(simulated_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract issues from simulated results for reporting."""
    issues = []
    
    for result in simulated_results:
        if result.get("status") == "error":
            issues.append({
                "issue_type": "simulation_error",
                "rule_id": result.get("rule_id"),
                "severity": "high",
                "description": f"Failed to simulate rule: {result.get('error')}"
            })
            continue
        
        if result.get("impact_level") == "high":
            changes = result.get("changes", {})
            issues.append({
                "issue_type": "high_impact_operation",
                "rule_id": result.get("rule_id"),
                "severity": "high",
                "description": f"High impact: {changes.get('row_change_percentage', 0):.1f}% row change",
                "details": {
                    "rows_affected": changes.get("row_change", 0),
                    "columns_affected": changes.get("column_change", 0)
                }
            })
        
        if result.get("risk_assessment", {}).get("is_risky"):
            for risk_factor in result.get("risk_assessment", {}).get("risk_factors", []):
                issues.append({
                    "issue_type": "risk_detected",
                    "rule_id": result.get("rule_id"),
                    "severity": "high",
                    "description": risk_factor
                })
    
    return issues
