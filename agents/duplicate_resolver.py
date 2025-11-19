"""
Duplicate Resolver Agent

Detects and merges/removes duplicate records with comprehensive duplicate detection strategies.
Handles exact duplicates, case variations, whitespace differences, email case-insensitivity,
missing values, and conflicting duplicates.
Input: CSV/JSON/XLSX file (primary)
Output: Standardized duplicate resolution results with deduplication effectiveness scores
"""

import pandas as pd
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
    email_columns = parameters.get("email_columns", [])  # Column names that contain emails
    key_columns = parameters.get("key_columns", [])  # Columns to consider for deduplication
    null_handling = parameters.get("null_handling", "ignore_nulls")  # ignore_nulls or match_nulls
    conflict_resolution = parameters.get("conflict_resolution", "keep_first")  # keep_first, keep_last, merge_smart
    dedup_reduction_weight = parameters.get("dedup_reduction_weight", 0.5)
    data_retention_weight = parameters.get("data_retention_weight", 0.3)
    column_retention_weight = parameters.get("column_retention_weight", 0.2)
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file based on format
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_contents), on_bad_lines='skip')
        elif filename.endswith('.json'):
            df = pd.read_json(io.BytesIO(file_contents))
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(file_contents))
        else:
            return {
                "status": "error",
                "agent_id": "duplicate-resolver",
                "error": f"Unsupported file format: {filename}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.empty:
            return {
                "status": "error",
                "agent_id": "duplicate-resolver",
                "agent_name": "Duplicate Resolver",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Store original data for comparison
        original_df = df.copy()
        
        # Auto-detect email columns if not provided
        if not email_columns:
            email_columns = _auto_detect_email_columns(df)
        
        # Analyze duplicates with specified detection types
        duplicate_analysis = _analyze_duplicates(df, detection_types, {
            "email_columns": email_columns,
            "key_columns": key_columns,
            "null_handling": null_handling
        })
        
        # Resolve duplicates based on strategy
        df_deduplicated, resolution_log, duplicate_issues = _resolve_duplicates(
            df, duplicate_analysis, merge_strategy, {
                "email_columns": email_columns,
                "key_columns": key_columns,
                "null_handling": null_handling,
                "conflict_resolution": conflict_resolution
            }
        )
        
        # Calculate deduplication effectiveness
        total_duplicates = sum(col_data["duplicate_count"] for col_data in duplicate_analysis["duplicate_summary"].values() if isinstance(col_data, dict))
        dedup_score = _calculate_dedup_score(original_df, df_deduplicated, duplicate_analysis, {
            "dedup_reduction_weight": dedup_reduction_weight,
            "data_retention_weight": data_retention_weight,
            "column_retention_weight": column_retention_weight,
            "excellent_threshold": excellent_threshold,
            "good_threshold": good_threshold
        })
        
        # Determine quality status
        if dedup_score["overall_score"] >= excellent_threshold:
            quality_status = "excellent"
        elif dedup_score["overall_score"] >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"
        
        # Build results
        dedup_data = {
            "dedup_score": dedup_score,
            "quality_status": quality_status,
            "duplicate_analysis": duplicate_analysis,
            "resolution_log": resolution_log,
            "summary": f"Duplicate resolution completed. Quality: {quality_status}. Processed {len(original_df)} rows, resolved {duplicate_analysis.get('total_duplicates', 0)} duplicate records.",
            "row_level_issues": duplicate_issues[:100]  # Limit to first 100
        }
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        total_dups = duplicate_analysis.get('total_duplicates', 0)
        executive_summary = [{
            "summary_id": "exec_duplicate_resolution",
            "title": "Duplicate Resolution Status",
            "value": f"{dedup_score['overall_score']:.1f}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"Quality: {quality_status}, Duplicates Resolved: {total_dups}, {len(original_df) - len(df_deduplicated)} rows removed, {dedup_score['metrics']['dedup_effectiveness_percentage']:.1f}% effectiveness"
        }]
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_parts = []
        ai_analysis_parts.append(f"DUPLICATE RESOLVER ANALYSIS:")
        ai_analysis_parts.append(f"- Deduplication Score: {dedup_score['overall_score']:.1f}/100 (Effectiveness: {dedup_score['metrics']['dedup_effectiveness_score']:.1f}, Data Integrity: {dedup_score['metrics']['data_integrity_score']:.1f}, Detection Accuracy: {dedup_score['metrics']['detection_accuracy_score']:.1f})")
        ai_analysis_parts.append(f"- Duplicates Resolved: {total_dups} duplicate records detected, {len(original_df) - len(df_deduplicated)} rows removed, {dedup_score['metrics']['dedup_effectiveness_percentage']:.1f}% effectiveness")
        
        dup_methods = duplicate_analysis.get('duplicate_summary', {})
        ai_analysis_parts.append(f"- Detection Methods: {len(dup_methods)} methods used - {', '.join(dup_methods.keys())}")
        ai_analysis_parts.append(f"- Data Retention: {len(df_deduplicated)} rows retained ({(len(df_deduplicated) / len(original_df) * 100):.1f}% of original)")
        ai_analysis_parts.append(f"- Resolution Strategy: {resolution_log[0].get('strategy', 'unknown') if len(resolution_log) > 0 else 'N/A'}")
        
        if len(duplicate_analysis.get('recommendations', [])) > 0:
            ai_analysis_parts.append(f"- Top Recommendation: {duplicate_analysis['recommendations'][0].get('recommendation', 'Review duplicate resolution strategy')}")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # Add to dedup_data
        dedup_data["executive_summary"] = executive_summary
        dedup_data["ai_analysis_text"] = ai_analysis_text
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # High duplicate volume alert
        duplicate_pct = (total_dups / len(original_df) * 100) if len(original_df) > 0 else 0
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
        
        # Data loss from deduplication
        rows_removed = len(original_df) - len(df_deduplicated)
        if rows_removed > len(original_df) * 0.2:
            alerts.append({
                "alert_id": "alert_duplicates_data_loss",
                "severity": "high",
                "category": "data_retention",
                "message": f"Significant data loss: {rows_removed} rows removed ({(rows_removed/len(original_df)*100):.1f}% of dataset)",
                "affected_fields_count": rows_removed,
                "recommendation": "Review deduplication strategy. Consider merge strategies instead of removal to preserve information."
            })
        
        # Conflicting duplicates alert
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
        
        # Quality score alert
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
        
        # Detection method effectiveness alert
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
        
        # Key column validation alert
        if not key_columns and duplicate_pct > 5:
            alerts.append({
                "alert_id": "alert_duplicates_no_key_columns",
                "severity": "medium",
                "category": "configuration",
                "message": "No key columns specified for duplicate detection. Using all columns may miss partial duplicates.",
                "affected_fields_count": len(df.columns),
                "recommendation": "Define key columns (e.g., ID, email) for more precise duplicate detection."
            })
        
        # Multiple detection types triggered
        significant_methods = {k: v for k, v in dup_methods.items() if isinstance(v, dict) and v.get('duplicate_count', 0) > len(original_df) * 0.05}
        if len(significant_methods) >= 3:
            alerts.append({
                "alert_id": "alert_duplicates_multiple_types",
                "severity": "high",
                "category": "data_quality",
                "message": f"{len(significant_methods)} different duplicate types detected ({', '.join(significant_methods.keys())}). Systematic data quality issues likely.",
                "affected_fields_count": len(significant_methods),
                "recommendation": "Review data entry, import, and validation processes comprehensively."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Convert duplicate issues to standardized format (row-level duplicates)
        for dup_issue in duplicate_issues[:100]:
            issues.append({
                "issue_id": f"issue_duplicates_{dup_issue.get('row_index', 0)}_duplicate",
                "agent_id": "duplicate-resolver",
                "field_name": "record",
                "issue_type": dup_issue.get('issue_type', 'duplicate_record'),
                "severity": dup_issue.get('severity', 'warning'),
                "message": dup_issue.get('description', 'Duplicate record detected')
            })
        
        # Add detection method-specific issues
        for method, data in dup_methods.items():
            if isinstance(data, dict) and data.get('duplicate_count', 0) > 0:
                issues.append({
                    "issue_id": f"issue_duplicates_method_{method}",
                    "agent_id": "duplicate-resolver",
                    "field_name": "multiple",
                    "issue_type": f"duplicate_{method}",
                    "severity": "high" if data.get('duplicate_count', 0) > len(original_df) * 0.1 else "medium",
                    "message": f"{data.get('duplicate_count', 0)} duplicate(s) detected using {method} method: {data.get('description', '')}"
                })
        
        # Add conflicting duplicate issues
        if conflicting_dups > 0:
            issues.append({
                "issue_id": "issue_duplicates_conflicts",
                "agent_id": "duplicate-resolver",
                "field_name": "multiple",
                "issue_type": "conflicting_duplicates",
                "severity": "critical",
                "message": f"{conflicting_dups} conflicting duplicate(s) found - same keys but different values requiring manual resolution"
            })
        
        # Add data loss issue if significant removal
        if rows_removed > len(original_df) * 0.2:
            issues.append({
                "issue_id": "issue_duplicates_data_loss",
                "agent_id": "duplicate-resolver",
                "field_name": "dataset",
                "issue_type": "data_retention",
                "severity": "high",
                "message": f"Significant data loss: {rows_removed} rows ({(rows_removed/len(original_df)*100):.1f}%) removed during deduplication"
            })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        agent_recommendations = []
        
        # Recommendation 1: Address conflicting duplicates
        if conflicting_dups > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_duplicates_conflicts",
                "agent_id": "duplicate-resolver",
                "field_name": "multiple",
                "priority": "critical",
                "recommendation": f"Manually review and resolve {conflicting_dups} conflicting duplicate(s) with different values for same keys",
                "timeline": "immediate"
            })
        
        # Recommendation 2: Unique constraints
        if total_dups > len(original_df) * 0.1:
            agent_recommendations.append({
                "recommendation_id": "rec_duplicates_constraints",
                "agent_id": "duplicate-resolver",
                "field_name": "all",
                "priority": "high",
                "recommendation": "Implement unique key constraints at database level to prevent duplicate entry",
                "timeline": "1 week"
            })
        
        # Recommendation 3: Detection method optimization
        for method, data in dup_methods.items():
            if data.get('duplicate_count', 0) > 0:
                agent_recommendations.append({
                    "recommendation_id": f"rec_duplicates_{method}",
                    "agent_id": "duplicate-resolver",
                    "field_name": "various",
                    "priority": "high" if data.get('duplicate_count', 0) > len(original_df) * 0.05 else "medium",
                    "recommendation": f"Address {data.get('duplicate_count', 0)} {method} duplicate(s) with targeted resolution strategy",
                    "timeline": "1-2 weeks"
                })
                if len(agent_recommendations) >= 5:
                    break
        
        # Recommendation 4: Merge strategy
        if merge_strategy == 'remove_duplicates' and rows_removed > len(original_df) * 0.1:
            agent_recommendations.append({
                "recommendation_id": "rec_duplicates_merge_strategy",
                "agent_id": "duplicate-resolver",
                "field_name": "all",
                "priority": "medium",
                "recommendation": "Consider smart merge strategy instead of removal to preserve valuable information from duplicate records",
                "timeline": "2 weeks"
            })
        
        # Recommendation 5: Data source improvement
        agent_recommendations.append({
            "recommendation_id": "rec_duplicates_source",
            "agent_id": "duplicate-resolver",
            "field_name": "all",
            "priority": "medium",
            "recommendation": "Review data entry and import processes to prevent duplicate creation at source",
            "timeline": "2 weeks"
        })
        
        # Recommendation 6: Monitoring
        agent_recommendations.append({
            "recommendation_id": "rec_duplicates_monitoring",
            "agent_id": "duplicate-resolver",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Establish duplicate rate monitoring and alerting to detect data quality degradation",
            "timeline": "3 weeks"
        })
        
        # Recommendation 7: Key column identification
        if not key_columns:
            agent_recommendations.append({
                "recommendation_id": "rec_duplicates_key_columns",
                "agent_id": "duplicate-resolver",
                "field_name": "all",
                "priority": "high",
                "recommendation": "Define key columns for duplicate detection to improve precision and avoid false positives",
                "timeline": "1 week"
            })
        
        # Recommendation 8: Email normalization
        if len(email_columns) > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_duplicates_email_normalization",
                "agent_id": "duplicate-resolver",
                "field_name": ", ".join(email_columns[:3]),
                "priority": "medium",
                "recommendation": f"Implement email normalization rules for {len(email_columns)} email column(s) to prevent case/format duplicates",
                "timeline": "2 weeks"
            })
        
        # Recommendation 9: Documentation
        agent_recommendations.append({
            "recommendation_id": "rec_duplicates_documentation",
            "agent_id": "duplicate-resolver",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Document duplicate resolution decisions, mer ge strategies, and business rules for handling conflicting data",
            "timeline": "3 weeks"
        })
        
        # Recommendation 10: Automated deduplication
        if duplicate_pct > 10:
            agent_recommendations.append({
                "recommendation_id": "rec_duplicates_automation",
                "agent_id": "duplicate-resolver",
                "field_name": "all",
                "priority": "high",
                "recommendation": f"{duplicate_pct:.1f}% duplicate rate warrants automated deduplication pipeline with periodic manual review",
                "timeline": "2-3 weeks"
            })

        # Generate cleaned file (CSV format)
        cleaned_file_bytes = _generate_cleaned_file(df_deduplicated, filename)
        cleaned_file_base64 = base64.b64encode(cleaned_file_bytes).decode('utf-8')

        return {
            "status": "success",
            "agent_id": "duplicate-resolver",
            "agent_name": "Duplicate Resolver",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_processed": len(original_df),
                "duplicates_detected": duplicate_analysis.get('total_duplicates', 0),
                "duplicates_resolved": len(df_deduplicated) - len(df_deduplicated.drop_duplicates()),
                "remaining_rows": len(df_deduplicated),
                "rows_removed": len(original_df) - len(df_deduplicated),
                "total_issues": len(duplicate_issues)
            },
            "data": dedup_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
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


def _auto_detect_email_columns(df: pd.DataFrame) -> List[str]:
    """Auto-detect columns that likely contain email addresses."""
    email_columns = []
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    for col in df.columns:
        # Check column name
        if 'email' in str(col).lower() or 'mail' in str(col).lower():
            email_columns.append(str(col))
            continue
        
        # Check sample values
        if df[col].dtype == 'object':
            sample = df[col].dropna().head(20)
            email_count = sum(1 for val in sample if email_pattern.match(str(val)))
            if len(sample) > 0 and email_count / len(sample) > 0.5:
                email_columns.append(str(col))
    
    return email_columns


def _normalize_string(value: str, preserve_case: bool = False) -> str:
    """Normalize string for comparison."""
    if pd.isna(value):
        return ""
    
    value = str(value).strip()
    if not preserve_case:
        value = value.lower()
    
    # Normalize whitespace
    value = re.sub(r'\s+', ' ', value)
    
    return value


def _normalize_email(value: str) -> str:
    """Normalize email address (case-insensitive)."""
    if pd.isna(value):
        return ""
    
    value = str(value).strip().lower()
    # Basic email normalization
    value = re.sub(r'\s+', '', value)
    return value


def _is_email_column(col_name: str, email_columns: List[str]) -> bool:
    """Check if column is marked as email column."""
    return str(col_name) in email_columns


def _create_duplicate_key(row: pd.Series, email_columns: List[str], key_columns: List[str], 
                          normalize_method: str = "exact", null_handling: str = "ignore_nulls") -> str:
    """Create a key for duplicate detection."""
    key_parts = []
    
    # Use specific key columns if provided
    if key_columns:
        cols_to_use = [col for col in key_columns if col in row.index]
    else:
        cols_to_use = list(row.index)
    
    for col in cols_to_use:
        value = row[col]
        
        # Handle nulls
        if pd.isna(value):
            if null_handling == "ignore_nulls":
                key_parts.append("__NULL__")
            else:
                key_parts.append("")
        else:
            # Apply normalization based on detection type
            if normalize_method == "exact":
                key_parts.append(str(value))
            elif normalize_method == "case_variations":
                key_parts.append(_normalize_string(str(value), preserve_case=False))
            elif normalize_method == "email_case" and _is_email_column(col, email_columns):
                key_parts.append(_normalize_email(str(value)))
            else:
                key_parts.append(_normalize_string(str(value), preserve_case=False))
    
    return "|".join(str(p) for p in key_parts)


def _analyze_duplicates(df: pd.DataFrame, detection_types: List[str], config: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze duplicates using specified detection methods."""
    email_columns = config.get("email_columns", [])
    key_columns = config.get("key_columns", [])
    null_handling = config.get("null_handling", "ignore_nulls")
    
    analysis = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "duplicate_summary": {},
        "duplicate_sets": {},
        "total_duplicates": 0,
        "detection_methods": detection_types,
        "recommendations": []
    }
    
    # Detect duplicates using each specified method
    all_duplicate_indices: Set[int] = set()
    
    for detection_type in detection_types:
        duplicate_groups = {}
        
        if detection_type == "exact":
            # Exact duplicates - exact match across all columns
            duplicate_mask = df.duplicated(keep=False)
            duplicate_indices = set(df[duplicate_mask].index)
        
        elif detection_type == "case_variations":
            # Case variations - ignore case and extra whitespace
            duplicate_indices = _find_duplicates_by_key(df, email_columns, key_columns, 
                                                       normalize_method="case_variations", 
                                                       null_handling=null_handling)
        
        elif detection_type == "email_case":
            # Email case-insensitivity - treat emails as case-insensitive
            duplicate_indices = _find_duplicates_by_key(df, email_columns, key_columns,
                                                       normalize_method="email_case",
                                                       null_handling=null_handling)
        
        elif detection_type == "missing_values":
            # Missing values handling - rows that differ only in null placement
            duplicate_indices = _find_duplicates_missing_values(df, email_columns, 
                                                               key_columns, null_handling)
        
        elif detection_type == "conflicting":
            # Conflicting duplicates - same key but different values in some columns
            duplicate_indices = _find_conflicting_duplicates(df, email_columns, key_columns,
                                                            null_handling=null_handling)
        
        else:
            duplicate_indices = set()
        
        all_duplicate_indices.update(duplicate_indices)
        
        analysis["duplicate_summary"][detection_type] = {
            "method": detection_type,
            "duplicate_count": len(duplicate_indices),
            "duplicate_percentage": round((len(duplicate_indices) / len(df) * 100) if len(df) > 0 else 0, 2),
            "description": _get_detection_description(detection_type),
            "affected_rows": sorted(list(duplicate_indices))[:50]  # Limit for performance
        }
    
    analysis["total_duplicates"] = len(all_duplicate_indices)
    
    # Generate recommendations
    if len(all_duplicate_indices) > 0:
        dup_percentage = (len(all_duplicate_indices) / len(df) * 100) if len(df) > 0 else 0
        
        if dup_percentage > 50:
            analysis["recommendations"].append({
                "action": "investigate_data_source",
                "reason": f"High duplicate percentage ({dup_percentage:.1f}%) - investigate data collection process",
                "priority": "high"
            })
        
        analysis["recommendations"].append({
            "action": "apply_deduplication",
            "reason": f"Found {len(all_duplicate_indices)} duplicate records across {len(detection_types)} detection methods",
            "priority": "high"
        })
    
    return analysis


def _get_detection_description(detection_type: str) -> str:
    """Get human-readable description of detection type."""
    descriptions = {
        "exact": "Exact duplicates - identical values in all columns",
        "case_variations": "Case and whitespace variations - same data, different casing or spacing",
        "email_case": "Email case-insensitivity - same records with different email cases",
        "missing_values": "Missing value duplicates - identical except for null placement",
        "conflicting": "Conflicting duplicates - same key but different values"
    }
    return descriptions.get(detection_type, detection_type)


def _find_duplicates_by_key(df: pd.DataFrame, email_columns: List[str], key_columns: List[str],
                           normalize_method: str = "case_variations",
                           null_handling: str = "ignore_nulls") -> Set[int]:
    """Find duplicates by creating normalized keys."""
    seen_keys = {}
    duplicate_indices = set()
    
    for idx, row in df.iterrows():
        key = _create_duplicate_key(row, email_columns, key_columns, normalize_method, null_handling)
        
        if key in seen_keys:
            duplicate_indices.add(idx)
            duplicate_indices.add(seen_keys[key])
        else:
            seen_keys[key] = idx
    
    return duplicate_indices


def _find_duplicates_missing_values(df: pd.DataFrame, email_columns: List[str],
                                   key_columns: List[str], null_handling: str) -> Set[int]:
    """Find duplicates that differ only in null placement."""
    duplicate_indices = set()
    
    # For each pair of rows, check if they're identical except for nulls
    for i in range(len(df)):
        for j in range(i + 1, len(df)):
            row_i = df.iloc[i]
            row_j = df.iloc[j]
            
            # Check if rows are identical except for nulls
            non_null_match = True
            for col in df.columns:
                val_i = row_i[col]
                val_j = row_j[col]
                
                # If both are non-null, they must match
                if pd.notnull(val_i) and pd.notnull(val_j):
                    norm_i = _normalize_string(str(val_i), preserve_case=False)
                    norm_j = _normalize_string(str(val_j), preserve_case=False)
                    if norm_i != norm_j:
                        non_null_match = False
                        break
            
            if non_null_match:
                duplicate_indices.add(i)
                duplicate_indices.add(j)
    
    return duplicate_indices


def _find_conflicting_duplicates(df: pd.DataFrame, email_columns: List[str],
                                key_columns: List[str], null_handling: str) -> Set[int]:
    """Find duplicates with same key but conflicting values."""
    if not key_columns:
        return set()
    
    duplicate_indices = set()
    key_groups = {}
    
    for idx, row in df.iterrows():
        # Create key from key_columns only
        key_parts = []
        for col in key_columns:
            if col in row.index:
                value = row[col]
                if pd.isna(value):
                    key_parts.append("__NULL__")
                else:
                    if _is_email_column(col, email_columns):
                        key_parts.append(_normalize_email(str(value)))
                    else:
                        key_parts.append(_normalize_string(str(value), preserve_case=False))
        
        key = "|".join(str(p) for p in key_parts)
        
        if key not in key_groups:
            key_groups[key] = []
        key_groups[key].append((idx, row))
    
    # Find groups with conflicting values
    for key, group in key_groups.items():
        if len(group) > 1:
            # Check if non-key columns have conflicts
            non_key_cols = [col for col in df.columns if col not in key_columns]
            
            for col in non_key_cols:
                values = [row[col] for _, row in group]
                non_null_values = [v for v in values if pd.notnull(v)]
                
                if len(non_null_values) > 1:
                    # Check if they differ
                    normalized = [_normalize_string(str(v), preserve_case=False) for v in non_null_values]
                    if len(set(normalized)) > 1:
                        # Conflicting values found
                        for idx, _ in group:
                            duplicate_indices.add(idx)
                        break
    
    return duplicate_indices


def _resolve_duplicates(df: pd.DataFrame, duplicate_analysis: Dict[str, Any],
                       merge_strategy: str, config: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str], List[Dict]]:
    """Resolve duplicates based on strategy."""
    df_resolved = df.copy()
    resolution_log = []
    row_level_issues = []
    
    duplicate_indices = set()
    for col_data in duplicate_analysis["duplicate_summary"].values():
        if isinstance(col_data, dict) and "affected_rows" in col_data:
            duplicate_indices.update(col_data.get("affected_rows", []))
    
    email_columns = config.get("email_columns", [])
    key_columns = config.get("key_columns", [])
    conflict_resolution = config.get("conflict_resolution", "keep_first")
    
    if merge_strategy == "remove_duplicates":
        # Remove all duplicates except first occurrence
        original_count = len(df_resolved)
        df_resolved = df_resolved.drop_duplicates(keep='first')
        removed_count = original_count - len(df_resolved)
        resolution_log.append(f"Removed {removed_count} duplicate rows (kept first occurrence)")
    
    elif merge_strategy == "merge_smart":
        # Merge duplicate rows intelligently
        if key_columns:
            df_resolved = _merge_by_key(df_resolved, key_columns, duplicate_indices, 
                                       conflict_resolution, resolution_log)
        else:
            df_resolved = df_resolved.drop_duplicates(keep='first')
            resolution_log.append("No key columns specified for smart merge, using remove_duplicates")
    
    # Create row-level issues for duplicates
    for idx in sorted(duplicate_indices):
        if idx < len(df):
            row_level_issues.append({
                "row_index": int(idx),
                "issue_type": "duplicate_record",
                "description": "Duplicate record detected and marked for resolution",
                "severity": "warning"
            })
    
    return df_resolved, resolution_log, row_level_issues


def _merge_by_key(df: pd.DataFrame, key_columns: List[str], duplicate_indices: Set[int],
                 conflict_resolution: str, log: List[str]) -> pd.DataFrame:
    """Merge duplicate rows by key columns."""
    df_result = df.copy()
    merged_rows = set()
    
    # Group by key
    key_groups = {}
    for idx, row in df_result.iterrows():
        key_parts = []
        for col in key_columns:
            if col in row.index:
                value = row[col]
                key_parts.append(str(value) if pd.notnull(value) else "__NULL__")
        
        key = "|".join(key_parts)
        if key not in key_groups:
            key_groups[key] = []
        key_groups[key].append(idx)
    
    # Merge groups with duplicates
    for key, indices in key_groups.items():
        if len(indices) > 1:
            # Found duplicates
            if conflict_resolution == "keep_first":
                keep_idx = indices[0]
                drop_indices = indices[1:]
            elif conflict_resolution == "keep_last":
                keep_idx = indices[-1]
                drop_indices = indices[:-1]
            else:  # merge_smart
                keep_idx = indices[0]
                drop_indices = indices[1:]
            
            # Drop duplicate rows
            for idx in drop_indices:
                if idx in df_result.index:
                    df_result = df_result.drop(idx)
                    merged_rows.add(idx)
            
            log.append(f"Merged {len(drop_indices)} rows for key '{key[:50]}...' (kept row {keep_idx})")
    
    return df_result


def _calculate_dedup_score(
    original_df: pd.DataFrame,
    dedup_df: pd.DataFrame,
    duplicate_analysis: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate deduplication effectiveness score."""
    total_duplicates = duplicate_analysis.get('total_duplicates', 0)
    rows_removed = len(original_df) - len(dedup_df)
    
    # Calculate metrics
    dedup_reduction_rate = ((total_duplicates - max(0, total_duplicates - rows_removed)) / total_duplicates * 100) if total_duplicates > 0 else 100
    data_retention_rate = (len(dedup_df) / len(original_df) * 100) if len(original_df) > 0 else 0
    column_retention_rate = (len(dedup_df.columns) / len(original_df.columns) * 100) if len(original_df.columns) > 0 else 0
    
    # Calculate weighted score
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
            "column_retention_rate": round(column_retention_rate, 1),
            "original_duplicates": total_duplicates,
            "duplicates_resolved": rows_removed,
            "original_rows": len(original_df),
            "deduplicated_rows": len(dedup_df),
            "original_columns": len(original_df.columns),
            "deduplicated_columns": len(dedup_df.columns),
            "duplicate_percentage_before": round((total_duplicates / len(original_df) * 100) if len(original_df) > 0 else 0, 2),
            "duplicate_percentage_after": round((max(0, total_duplicates - rows_removed) / len(dedup_df) * 100) if len(dedup_df) > 0 else 0, 2)
        }
    }


def _convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        val = float(obj)
        if np.isnan(val):
            return None
        elif np.isinf(val):
            return str(val)
        return val
    elif isinstance(obj, (float, int)) and not isinstance(obj, bool):
        if isinstance(obj, float):
            if np.isnan(obj):
                return None
            elif np.isinf(obj):
                return str(obj)
        return obj
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: _convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy_types(item) for item in obj]
    else:
        return obj


def _generate_cleaned_file(df: pd.DataFrame, original_filename: str) -> bytes:
    """
    Generate cleaned data file in CSV format.
    
    Args:
        df: Cleaned dataframe
        original_filename: Original filename to determine format
        
    Returns:
        File contents as bytes
    """
    # Always export as CSV for consistency and compatibility
    output = io.BytesIO()
    df.to_csv(output, index=False)
    return output.getvalue()
