"""
Golden Record Builder Agent

Creates the final unified, conflict-resolved, highest-quality version of a record—
also known as the Golden Record. Merges all incoming data representations from
multiple sources, systems, or formats into one authoritative, cleansed, standardized,
and trust-scored record.

Key Responsibilities:
1. Merge records from multiple sources
2. Apply survivorship rules (completeness, recency, source priority)
3. Resolve field conflicts
4. Generate trust scores for each field
5. Create the final authoritative record

Input: CSV file (primary) with potential duplicates/related records
Output: Golden records with trust scores, source attributions, and conflict resolutions
"""

import io
import re
import time
import base64
import hashlib
import polars as pl
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from collections import defaultdict
from agents.agent_utils import safe_get_list, safe_get_dict

try:
    import rapidfuzz
    from rapidfuzz import fuzz, distance
    import jellyfish
except ImportError:
    rapidfuzz = None
    jellyfish = None


def execute_golden_record_builder(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build golden records from potentially duplicate/related records.

    Args:
        file_contents: File bytes (read as binary)
        filename: Original filename (used to detect format)
        parameters: Agent parameters including survivorship rules and match keys

    Returns:
        Standardized output dictionary with golden record results
    """

    start_time = time.time()
    parameters = parameters or {}
    
    # Extract and parse parameters with defaults
    match_key_columns = safe_get_list(parameters, "match_key_columns", [])
    match_key_weights = safe_get_dict(parameters, "match_key_weights", {})
    survivorship_rules = safe_get_dict(parameters, "survivorship_rules", {})
    source_priority = safe_get_dict(parameters, "source_priority", {})
    source_column = parameters.get("source_column", None)
    timestamp_column = parameters.get("timestamp_column", None)
    default_survivorship_rule = parameters.get("default_survivorship_rule", "most_complete")
    min_trust_score = parameters.get("min_trust_score", 0.5)
    
    # Fuzzy matching parameters
    enable_fuzzy_matching = parameters.get("enable_fuzzy_matching", False)
    fuzzy_threshold = parameters.get("fuzzy_threshold", 80.0)
    
    # Scoring thresholds
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file - CSV only
        if not filename.endswith('.csv'):
            return {
                "status": "error",
                "agent_id": "golden-record-builder",
                "error": f"Unsupported file format: {filename}. Only CSV files are supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        try:
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000, truncate_ragged_lines=True)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": "golden-record-builder",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.height == 0:
            return {
                "status": "error",
                "agent_id": "golden-record-builder",
                "agent_name": "Golden Record Builder",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        original_df = df.clone()
        total_rows = df.height
        total_columns = len(df.columns)
        
        # Auto-detect match key columns if not provided
        if not match_key_columns:
            # If fuzzy matching is enabled but no match columns provided, auto-detect
            if enable_fuzzy_matching:
                match_key_columns = _auto_detect_match_keys_intelligent(df)
            else:
                match_key_columns = _auto_detect_match_keys(df)
        
        # Validate match key columns exist
        valid_match_keys = []
        df_columns_normalized = {col.strip().lower(): col for col in df.columns}
        
        for col in match_key_columns:
            col_clean = col.strip().lower()
            if col_clean in df_columns_normalized:
                actual_col = df_columns_normalized[col_clean]
                valid_match_keys.append(actual_col)
        
        if not valid_match_keys:
            # Fallback: treat each row as its own cluster
            valid_match_keys = []
        
        # ==================== CLUSTER RELATED RECORDS ====================
        if enable_fuzzy_matching and rapidfuzz and jellyfish:
               derived_fuzzy_config = _derive_fuzzy_config(
                  match_keys=valid_match_keys,
                  match_key_weights=match_key_weights,
                  all_columns=df.columns
               )
               # IMPORTANT: Do NOT use match keys as strict blocking keys.
               # Blocking by exact equality across multiple match keys disables fuzzy matching.
               clusters = _build_fuzzy_clusters(df, derived_fuzzy_config, fuzzy_threshold, blocking_keys=[])
        else:
             clusters = _build_record_clusters(df, valid_match_keys)
        
        # ==================== BUILD GOLDEN RECORDS ====================
        golden_records = []
        field_resolutions = []
        conflicts_resolved = 0
        values_survived = 0
        row_level_issues = []
        
        for idx, (cluster_id, cluster_info) in enumerate(clusters.items()):
            cluster_rows = cluster_info["rows"]
            cluster_df = df.filter(pl.col("__row_index__").is_in(cluster_rows)) if "__row_index__" in df.columns else df[cluster_rows]
            
            # Build golden record for this cluster
            golden_record, resolutions, cluster_conflicts = _build_single_golden_record(
                cluster_df=df[cluster_rows[0]:cluster_rows[-1]+1] if len(cluster_rows) == 1 else _get_cluster_df(df, cluster_rows),
                cluster_id=cluster_id,
                survivorship_rules=survivorship_rules,
                default_rule=default_survivorship_rule,
                source_column=source_column,
                source_priority=source_priority,
                timestamp_column=timestamp_column,
                df_full=df,
                cluster_rows=cluster_rows
            )
            
            golden_record_entry = {
                "cluster_id": cluster_id,
                "golden_record": golden_record,
                "source_record_count": len(cluster_rows),
                "source_row_indices": cluster_rows,
                "match_key_values": cluster_info.get("match_values", {}),
                "trust_score": golden_record.get("__trust_score__", 1.0),
                "conflicts_resolved": cluster_conflicts
            }
            
            # Add fuzzy details if present
            if "match_details" in cluster_info and cluster_info["match_details"]:
                 golden_record_entry["fuzzy_match_details"] = cluster_info["match_details"]
                 # Calculate average similarity for the cluster (excluding the first record which is the rep)
                 scores = [d["similarity_score"] for d in cluster_info["match_details"] if d["similarity_score"] >= 0]
                 if scores:
                     golden_record_entry["avg_similarity_score"] = sum(scores) / len(scores)

            golden_records.append(golden_record_entry)
            
            field_resolutions.extend(resolutions)
            conflicts_resolved += cluster_conflicts
            values_survived += len(golden_record) - 1  # Exclude trust score
            
            # Track issues for low trust scores
            if golden_record.get("__trust_score__", 1.0) < min_trust_score:
                row_level_issues.append({
                    "row_index": cluster_rows[0],
                    "column": "cluster",
                    "issue_type": "low_trust_score",
                    "severity": "warning",
                    "original_value": golden_record.get("__trust_score__", 0),
                    "message": f"Cluster {cluster_id} has low trust score ({golden_record.get('__trust_score__', 0):.2f})"
                })
        
        # Create golden records DataFrame
        golden_df = _create_golden_dataframe(golden_records, df.columns)
        
        # ==================== CALCULATE STATISTICS ====================
        golden_record_count = len(golden_records)
        compression_ratio = total_rows / golden_record_count if golden_record_count > 0 else 1.0
        avg_trust_score = sum(gr["trust_score"] for gr in golden_records) / len(golden_records) if golden_records else 0
        
        # Calculate quality score
        trust_score_component = avg_trust_score * 100 * 0.4
        compression_component = min(100, compression_ratio * 20) * 0.3  # Higher compression = better dedup
        conflict_resolution_rate = (conflicts_resolved / max(len(field_resolutions), 1)) * 100 if field_resolutions else 100
        conflict_component = conflict_resolution_rate * 0.3
        
        overall_score = trust_score_component + compression_component + conflict_component
        
        if overall_score >= excellent_threshold:
            quality_status = "excellent"
        elif overall_score >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"
        
        # Cap row-level issues
        row_level_issues = row_level_issues[:1000]
        
        # Calculate issue summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {},
            "affected_rows": len(set(issue["row_index"] for issue in row_level_issues)),
            "affected_columns": sorted(list(set(issue["column"] for issue in row_level_issues)))
        }
        
        for issue in row_level_issues:
            issue_type = issue.get("issue_type", "unknown")
            issue_summary["by_type"][issue_type] = issue_summary["by_type"].get(issue_type, 0) + 1
            severity = issue.get("severity", "info")
            issue_summary["by_severity"][severity] = issue_summary["by_severity"].get(severity, 0) + 1
        
        # ==================== BUILD GOLDEN RECORD DATA ====================
        golden_record_data = {
            "golden_score": round(overall_score, 1),
            "quality_status": quality_status,
            "golden_records": golden_records[:100],  # Limit for response size
            "field_resolutions": field_resolutions[:200],  # Limit
            "statistics": {
                "input_records": total_rows,
                "golden_records_created": golden_record_count,
                "clusters_formed": len(clusters),
                "compression_ratio": round(compression_ratio, 2),
                "conflicts_resolved": conflicts_resolved,
                "values_survived": values_survived,
                "average_trust_score": round(avg_trust_score, 3),
                "match_key_columns": valid_match_keys,
                "fuzzy_matching_enabled": enable_fuzzy_matching,
                "fuzzy_threshold": fuzzy_threshold if enable_fuzzy_matching else None
            },
            "survivorship_rules_applied": survivorship_rules or {"default": default_survivorship_rule},
            "summary": f"Golden record building completed. Created {golden_record_count} golden records "
                      f"from {total_rows} input records ({compression_ratio:.1f}x compression). "
                      f"{conflicts_resolved} conflicts resolved.",
            "row_level_issues": row_level_issues[:100],
            "issue_summary": issue_summary,
            "overrides": {
                "match_key_columns": match_key_columns,
                "match_key_weights": match_key_weights,
                "default_survivorship_rule": default_survivorship_rule,
                "source_column": source_column,
                "timestamp_column": timestamp_column,
                "min_trust_score": min_trust_score
            }
        }
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = [{
            "summary_id": "exec_golden_record_builder",
            "title": "Golden Record Status",
            "value": f"{overall_score:.1f}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"Created {golden_record_count} golden records from {total_rows} inputs, "
                          f"{compression_ratio:.1f}x compression, Avg Trust: {avg_trust_score:.2f}"
        }]
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_parts = []
        ai_analysis_parts.append(f"GOLDEN RECORD BUILDER ANALYSIS:")
        ai_analysis_parts.append(f"- Golden Score: {overall_score:.1f}/100 ({quality_status})")
        ai_analysis_parts.append(f"- Input Records: {total_rows}")
        ai_analysis_parts.append(f"- Golden Records Created: {golden_record_count}")
        ai_analysis_parts.append(f"- Compression Ratio: {compression_ratio:.1f}x")
        ai_analysis_parts.append(f"- Conflicts Resolved: {conflicts_resolved}")
        ai_analysis_parts.append(f"- Average Trust Score: {avg_trust_score:.2f}")
        
        if valid_match_keys:
            ai_analysis_parts.append(f"- Match Keys Used: {', '.join(valid_match_keys)}")
        else:
            ai_analysis_parts.append(f"- Match Keys: Auto-detected (each record unique)")
        
        low_trust_records = len([gr for gr in golden_records if gr["trust_score"] < min_trust_score])
        if low_trust_records > 0:
            ai_analysis_parts.append(f"- Low Trust Records: {low_trust_records} (below {min_trust_score})")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # Alert: Low compression ratio
        if compression_ratio < 1.5 and total_rows > 10:
            alerts.append({
                "alert_id": "alert_golden_low_compression",
                "severity": "info",
                "category": "deduplication",
                "message": f"Low compression ratio ({compression_ratio:.1f}x) - few duplicate records found",
                "affected_fields_count": 0,
                "recommendation": "Review match key columns or data may already be deduplicated."
            })
        
        # Alert: Many low trust records
        low_trust_count = len([gr for gr in golden_records if gr["trust_score"] < min_trust_score])
        if low_trust_count > len(golden_records) * 0.1:
            alerts.append({
                "alert_id": "alert_golden_low_trust",
                "severity": "high",
                "category": "data_quality",
                "message": f"{low_trust_count} golden records ({low_trust_count/len(golden_records)*100:.1f}%) have low trust scores",
                "affected_fields_count": low_trust_count,
                "recommendation": "Review survivorship rules and source data quality."
            })
        
        # Alert: Many conflicts
        if conflicts_resolved > total_rows * 0.5:
            alerts.append({
                "alert_id": "alert_golden_many_conflicts",
                "severity": "medium",
                "category": "conflict_resolution",
                "message": f"High number of conflicts resolved ({conflicts_resolved})",
                "affected_fields_count": conflicts_resolved,
                "recommendation": "Review source data consistency and survivorship rules."
            })
        
        # Alert: No match keys specified
        if not match_key_columns:
            alerts.append({
                "alert_id": "alert_golden_no_match_keys",
                "severity": "medium",
                "category": "configuration",
                "message": "No match key columns specified - auto-detection used",
                "affected_fields_count": 0,
                "recommendation": "Specify match_key_columns for better record clustering."
            })
        
        # Alert: Quality score
        if overall_score < good_threshold:
            alerts.append({
                "alert_id": "alert_golden_quality",
                "severity": "high",
                "category": "overall_quality",
                "message": f"Golden record quality score ({overall_score:.1f}%) is below threshold",
                "affected_fields_count": golden_record_count,
                "recommendation": "Review survivorship rules and data quality issues."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        for gr in golden_records:
            if gr["trust_score"] < min_trust_score:
                issues.append({
                    "issue_id": f"issue_golden_trust_{gr['cluster_id']}",
                    "agent_id": "golden-record-builder",
                    "field_name": f"cluster_{gr['cluster_id']}",
                    "issue_type": "low_trust_score",
                    "severity": "warning",
                    "message": f"Golden record for cluster {gr['cluster_id']} has low trust score ({gr['trust_score']:.2f})"
                })
        
        # Issues for unresolved conflicts (if any)
        unresolved = [r for r in field_resolutions if r.get("resolution_method") == "unresolved"]
        for res in unresolved[:10]:
            issues.append({
                "issue_id": f"issue_golden_unresolved_{res['cluster_id']}_{res['column']}",
                "agent_id": "golden-record-builder",
                "field_name": res["column"],
                "issue_type": "unresolved_conflict",
                "severity": "high",
                "message": f"Conflict in '{res['column']}' for cluster {res['cluster_id']} could not be resolved"
            })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        agent_recommendations = []
        
        # Recommendation 1: Review low trust records
        if low_trust_count > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_golden_trust",
                "agent_id": "golden-record-builder",
                "field_name": "trust_score",
                "priority": "high",
                "recommendation": f"Review {low_trust_count} golden record(s) with low trust scores for manual validation",
                "timeline": "1 week"
            })
        
        # Recommendation 2: Define survivorship rules
        if not survivorship_rules:
            agent_recommendations.append({
                "recommendation_id": "rec_golden_rules",
                "agent_id": "golden-record-builder",
                "field_name": "all",
                "priority": "medium",
                "recommendation": "Define explicit survivorship rules for each column to improve consistency",
                "timeline": "1 week"
            })
        
        # Recommendation 3: Specify match keys
        if not match_key_columns:
            agent_recommendations.append({
                "recommendation_id": "rec_golden_match_keys",
                "agent_id": "golden-record-builder",
                "field_name": "match_key_columns",
                "priority": "medium",
                "recommendation": "Specify match key columns for more accurate record clustering",
                "timeline": "immediate"
            })
        
        # Recommendation 4: Add source priority
        if not source_priority and source_column:
            agent_recommendations.append({
                "recommendation_id": "rec_golden_source_priority",
                "agent_id": "golden-record-builder",
                "field_name": "source_priority",
                "priority": "medium",
                "recommendation": "Define source priority ranking for better conflict resolution",
                "timeline": "1 week"
            })
        
        # Recommendation 5: Stewardship review
        if conflicts_resolved > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_golden_stewardship",
                "agent_id": "golden-record-builder",
                "field_name": "all",
                "priority": "medium",
                "recommendation": f"Send {min(conflicts_resolved, 100)} conflict resolutions to StewardshipFlagger for review",
                "timeline": "2 weeks"
            })
        
        # Recommendation 6: Documentation
        agent_recommendations.append({
            "recommendation_id": "rec_golden_documentation",
            "agent_id": "golden-record-builder",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Document golden record creation rules and publish to data catalog",
            "timeline": "3 weeks"
        })

        # Generate cleaned file (golden records CSV)
        cleaned_file_bytes = _generate_golden_file(golden_df, filename)
        cleaned_file_base64 = base64.b64encode(cleaned_file_bytes).decode('utf-8')

        return {
            "status": "success",
            "agent_id": "golden-record-builder",
            "agent_name": "Golden Record Builder",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "input_records": total_rows,
                "golden_records_created": golden_record_count,
                "clusters_formed": len(clusters),
                "compression_ratio": round(compression_ratio, 2),
                "conflicts_resolved": conflicts_resolved,
                "values_survived": values_survived,
                "average_trust_score": round(avg_trust_score, 3),
                "total_issues": len(row_level_issues)
            },
            "data": golden_record_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary,
            "cleaned_file": {
                "filename": f"mastered_{filename}",
                "content": cleaned_file_base64,
                "size_bytes": len(cleaned_file_bytes),
                "format": filename.split('.')[-1].lower()
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "golden-record-builder",
            "agent_name": "Golden Record Builder",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _auto_detect_match_keys(df: pl.DataFrame) -> List[str]:
    """Auto-detect potential match key columns."""
    potential_keys = []
    
    for col in df.columns:
        col_lower = col.lower()
        
        # Look for common key patterns
        key_patterns = [
            r'.*id$', r'.*_id$', r'^id$', r'.*key.*', r'.*code.*',
            r'.*email.*', r'.*phone.*', r'.*ssn.*', r'.*customer.*',
            r'.*account.*', r'.*user.*'
        ]
        
        for pattern in key_patterns:
            if re.match(pattern, col_lower):
                # Check uniqueness
                uniqueness = df[col].n_unique() / df.height if df.height > 0 else 0
                if uniqueness > 0.5:  # At least 50% unique
                    potential_keys.append(col)
                break
    
    return potential_keys[:3]  # Limit to top 3


def _auto_detect_match_keys_intelligent(df: pl.DataFrame) -> List[str]:
    """
    Intelligently auto-detect match key columns for fuzzy matching.
    For fuzzy matching, prioritize name/email/phone columns over IDs.
    """
    match_cols = []
    
    # Priority 1: Names (FirstName, LastName, FullName, Name)
    for col in df.columns:
        col_lower = col.lower()
        if any(x in col_lower for x in ['firstname', 'first_name', 'lastname', 'last_name', 'fullname', 'full_name', 'name']):
            if col_lower not in [c.lower() for c in match_cols]:
                match_cols.append(col)
    
    # Priority 2: Email
    for col in df.columns:
        col_lower = col.lower()
        if 'email' in col_lower or 'mail' in col_lower:
            if col_lower not in [c.lower() for c in match_cols]:
                match_cols.append(col)
    
    # Priority 3: Phone
    for col in df.columns:
        col_lower = col.lower()
        if 'phone' in col_lower or 'mobile' in col_lower or 'contact' in col_lower:
            if col_lower not in [c.lower() for c in match_cols]:
                match_cols.append(col)
    
    # Priority 4: Address
    for col in df.columns:
        col_lower = col.lower()
        if 'address' in col_lower or 'addr' in col_lower or 'street' in col_lower:
            if col_lower not in [c.lower() for c in match_cols]:
                match_cols.append(col)
    
    # Priority 5: Other good matching columns (City, PostalCode, Country)
    for col in df.columns:
        col_lower = col.lower()
        if any(x in col_lower for x in ['city', 'postcode', 'postal', 'zip', 'country', 'state']):
            if col_lower not in [c.lower() for c in match_cols]:
                match_cols.append(col)
    
    # Return top 6 columns for fuzzy matching
    return match_cols[:6]


def _build_record_clusters(df: pl.DataFrame, match_keys: List[str]) -> Dict[str, Dict]:
    """Build clusters of related records based on match keys."""
    clusters = {}
    
    if not match_keys:
        # Each record is its own cluster
        for i in range(df.height):
            clusters[f"cluster_{i}"] = {
                "rows": [i],
                "match_values": {}
            }
        return clusters
    
    # Group by match keys
    cluster_map = defaultdict(list)
    
    for i in range(df.height):
        row = df.row(i)
        key_values = []
        for col in match_keys:
            if col in df.columns:
                val = row[df.columns.index(col)]
                # Normalize value: convert to string, strip whitespace, handle None
                if val is None:
                    key_values.append("")
                else:
                    key_values.append(str(val).strip())
            else:
                key_values.append("")
        
        cluster_map[tuple(key_values)].append(i)
    
    # Convert to cluster dict
    for idx, (key_values, rows) in enumerate(cluster_map.items()):
        cluster_id = f"cluster_{idx}"
        clusters[cluster_id] = {
            "rows": rows,
            "match_values": dict(zip(match_keys, key_values))
        }
    
    return clusters


def _get_cluster_df(df: pl.DataFrame, row_indices: List[int]) -> pl.DataFrame:
    """Get a subset of the DataFrame for the given row indices."""
    if not row_indices:
        return df.head(0)
    
    # Use filter with row numbers
    return df.with_row_index("__temp_idx__").filter(
        pl.col("__temp_idx__").is_in(row_indices)
    ).drop("__temp_idx__")


def _build_single_golden_record(
    cluster_df: pl.DataFrame,
    cluster_id: str,
    survivorship_rules: Dict[str, str],
    default_rule: str,
    source_column: Optional[str],
    source_priority: Dict[str, int],
    timestamp_column: Optional[str],
    df_full: pl.DataFrame,
    cluster_rows: List[int]
) -> Tuple[Dict[str, Any], List[Dict], int]:
    """Build a single golden record from a cluster of related records."""
    golden_record = {}
    resolutions = []
    conflicts = 0
    
    # Get the actual rows from the full dataframe
    if len(cluster_rows) == 1:
        # Single record - just use it as the golden record
        row = df_full.row(cluster_rows[0])
        for col_idx, col in enumerate(df_full.columns):
            golden_record[col] = row[col_idx]
        golden_record["__trust_score__"] = 1.0
        return golden_record, resolutions, 0
    
    # Multiple records - apply survivorship rules
    cluster_data = _get_cluster_df(df_full, cluster_rows)
    
    trust_scores = []
    
    for col in df_full.columns:
        if col.startswith("__"):
            continue
        
        rule = survivorship_rules.get(col, default_rule)
        values = cluster_data[col].to_list()
        
        # Filter out nulls for comparison
        non_null_values = [v for v in values if v is not None]
        unique_values = list(set(str(v) for v in non_null_values))
        
        if len(unique_values) <= 1:
            # No conflict
            golden_record[col] = non_null_values[0] if non_null_values else None
            trust_scores.append(1.0)
        else:
            # Conflict - apply survivorship rule
            conflicts += 1
            winning_value, confidence = _apply_survivorship_rule(
                values=values,
                rule=rule,
                cluster_data=cluster_data,
                column=col,
                source_column=source_column,
                source_priority=source_priority,
                timestamp_column=timestamp_column
            )
            
            golden_record[col] = winning_value
            trust_scores.append(confidence)
            
            resolutions.append({
                "cluster_id": cluster_id,
                "column": col,
                "competing_values": unique_values[:5],
                "winning_value": str(winning_value) if winning_value is not None else None,
                "resolution_method": rule,
                "confidence": confidence
            })
    
    # Calculate overall trust score
    golden_record["__trust_score__"] = sum(trust_scores) / len(trust_scores) if trust_scores else 1.0
    
    return golden_record, resolutions, conflicts


def _apply_survivorship_rule(
    values: List[Any],
    rule: str,
    cluster_data: pl.DataFrame,
    column: str,
    source_column: Optional[str],
    source_priority: Dict[str, int],
    timestamp_column: Optional[str]
) -> Tuple[Any, float]:
    """Apply a survivorship rule to resolve conflicting values."""
    non_null_values = [v for v in values if v is not None]
    
    if not non_null_values:
        return None, 0.5
    
    if len(set(str(v) for v in non_null_values)) == 1:
        return non_null_values[0], 1.0
    
    if rule == "most_complete" or rule == "completeness":
        # Choose the longest/most complete value
        best_value = max(non_null_values, key=lambda x: len(str(x)) if x else 0)
        confidence = 0.8
        return best_value, confidence
    
    elif rule == "most_recent" or rule == "recency":
        # Use timestamp column if available
        if timestamp_column and timestamp_column in cluster_data.columns:
            try:
                # Parse dates and sort
                sorted_df = cluster_data.sort(timestamp_column, descending=True)
                result = sorted_df[column][0]
                return result, 0.85
            except Exception as e:
                pass
        # Fallback to last value
        return non_null_values[-1], 0.7
    
    elif rule == "source_priority":
        # Use source priority
        if source_column and source_column in cluster_data.columns:
            best_priority = float('inf')
            best_value = non_null_values[0]
            
            for i, val in enumerate(values):
                if val is None:
                    continue
                source = cluster_data[source_column][i] if i < cluster_data.height else None
                priority = source_priority.get(str(source), 999)
                if priority < best_priority:
                    best_priority = priority
                    best_value = val
            
            confidence = 0.9 if best_priority < 999 else 0.7
            return best_value, confidence
        
        # Fallback to first value
        return non_null_values[0], 0.6
    
    elif rule == "most_frequent" or rule == "frequency":
        # Choose most common value
        from collections import Counter
        value_counts = Counter(str(v) for v in non_null_values)
        most_common = value_counts.most_common(1)[0]
        
        # Find original value (not stringified)
        for v in non_null_values:
            if str(v) == most_common[0]:
                frequency_ratio = most_common[1] / len(non_null_values)
                return v, min(0.95, 0.5 + frequency_ratio * 0.5)
        
        return non_null_values[0], 0.7
    
    elif rule == "min":
        try:
            return min(non_null_values), 0.9
        except:
            return non_null_values[0], 0.7
    
    elif rule == "max":
        try:
            return max(non_null_values), 0.9
        except:
            return non_null_values[0], 0.7
    
    elif rule == "first":
        return non_null_values[0], 0.75
    
    elif rule == "last":
        return non_null_values[-1], 0.75
    
    else:
        # Default: most complete
        best_value = max(non_null_values, key=lambda x: len(str(x)) if x else 0)
        return best_value, 0.7


def _create_golden_dataframe(golden_records: List[Dict], original_columns: List[str]) -> pl.DataFrame:
    """Create a DataFrame from golden records."""
    if not golden_records:
        return pl.DataFrame()
    
    # Extract just the golden record values
    data = {}
    for col in original_columns:
        data[col] = [gr["golden_record"].get(col) for gr in golden_records]
    
    # Add metadata columns
    data["__cluster_id__"] = [gr["cluster_id"] for gr in golden_records]
    data["__trust_score__"] = [gr["trust_score"] for gr in golden_records]
    data["__source_count__"] = [gr["source_record_count"] for gr in golden_records]
    
    return pl.DataFrame(data)


def _generate_golden_file(df: pl.DataFrame, original_filename: str) -> bytes:
    """Generate golden records file in CSV format."""
    output = io.BytesIO()
    df.write_csv(output)
    return output.getvalue()


def _normalize_fuzzy_value(value: Any, field_type: str) -> str:
    """Normalize value for fuzzy matching based on field type."""
    if value is None:
        return ""
    
    s_val = str(value).lower().strip()
    
    # Remove punctuation/special characters
    s_val = re.sub(r'[^\w\s]', '', s_val)
    
    if field_type == "phone":
        # Digits only
        return re.sub(r'\D', '', s_val)
    
    elif field_type == "email":
        return s_val
    
    elif field_type == "date":
        # Try to parse and format YYYY-MM-DD
        # Simple heuristic: keep alphanumeric
        return s_val
            
    elif field_type == "address":
        # Remove redundant words
        redundant = ["road", "rd", "street", "st", "avenue", "ave", "lane", "ln", "drive", "dr"]
        words = s_val.split()
        return " ".join([w for w in words if w not in redundant])
        
    return s_val


def _infer_fuzzy_field_type(column_name: str) -> str:
    """Infer fuzzy field type from a column name (heuristic)."""
    c = (column_name or "").strip().lower()
    if not c:
        return "text"
    if "email" in c:
        return "email"
    if "phone" in c or "mobile" in c or "contact" in c or c in {"msisdn"}:
        return "phone"
    if "name" in c or c in {"first_name", "lastname", "last_name", "fullname", "full_name"}:
        return "name"
    if "address" in c or "addr" in c:
        return "address"
    if "dob" in c or "birth" in c or "date" in c:
        return "date"
    if "zip" in c or "postal" in c or "pincode" in c or "pin" in c:
        return "zip"
    return "text"


def _derive_fuzzy_config(
    match_keys: List[str],
    match_key_weights: Dict[str, Any],
    all_columns: List[str]
) -> Dict[str, Any]:
    """Build internal fuzzy_config from match keys + user weights.

    If match_keys is empty, uses all columns.

    match_key_weights expects: {"colName": 0-100, ...}
    We normalize weights internally.
    """

    # Determine which columns participate in similarity.
    similarity_columns: List[str]
    if match_keys:
        similarity_columns = list(match_keys)
    else:
        # If no match keys provided, use all columns
        similarity_columns = list(all_columns)

    # Build raw weights map (0-100). If missing, distribute evenly.
    raw_weights: Dict[str, float] = {}
    for col in similarity_columns:
        w = match_key_weights.get(col)
        if w is None:
            # also allow lowercase key match
            w = match_key_weights.get(col.lower())
        try:
            w_num = float(w) if w is not None else None
        except Exception:
            w_num = None

        if w_num is None:
            # Smart default weights for auto-detected columns
            col_lower = col.lower()
            if any(x in col_lower for x in ['email', 'mail']):
                raw_weights[col] = 40.0  # Email is very unique
            elif any(x in col_lower for x in ['phone', 'mobile']):
                raw_weights[col] = 30.0  # Phone is unique
            elif any(x in col_lower for x in ['lastname', 'last_name']):
                raw_weights[col] = 35.0  # Last name is important
            elif any(x in col_lower for x in ['firstname', 'first_name']):
                raw_weights[col] = 25.0  # First name matters
            else:
                raw_weights[col] = 10.0  # Default
        else:
            raw_weights[col] = max(0.0, min(100.0, w_num))

    if similarity_columns:
        if sum(raw_weights.values()) <= 0:
            # Even distribution if nothing specified
            even = 1.0
            raw_weights = {c: even for c in similarity_columns}

    # Normalize to weights used by _calculate_record_similarity.
    total = float(sum(raw_weights.values())) if raw_weights else 0.0
    normalized = {c: (raw_weights[c] / total) if total > 0 else 1.0 for c in raw_weights}

    columns_config: Dict[str, Dict[str, Any]] = {}
    for col in similarity_columns:
        columns_config[col] = {
            "type": _infer_fuzzy_field_type(col),
            "weight": float(normalized.get(col, 1.0))
        }

    return {"columns": columns_config}


def _calculate_field_similarity(val1: str, val2: str, field_type: str) -> float:
    """Calculate similarity score (0-100) for a single field."""
    if not val1 or not val2:
        return 0.0
    
    if val1 == val2:
        return 100.0
        
    if field_type == "name":
        # Jaro-Winkler + Double Metaphone
        # Use rapidfuzz for Jaro-Winkler
        jw_score = rapidfuzz.distance.JaroWinkler.similarity(val1, val2) * 100
        
        # Use jellyfish for Metaphone (proxy for Double Metaphone if not available)
        try:
            m1 = jellyfish.metaphone(val1)
            m2 = jellyfish.metaphone(val2)
            phonetic_match = 100.0 if m1 == m2 and m1 else 0.0
        except:
            phonetic_match = 0.0
            
        # Weighted combination: 80% JW, 20% Phonetic
        return (jw_score * 0.8) + (phonetic_match * 0.2)
        
    elif field_type == "email":
        # Exact + Levenshtein
        return rapidfuzz.fuzz.ratio(val1, val2)
        
    elif field_type == "phone":
        # Exact (normalized) + Levenshtein
        return rapidfuzz.fuzz.ratio(val1, val2)
        
    elif field_type == "address":
        # Token Sort Ratio
        return rapidfuzz.fuzz.token_sort_ratio(val1, val2)
        
    elif field_type in ["dob", "zip", "pin"]:
        # Exact
        return 100.0 if val1 == val2 else 0.0
        
    else:
        # Default Levenshtein
        return rapidfuzz.fuzz.ratio(val1, val2)


def _calculate_record_similarity(row1: Dict, row2: Dict, fuzzy_config: Dict) -> Tuple[float, Dict]:
    """Calculate weighted similarity between two records."""
    total_score = 0.0
    total_weight = 0.0
    field_scores = {}
    
    columns_config = fuzzy_config.get("columns", {})
    
    # If no config provided, use all columns with equal weight and default type
    if not columns_config:
        for col in row1.keys():
            if col in row2:
                columns_config[col] = {"type": "text", "weight": 1.0}
    
    for col, config in columns_config.items():
        if col not in row1 or col not in row2:
            continue
            
        field_type = config.get("type", "text")
        weight = config.get("weight", 1.0)
        
        val1 = _normalize_fuzzy_value(row1[col], field_type)
        val2 = _normalize_fuzzy_value(row2[col], field_type)
        
        score = _calculate_field_similarity(val1, val2, field_type)
        field_scores[col] = score
        
        total_score += score * weight
        total_weight += weight
        
    if total_weight == 0:
        return 0.0, {}
        
    final_score = total_score / total_weight
    return final_score, field_scores


def _build_fuzzy_clusters(df: pl.DataFrame, fuzzy_config: Dict, threshold: float, blocking_keys: List[str]) -> Dict[str, Dict]:
    """Build clusters using fuzzy matching."""
    clusters = {}
    cluster_counter = 0
    
    # Convert to list of dicts for easier iteration
    records = df.to_dicts()
    
    # Map: cluster_id -> representative_record
    cluster_representatives = {}
    
    for i, record in enumerate(records):
        best_cluster_id = None
        best_score = -1.0
        best_field_scores = {}
        
        # Compare with existing clusters
        for cluster_id, rep_record in cluster_representatives.items():
            # Blocking check (optional optimization)
            # If blocking keys are provided, only compare if they match exactly
            if blocking_keys:
                match = True
                for k in blocking_keys:
                    if str(record.get(k)) != str(rep_record.get(k)):
                        match = False
                        break
                if not match:
                    continue
            
            score, field_scores = _calculate_record_similarity(record, rep_record, fuzzy_config)
            
            if score >= threshold and score > best_score:
                best_score = score
                best_cluster_id = cluster_id
                best_field_scores = field_scores
        
        if best_cluster_id:
            # Add to existing cluster
            clusters[best_cluster_id]["rows"].append(i)
            # Store match details
            clusters[best_cluster_id]["match_details"].append({
                "row_index": i,
                "similarity_score": best_score,
                "field_scores": best_field_scores
            })
        else:
            # Create new cluster
            cluster_id = f"cluster_{cluster_counter}"
            cluster_counter += 1
            clusters[cluster_id] = {
                "rows": [i],
                "match_values": {},
                "match_details": [] # First record has no match details relative to itself
            }
            cluster_representatives[cluster_id] = record
            
    return clusters
