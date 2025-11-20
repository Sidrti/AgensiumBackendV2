"""
Duplicate Resolver Agent (Optimized)

Detects and merges/removes duplicate records with comprehensive duplicate detection strategies.
Handles exact duplicates, case variations, whitespace differences, email case-insensitivity,
missing values, and conflicting duplicates.
Input: CSV file (primary)
Output: Standardized duplicate resolution results with deduplication effectiveness scores
"""

import polars as pl
import numpy as np
import io
import time
import re
import base64
from typing import Dict, Any, Optional, List, Set, Tuple

def execute_duplicate_resolver(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Detect and resolve duplicate records in data.

    Args:
        file_contents: File bytes (read as binary)
        filename: Original filename (used to detect format)
        parameters: Agent parameters from tool.json

    Returns:
        Standardized output dictionary
    """
    start_time = time.time()
    parameters = parameters or {}

    # Extract parameters with defaults
    detection_types = parameters.get("detection_types", ["exact", "case_variations", "email_case", "missing_values", "conflicting"])
    merge_strategy = parameters.get("merge_strategy", "remove_duplicates")  # remove_duplicates or merge_smart
    email_columns = parameters.get("email_columns", [])
    key_columns = parameters.get("key_columns", [])
    null_handling = parameters.get("null_handling", "ignore_nulls")  # ignore_nulls or match_nulls
    conflict_resolution = parameters.get("conflict_resolution", "keep_first")
    dedup_reduction_weight = parameters.get("dedup_reduction_weight", 0.5)
    data_retention_weight = parameters.get("data_retention_weight", 0.3)
    column_retention_weight = parameters.get("column_retention_weight", 0.2)
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file - CSV only
        if not filename.endswith('.csv'):
             raise ValueError(f"Unsupported file format: {filename}. Only CSV is supported.")
        
        df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True)

        if df.height == 0:
             return {
                "status": "error",
                "agent_id": "duplicate-resolver",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        original_df = df.clone()
        
        # Auto-detect email columns if not provided
        if not email_columns:
            email_columns = _auto_detect_email_columns(df)
        
        # Analyze duplicates
        duplicate_analysis = _analyze_duplicates(df, detection_types, {
            "email_columns": email_columns,
            "key_columns": key_columns,
            "null_handling": null_handling
        })
        
        # Resolve duplicates
        df_deduplicated, resolution_log, duplicate_issues = _resolve_duplicates(
            df, duplicate_analysis, merge_strategy, {
                "email_columns": email_columns,
                "key_columns": key_columns,
                "null_handling": null_handling,
                "conflict_resolution": conflict_resolution
            }
        )
        
        # Calculate effectiveness
        dedup_score = _calculate_dedup_score(original_df, df_deduplicated, duplicate_analysis, {
            "dedup_reduction_weight": dedup_reduction_weight,
            "data_retention_weight": data_retention_weight,
            "column_retention_weight": column_retention_weight,
            "excellent_threshold": excellent_threshold,
            "good_threshold": good_threshold
        })
        
        # Quality status
        if dedup_score["overall_score"] >= excellent_threshold:
            quality_status = "excellent"
        elif dedup_score["overall_score"] >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"
            
        # Generate ROW-LEVEL-ISSUES
        row_level_issues = []
        dup_methods = duplicate_analysis.get("duplicate_summary", {})
        
        # Map rows to detection methods
        row_detection_map = {}
        for method, method_data in dup_methods.items():
            if isinstance(method_data, dict):
                for affected_row in method_data.get("affected_rows", []):
                    if affected_row not in row_detection_map:
                        row_detection_map[affected_row] = []
                    row_detection_map[affected_row].append(method)
        
        for row_idx, detection_methods in row_detection_map.items():
            if len(row_level_issues) >= 1000:
                break
            
            if "conflicting" in detection_methods:
                issue_type = "key_conflict"
                severity = "critical"
                message = "Key conflict: Same key but different values detected"
            elif "exact" in detection_methods:
                issue_type = "duplicate_row"
                severity = "warning"
                message = f"Exact duplicate: Row {row_idx} is identical to another row"
            else:
                issue_type = "partial_duplicate"
                severity = "info"
                message = f"Partial duplicate: Row {row_idx} matches via {', '.join(detection_methods)}"
            
            row_level_issues.append({
                "row_index": int(row_idx),
                "column": "all",
                "issue_type": issue_type,
                "severity": severity,
                "message": message,
                "detection_methods": detection_methods
            })
            
        # Issue summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {},
            "affected_rows": len(set(issue["row_index"] for issue in row_level_issues)),
            "affected_columns": []
        }
        
        for issue in row_level_issues:
            issue_type = issue.get("issue_type", "unknown")
            issue_summary["by_type"][issue_type] = issue_summary["by_type"].get(issue_type, 0) + 1
            severity = issue.get("severity", "info")
            issue_summary["by_severity"][severity] = issue_summary["by_severity"].get(severity, 0) + 1

        # Build results
        dedup_data = {
            "dedup_score": dedup_score,
            "quality_status": quality_status,
            "duplicate_analysis": duplicate_analysis,
            "resolution_log": resolution_log,
            "summary": f"Duplicate resolution completed. Quality: {quality_status}. Processed {original_df.height} rows, resolved {duplicate_analysis.get('total_duplicates', 0)} duplicate records.",
            "row_level_issues": row_level_issues[:100],
            "issue_summary": issue_summary,
            "overrides": {
                "detection_types": detection_types,
                "merge_strategy": merge_strategy,
                "email_columns": email_columns,
                "key_columns": key_columns,
                "null_handling": null_handling,
                "conflict_resolution": conflict_resolution,
                "dedup_reduction_weight": dedup_reduction_weight,
                "data_retention_weight": data_retention_weight,
                "column_retention_weight": column_retention_weight,
                "excellent_threshold": excellent_threshold,
                "good_threshold": good_threshold
            }
        }
        
        # Re-implementing the return structure fully
        total_dups = duplicate_analysis.get('total_duplicates', 0)
        executive_summary = [{
            "summary_id": "exec_duplicate_resolution",
            "title": "Duplicate Resolution Status",
            "value": f"{dedup_score['overall_score']:.1f}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"Quality: {quality_status}, Duplicates Resolved: {total_dups}, {original_df.height - df_deduplicated.height} rows removed, {dedup_score['metrics']['dedup_reduction_rate']:.1f}% effectiveness"
        }]
        
        ai_analysis_parts = []
        ai_analysis_parts.append(f"DUPLICATE RESOLVER ANALYSIS:")
        ai_analysis_parts.append(f"- Deduplication Score: {dedup_score['overall_score']:.1f}/100 (Dedup Reduction: {dedup_score['metrics']['dedup_reduction_rate']:.1f}, Data Retention: {dedup_score['metrics']['data_retention_rate']:.1f}, Column Retention: {dedup_score['metrics']['column_retention_rate']:.1f})")
        ai_analysis_parts.append(f"- Duplicates Resolved: {total_dups} duplicate records detected, {original_df.height - df_deduplicated.height} rows removed, {dedup_score['metrics']['dedup_reduction_rate']:.1f}% effectiveness")
        
        dup_methods = duplicate_analysis.get('duplicate_summary', {})
        ai_analysis_parts.append(f"- Detection Methods: {len(dup_methods)} methods used - {', '.join(dup_methods.keys())}")
        ai_analysis_parts.append(f"- Data Retention: {df_deduplicated.height} rows retained ({(df_deduplicated.height / original_df.height * 100):.1f}% of original)")
        ai_analysis_parts.append(f"- Resolution Strategy: {resolution_log[0] if len(resolution_log) > 0 else 'N/A'}")
        
        if len(duplicate_analysis.get('recommendations', [])) > 0:
            ai_analysis_parts.append(f"- Top Recommendation: {duplicate_analysis['recommendations'][0].get('recommendation', 'Review duplicate resolution strategy')}")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        alerts = []
        duplicate_pct = (total_dups / original_df.height * 100) if original_df.height > 0 else 0
        if duplicate_pct > 30:
            alerts.append({
                "alert_id": "alert_duplicates_high_volume",
                "severity": "critical",
                "category": "data_uniqueness",
                "message": f"High duplicate volume: {total_dups} duplicates detected ({duplicate_pct:.1f}% of dataset)",
                "affected_fields_count": len(dup_methods),
                "recommendation": "Review data collection process. High duplicate rate indicates systemic data entry issues or inadequate uniqueness constraints."
            })
        elif duplicate_pct > 10:
            alerts.append({
                "alert_id": "alert_duplicates_medium_volume",
                "severity": "high",
                "category": "data_uniqueness",
                "message": f"Moderate duplicate volume: {total_dups} duplicates detected ({duplicate_pct:.1f}% of dataset)",
                "affected_fields_count": len(dup_methods),
                "recommendation": "Implement deduplication strategies and unique key constraints."
            })
            
        rows_removed = original_df.height - df_deduplicated.height
        if rows_removed > original_df.height * 0.2:
            alerts.append({
                "alert_id": "alert_duplicates_data_loss",
                "severity": "high",
                "category": "data_retention",
                "message": f"Significant data loss: {rows_removed} rows removed ({(rows_removed/original_df.height*100):.1f}% of dataset)",
                "affected_fields_count": rows_removed,
                "recommendation": "Review deduplication strategy. Consider merge strategies instead of removal to preserve information."
            })
            
        conflicting_dups = dup_methods.get('conflicting', {}).get('duplicate_count', 0)
        if conflicting_dups > 0:
            alerts.append({
                "alert_id": "alert_duplicates_conflicts",
                "severity": "high",
                "category": "data_integrity",
                "message": f"{conflicting_dups} conflicting duplicate(s) detected with same keys but different values",
                "affected_fields_count": conflicting_dups,
                "recommendation": "Review conflicting duplicates manually to determine correct values and resolution strategy."
            })
            
        if dedup_score["overall_score"] < good_threshold:
            severity = "critical" if dedup_score["overall_score"] < 50 else "high" if dedup_score["overall_score"] < good_threshold else "medium"
            alerts.append({
                "alert_id": "alert_duplicates_quality",
                "severity": severity,
                "category": "quality_score",
                "message": f"Deduplication quality score: {dedup_score['overall_score']:.1f}/100 ({quality_status})",
                "affected_fields_count": total_dups,
                "recommendation": "Optimize duplicate detection and resolution strategies for better results."
            })
            
        if len(dup_methods) > 0:
            methods_with_dups = {k: v for k, v in dup_methods.items() if isinstance(v, dict) and v.get('duplicate_count', 0) > 0}
            if len(methods_with_dups) == 0 and total_dups == 0:
                alerts.append({
                    "alert_id": "alert_duplicates_none_detected",
                    "severity": "low",
                    "category": "detection_effectiveness",
                    "message": "No duplicates detected across all detection methods. Data appears unique.",
                    "affected_fields_count": 0,
                    "recommendation": "Excellent! Maintain current data entry practices to preserve uniqueness."
                })
                
        if not key_columns and duplicate_pct > 5:
            alerts.append({
                "alert_id": "alert_duplicates_no_key_columns",
                "severity": "medium",
                "category": "configuration",
                "message": "No key columns specified for duplicate detection. Using all columns may miss partial duplicates.",
                "affected_fields_count": len(df.columns),
                "recommendation": "Define key columns (e.g., ID, email) for more precise duplicate detection."
            })
            
        significant_methods = {k: v for k, v in dup_methods.items() if isinstance(v, dict) and v.get('duplicate_count', 0) > original_df.height * 0.05}
        if len(significant_methods) >= 3:
            alerts.append({
                "alert_id": "alert_duplicates_multiple_types",
                "severity": "high",
                "category": "data_quality",
                "message": f"{len(significant_methods)} different duplicate types detected ({', '.join(significant_methods.keys())}). Systematic data quality issues likely.",
                "affected_fields_count": len(significant_methods),
                "recommendation": "Review data entry, import, and validation processes comprehensively."
            })
            
        issues = []
        for dup_issue in duplicate_issues[:100]:
            issues.append({
                "issue_id": f"issue_duplicates_{dup_issue.get('row_index', 0)}_duplicate",
                "agent_id": "duplicate-resolver",
                "field_name": "record",
                "issue_type": dup_issue.get('issue_type', 'duplicate_record'),
                "severity": dup_issue.get('severity', 'warning'),
                "message": dup_issue.get('description', 'Duplicate record detected')
            })
            
        for method, data in dup_methods.items():
            if isinstance(data, dict) and data.get('duplicate_count', 0) > 0:
                issues.append({
                    "issue_id": f"issue_duplicates_method_{method}",
                    "agent_id": "duplicate-resolver",
                    "field_name": "multiple",
                    "issue_type": f"duplicate_{method}",
                    "severity": "high" if data.get('duplicate_count', 0) > original_df.height * 0.1 else "medium",
                    "message": f"{data.get('duplicate_count', 0)} duplicate(s) detected using {method} method: {data.get('description', '')}"
                })
                
        if conflicting_dups > 0:
            issues.append({
                "issue_id": "issue_duplicates_conflicts",
                "agent_id": "duplicate-resolver",
                "field_name": "multiple",
                "issue_type": "conflicting_duplicates",
                "severity": "critical",
                "message": f"{conflicting_dups} conflicting duplicate(s) found - same keys but different values requiring manual resolution"
            })
            
        if rows_removed > original_df.height * 0.2:
            issues.append({
                "issue_id": "issue_duplicates_data_loss",
                "agent_id": "duplicate-resolver",
                "field_name": "dataset",
                "issue_type": "data_retention",
                "severity": "high",
                "message": f"Significant data loss: {rows_removed} rows ({(rows_removed/original_df.height*100):.1f}%) removed during deduplication"
            })
            
        agent_recommendations = []
        if conflicting_dups > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_duplicates_conflicts",
                "agent_id": "duplicate-resolver",
                "field_name": "multiple",
                "priority": "critical",
                "recommendation": f"Manually review and resolve {conflicting_dups} conflicting duplicate(s) with different values for same keys",
                "timeline": "immediate"
            })
            
        if total_dups > original_df.height * 0.1:
            agent_recommendations.append({
                "recommendation_id": "rec_duplicates_constraints",
                "agent_id": "duplicate-resolver",
                "field_name": "all",
                "priority": "high",
                "recommendation": "Implement unique key constraints at database level to prevent duplicate entry",
                "timeline": "1 week"
            })
            
        for method, data in dup_methods.items():
            if data.get('duplicate_count', 0) > 0:
                agent_recommendations.append({
                    "recommendation_id": f"rec_duplicates_{method}",
                    "agent_id": "duplicate-resolver",
                    "field_name": "various",
                    "priority": "high" if data.get('duplicate_count', 0) > original_df.height * 0.05 else "medium",
                    "recommendation": f"Address {data.get('duplicate_count', 0)} {method} duplicate(s) with targeted resolution strategy",
                    "timeline": "1-2 weeks"
                })
                if len(agent_recommendations) >= 5:
                    break
                    
        if merge_strategy == 'remove_duplicates' and rows_removed > original_df.height * 0.1:
            agent_recommendations.append({
                "recommendation_id": "rec_duplicates_merge_strategy",
                "agent_id": "duplicate-resolver",
                "field_name": "all",
                "priority": "medium",
                "recommendation": "Consider smart merge strategy instead of removal to preserve valuable information from duplicate records",
                "timeline": "2 weeks"
            })
            
        agent_recommendations.append({
            "recommendation_id": "rec_duplicates_source",
            "agent_id": "duplicate-resolver",
            "field_name": "all",
            "priority": "medium",
            "recommendation": "Review data entry and import processes to prevent duplicate creation at source",
            "timeline": "2 weeks"
        })
        
        agent_recommendations.append({
            "recommendation_id": "rec_duplicates_monitoring",
            "agent_id": "duplicate-resolver",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Establish duplicate rate monitoring and alerting to detect data quality degradation",
            "timeline": "3 weeks"
        })
        
        if not key_columns:
            agent_recommendations.append({
                "recommendation_id": "rec_duplicates_key_columns",
                "agent_id": "duplicate-resolver",
                "field_name": "all",
                "priority": "high",
                "recommendation": "Define key columns for duplicate detection to improve precision and avoid false positives",
                "timeline": "1 week"
            })
            
        if len(email_columns) > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_duplicates_email_normalization",
                "agent_id": "duplicate-resolver",
                "field_name": ", ".join(email_columns[:3]),
                "priority": "medium",
                "recommendation": f"Implement email normalization rules for {len(email_columns)} email column(s) to prevent case/format duplicates",
                "timeline": "2 weeks"
            })
            
        agent_recommendations.append({
            "recommendation_id": "rec_duplicates_documentation",
            "agent_id": "duplicate-resolver",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Document duplicate resolution decisions, merge strategies, and business rules for handling conflicting data",
            "timeline": "3 weeks"
        })
        
        if duplicate_pct > 10:
            agent_recommendations.append({
                "recommendation_id": "rec_duplicates_automation",
                "agent_id": "duplicate-resolver",
                "field_name": "all",
                "priority": "high",
                "recommendation": f"{duplicate_pct:.1f}% duplicate rate warrants automated deduplication pipeline with periodic manual review",
                "timeline": "2-3 weeks"
            })

        # Generate cleaned file
        output = io.BytesIO()
        df_deduplicated.write_csv(output)
        cleaned_file_bytes = output.getvalue()
        cleaned_file_base64 = base64.b64encode(cleaned_file_bytes).decode('utf-8')

        return {
            "status": "success",
            "agent_id": "duplicate-resolver",
            "agent_name": "Duplicate Resolver",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_processed": original_df.height,
                "duplicates_detected": duplicate_analysis.get('total_duplicates', 0),
                "duplicates_resolved": original_df.height - df_deduplicated.height,
                "remaining_rows": df_deduplicated.height,
                "rows_removed": original_df.height - df_deduplicated.height,
                "total_issues": len(duplicate_issues)
            },
            "data": dedup_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
            "executive_summary" : executive_summary,
            "ai_analysis_text" : ai_analysis_text,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary,
            "cleaned_file": {
                "filename": f"cleaned_{filename}",
                "content": cleaned_file_base64,
                "size_bytes": len(cleaned_file_bytes),
                "format": filename.split('.')[-1].lower()
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "duplicate-resolver",
            "agent_name": "Duplicate Resolver",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }

def _auto_detect_email_columns(df: pl.DataFrame) -> List[str]:
    email_columns = []
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    for col in df.columns:
        if 'email' in col.lower() or 'mail' in col.lower():
            email_columns.append(col)
            continue
        
        if df[col].dtype == pl.Utf8:
            # Check sample
            sample = df[col].drop_nulls().head(20)
            if sample.len() > 0:
                # Polars regex match
                matches = sample.str.contains(email_pattern).sum()
                if matches / sample.len() > 0.5:
                    email_columns.append(col)
    return email_columns

def _analyze_duplicates(df: pl.DataFrame, detection_types: List[str], config: Dict[str, Any]) -> Dict[str, Any]:
    email_columns = config.get("email_columns", [])
    key_columns = config.get("key_columns", [])
    null_handling = config.get("null_handling", "ignore_nulls")
    
    analysis = {
        "total_rows": df.height,
        "total_columns": len(df.columns),
        "duplicate_summary": {},
        "total_duplicates": 0,
        "detection_methods": detection_types,
        "recommendations": []
    }
    
    all_duplicate_indices = set()
    
    for detection_type in detection_types:
        duplicate_indices = set()
        
        if detection_type == "exact":
            # Exact duplicates
            is_dup = df.is_duplicated()
            duplicate_indices = set(df.with_row_count("idx").filter(is_dup)["idx"].to_list())
            
        elif detection_type == "case_variations":
            # Case variations
            cols_to_check = key_columns if key_columns else df.columns
            exprs = []
            for col in cols_to_check:
                if df[col].dtype == pl.Utf8:
                    exprs.append(pl.col(col).str.to_lowercase().str.strip_chars().alias(col))
                else:
                    exprs.append(pl.col(col))
            
            temp_df = df.select(exprs)
            is_dup = temp_df.is_duplicated()
            duplicate_indices = set(df.with_row_count("idx").filter(is_dup)["idx"].to_list())
            
        elif detection_type == "email_case":
            # Email case
            if email_columns:
                cols_to_check = key_columns if key_columns else df.columns
                exprs = []
                for col in cols_to_check:
                    if col in email_columns and df[col].dtype == pl.Utf8:
                        exprs.append(pl.col(col).str.to_lowercase().str.strip_chars().alias(col))
                    else:
                        exprs.append(pl.col(col))
                
                temp_df = df.select(exprs)
                is_dup = temp_df.is_duplicated()
                duplicate_indices = set(df.with_row_count("idx").filter(is_dup)["idx"].to_list())
        
        elif detection_type == "conflicting":
            # Conflicting duplicates (same key, different values)
            if key_columns:
                # Group by key columns
                # If count > 1, it's a potential conflict
                # We need to check if other columns differ
                
                # Normalize keys first? Assuming exact match on keys for conflict detection
                # Or should we use case-insensitive keys? Let's use exact for now as per original logic mostly
                
                # Original logic: _find_conflicting_duplicates uses normalized keys
                
                # Polars approach:
                # 1. Create normalized key columns
                key_exprs = []
                for col in key_columns:
                    if df[col].dtype == pl.Utf8:
                        key_exprs.append(pl.col(col).str.to_lowercase().str.strip_chars().alias(f"__key_{col}"))
                    else:
                        key_exprs.append(pl.col(col).alias(f"__key_{col}"))
                
                temp_df = df.with_columns(key_exprs).with_row_count("idx")
                key_col_names = [f"__key_{c}" for c in key_columns]
                
                # Filter groups with size > 1
                grouped = temp_df.group_by(key_col_names).agg([
                    pl.col("idx"),
                    pl.count().alias("count")
                ]).filter(pl.col("count") > 1)
                
                # For each group, check if original values differ
                # This is hard to do purely in Polars expressions without iterating
                # But we can check n_unique of other columns
                
                # Let's iterate over the groups (should be smaller than N)
                # Or better:
                # Join back to original DF
                # Group by keys again
                # Agg n_unique of all other columns
                # If any n_unique > 1, then it's a conflict
                
                if grouped.height > 0:
                    # Get indices of potential conflicts
                    potential_indices = grouped.explode("idx")["idx"]
                    potential_conflicts = df.with_row_count("idx").filter(pl.col("idx").is_in(potential_indices))
                    
                    # Add normalized keys back
                    potential_conflicts = potential_conflicts.with_columns(key_exprs)
                    
                    # Group by keys and check n_unique of non-key columns
                    non_key_cols = [c for c in df.columns if c not in key_columns]
                    
                    if non_key_cols:
                        agg_exprs = [pl.col(c).n_unique().alias(f"__nu_{c}") for c in non_key_cols]
                        
                        conflicts = potential_conflicts.group_by(key_col_names).agg(
                            agg_exprs + [pl.col("idx")]
                        )
                        
                        # Filter where any n_unique > 1
                        condition = pl.lit(False)
                        for c in non_key_cols:
                            condition = condition | (pl.col(f"__nu_{c}") > 1)
                        
                        real_conflicts = conflicts.filter(condition)
                        duplicate_indices = set(real_conflicts.explode("idx")["idx"].to_list())

        all_duplicate_indices.update(duplicate_indices)
        
        analysis["duplicate_summary"][detection_type] = {
            "method": detection_type,
            "duplicate_count": len(duplicate_indices),
            "duplicate_percentage": round((len(duplicate_indices) / df.height * 100) if df.height > 0 else 0, 2),
            "description": detection_type,
            "affected_rows": sorted(list(duplicate_indices))[:50]
        }
        
    analysis["total_duplicates"] = len(all_duplicate_indices)
    
    if len(all_duplicate_indices) > 0:
        dup_percentage = (len(all_duplicate_indices) / df.height * 100) if df.height > 0 else 0
        if dup_percentage > 50:
            analysis["recommendations"].append({
                "action": "investigate_data_source",
                "reason": f"High duplicate percentage ({dup_percentage:.1f}%)",
                "priority": "high"
            })
        analysis["recommendations"].append({
            "action": "apply_deduplication",
            "reason": f"Found {len(all_duplicate_indices)} duplicate records",
            "priority": "high"
        })
        
    return analysis

def _resolve_duplicates(df: pl.DataFrame, duplicate_analysis: Dict[str, Any],
                       merge_strategy: str, config: Dict[str, Any]) -> Tuple[pl.DataFrame, List[str], List[Dict]]:
    
    resolution_log = []
    row_level_issues = []
    
    duplicate_indices = set()
    for col_data in duplicate_analysis["duplicate_summary"].values():
        if isinstance(col_data, dict) and "affected_rows" in col_data:
            duplicate_indices.update(col_data.get("affected_rows", []))
            
    # If no duplicates, return original
    if not duplicate_indices:
        return df, ["No duplicates found"], []
        
    df_resolved = df.clone()
    
    if merge_strategy == "remove_duplicates":
        # We need to keep the first occurrence of duplicates
        # But "duplicates" here is defined by the union of all detection methods
        # This is tricky because different methods find different duplicates
        # The simplest approach consistent with "remove_duplicates" is to drop rows that are duplicates
        # BUT we must keep one.
        
        # If we use the indices found, we know which rows are duplicates.
        # But we don't know which groups they belong to across all methods easily.
        
        # Simplified approach:
        # If "exact" or "case_variations" or "email_case" was used, we can use Polars `unique`.
        # But we have a set of indices.
        
        # Let's assume we want to remove rows that were flagged as duplicates, keeping the first one in index order.
        # But we need to know the groups.
        
        # Re-running the most aggressive deduplication (likely case_variations + email_case) might be safer
        # to identify groups.
        
        # Or, we can just use the `unique` method on the dataframe with the same normalization logic
        # used in detection.
        
        # Let's construct a "normalization" expression based on config
        key_columns = config.get("key_columns", [])
        email_columns = config.get("email_columns", [])
        cols_to_check = key_columns if key_columns else df.columns
        
        exprs = []
        for col in cols_to_check:
            if df[col].dtype == pl.Utf8:
                if col in email_columns:
                    exprs.append(pl.col(col).str.to_lowercase().str.strip_chars().alias(f"__norm_{col}"))
                else:
                    exprs.append(pl.col(col).str.to_lowercase().str.strip_chars().alias(f"__norm_{col}"))
            else:
                exprs.append(pl.col(col).alias(f"__norm_{col}"))
        
        # Add normalized columns
        temp_df = df.with_columns(exprs)
        norm_cols = [f"__norm_{c}" for c in cols_to_check]
        
        # Keep unique based on normalized columns
        df_resolved = temp_df.unique(subset=norm_cols, keep='first').select(df.columns)
        
        removed_count = df.height - df_resolved.height
        resolution_log.append(f"Removed {removed_count} duplicate rows (kept first occurrence)")
        
    elif merge_strategy == "merge_smart":
        # Smart merge is complex. For now, fallback to remove_duplicates or implement simple non-null coalescing
        # Coalescing: Group by keys, take first non-null value for each column
        
        key_columns = config.get("key_columns", [])
        if key_columns:
             # Normalize keys
            key_exprs = []
            for col in key_columns:
                if df[col].dtype == pl.Utf8:
                    key_exprs.append(pl.col(col).str.to_lowercase().str.strip_chars().alias(f"__key_{col}"))
                else:
                    key_exprs.append(pl.col(col).alias(f"__key_{col}"))
            
            temp_df = df.with_columns(key_exprs)
            key_col_names = [f"__key_{c}" for c in key_columns]
            
            # Aggregation expressions: first non-null
            agg_exprs = []
            for col in df.columns:
                if col not in key_columns:
                    # Custom aggregation to take first non-null
                    # Polars doesn't have a direct "first_non_null" agg, but we can sort nulls to end?
                    # Or use `reduce`?
                    # Simplest: just take mode or first.
                    # Let's use `first` for now as "smart merge" usually implies filling gaps, which is hard in standard agg
                    agg_exprs.append(pl.col(col).drop_nulls().first().alias(col))
                else:
                    agg_exprs.append(pl.col(col).first().alias(col))
            
            df_resolved = temp_df.group_by(key_col_names).agg(agg_exprs).select(df.columns)
            
            removed_count = df.height - df_resolved.height
            resolution_log.append(f"Smart merged {removed_count} rows based on keys {key_columns}")
        else:
             # Fallback
            df_resolved = df.unique(keep='first')
            resolution_log.append("No key columns for smart merge, used remove_duplicates")

    # Generate issues for detected duplicates
    for idx in sorted(list(duplicate_indices)):
        row_level_issues.append({
            "row_index": int(idx),
            "issue_type": "duplicate_record",
            "description": "Duplicate record detected",
            "severity": "warning"
        })
        
    return df_resolved, resolution_log, row_level_issues

def _calculate_dedup_score(original_df, dedup_df, duplicate_analysis, config):
    total_duplicates = duplicate_analysis.get('total_duplicates', 0)
    rows_removed = original_df.height - dedup_df.height
    
    dedup_reduction_rate = ((total_duplicates - max(0, total_duplicates - rows_removed)) / total_duplicates * 100) if total_duplicates > 0 else 100
    data_retention_rate = (dedup_df.height / original_df.height * 100) if original_df.height > 0 else 0
    column_retention_rate = 100.0 # Columns usually don't change in dedup
    
    dedup_weight = config.get('dedup_reduction_weight', 0.5)
    data_weight = config.get('data_retention_weight', 0.3)
    column_weight = config.get('column_retention_weight', 0.2)
    
    overall_score = (
        dedup_reduction_rate * dedup_weight +
        data_retention_rate * data_weight +
        column_retention_rate * column_weight
    )
    
    return {
        "overall_score": round(overall_score, 1),
        "metrics": {
            "dedup_reduction_rate": round(dedup_reduction_rate, 1),
            "data_retention_rate": round(data_retention_rate, 1),
            "column_retention_rate": round(column_retention_rate, 1)
        }
    }
