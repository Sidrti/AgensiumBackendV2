"""
Survivorship Resolver Agent

Determines which field values should "survive" when multiple sources provide different
or conflicting values for the same entity. Applies business rules, scoring logic,
and priority models to pick the best possible value.

This agent is the "brain" behind decision-making when merging records. It supports:
1. Freshness/Timestamp-based resolution
2. Data Quality Scoring
3. Value Length/Data Richness
4. Business Rules (custom field-level logic)
5. Source Priority

Key Responsibilities:
- Compare conflicting field values
- Apply hierarchical rule engine
- Support field-level custom rules
- Pass resolved fields to GoldenRecordBuilder

Input: CSV file with potential duplicates/related records
Output: Resolved field values with confidence scores and resolution explanations
"""

import io
import re
import time
import base64
import polars as pl
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from collections import Counter, defaultdict


# ==================== VALIDATION PATTERNS ====================
VALIDATION_PATTERNS = {
    "email": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    "phone_e164": r'^\+[1-9]\d{6,14}$',
    "phone_general": r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]{6,}$',
    "date_iso": r'^\d{4}-\d{2}-\d{2}$',
    "date_general": r'^\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}$',
    "uuid": r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
    "zip_us": r'^\d{5}(-\d{4})?$',
    "url": r'^https?://[^\s/$.?#].[^\s]*$',
    "ssn": r'^\d{3}-\d{2}-\d{4}$'
}

# ==================== FIELD TYPE DETECTION ====================
FIELD_TYPE_PATTERNS = {
    "email": [r'email', r'e[-_]?mail', r'mail'],
    "phone": [r'phone', r'mobile', r'cell', r'tel', r'fax'],
    "date": [r'date', r'_at$', r'_on$', r'timestamp', r'created', r'updated', r'modified'],
    "name": [r'name', r'first[-_]?name', r'last[-_]?name', r'full[-_]?name'],
    "address": [r'address', r'street', r'city', r'state', r'zip', r'postal', r'country'],
    "id": [r'_id$', r'^id$', r'identifier', r'key', r'code'],
    "gender": [r'gender', r'sex'],
    "boolean": [r'is_', r'has_', r'can_', r'enabled', r'active', r'flag']
}


def execute_survivorship_resolver(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Resolve conflicting field values using hierarchical survivorship rules.

    Args:
        file_contents: File bytes (read as binary)
        filename: Original filename
        parameters: Agent parameters including rules and thresholds

    Returns:
        Standardized output dictionary with resolution results
    """

    start_time = time.time()
    parameters = parameters or {}

    # Extract parameters with defaults
    match_key_columns = parameters.get("match_key_columns", [])
    survivorship_rules = parameters.get("survivorship_rules", {})  # column -> rule
    source_priority = parameters.get("source_priority", {})  # source -> priority (lower = better)
    source_column = parameters.get("source_column", None)
    timestamp_column = parameters.get("timestamp_column", None)
    quality_score_columns = parameters.get("quality_score_columns", {})  # column -> quality score column
    default_rule = parameters.get("default_rule", "quality_score")
    min_confidence_threshold = parameters.get("min_confidence_threshold", 0.5)
    
    # Field-specific validation rules
    field_validation_rules = parameters.get("field_validation_rules", {})
    
    # Scoring thresholds
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file - CSV only
        if not filename.endswith('.csv'):
            return {
                "status": "error",
                "agent_id": "survivorship-resolver",
                "error": f"Unsupported file format: {filename}. Only CSV files are supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        try:
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": "survivorship-resolver",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.height == 0:
            return {
                "status": "error",
                "agent_id": "survivorship-resolver",
                "agent_name": "Survivorship Resolver",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        total_rows = df.height
        total_columns = len(df.columns)
        
        # Auto-detect match key columns if not provided
        if not match_key_columns:
            match_key_columns = _auto_detect_match_keys(df)
        
        valid_match_keys = [col for col in match_key_columns if col in df.columns]
        
        # Auto-detect field types for validation
        field_types = _detect_field_types(df)
        
        # ==================== CLUSTER RELATED RECORDS ====================
        clusters = _build_record_clusters(df, valid_match_keys)
        
        # ==================== RESOLVE CONFLICTS ====================
        resolved_fields = []
        resolution_log = []
        conflicts_detected = 0
        conflicts_resolved = 0
        values_survived = 0
        low_confidence_resolutions = 0
        unresolved_conflicts = 0
        row_level_issues = []
        
        rules_applied = defaultdict(int)
        resolution_by_field = defaultdict(lambda: {"resolved": 0, "unresolved": 0})
        
        for cluster_id, cluster_info in clusters.items():
            cluster_rows = cluster_info["rows"]
            
            if len(cluster_rows) <= 1:
                # Single record - no conflicts possible
                continue
            
            # Get cluster data
            cluster_data = _get_cluster_df(df, cluster_rows)
            
            for col in df.columns:
                if col.startswith("__"):
                    continue
                
                values = cluster_data[col].to_list()
                non_null_values = [v for v in values if v is not None and str(v).strip() != '']
                unique_values = list(set(str(v) for v in non_null_values))
                
                if len(unique_values) <= 1:
                    # No conflict
                    continue
                
                conflicts_detected += 1
                
                # Determine rule to apply
                rule = survivorship_rules.get(col, default_rule)
                field_type = field_types.get(col, "unknown")
                
                # Apply resolution
                result = _resolve_conflict(
                    values=values,
                    cluster_data=cluster_data,
                    column=col,
                    rule=rule,
                    field_type=field_type,
                    source_column=source_column,
                    source_priority=source_priority,
                    timestamp_column=timestamp_column,
                    quality_score_columns=quality_score_columns,
                    field_validation_rules=field_validation_rules,
                    df=df
                )
                
                resolved_fields.append({
                    "cluster_id": cluster_id,
                    "column": col,
                    "field_type": field_type,
                    "competing_values": unique_values[:5],
                    "value_count": len(unique_values),
                    "winner": result["winner"],
                    "rule_applied": result["rule_applied"],
                    "confidence": result["confidence"],
                    "rationale": result["rationale"],
                    "scores": result.get("scores", {}),
                    "source_rows": cluster_rows
                })
                
                rules_applied[result["rule_applied"]] += 1
                
                if result["confidence"] >= min_confidence_threshold:
                    conflicts_resolved += 1
                    values_survived += 1
                    resolution_by_field[col]["resolved"] += 1
                else:
                    low_confidence_resolutions += 1
                    resolution_by_field[col]["unresolved"] += 1
                    
                    if result["confidence"] < 0.3:
                        unresolved_conflicts += 1
                        row_level_issues.append({
                            "row_index": cluster_rows[0],
                            "column": col,
                            "issue_type": "unresolved_conflict",
                            "severity": "high",
                            "original_value": str(unique_values),
                            "message": f"Could not confidently resolve conflict for '{col}' ({result['confidence']:.2f} confidence)"
                        })
                
                resolution_log.append({
                    "cluster_id": cluster_id,
                    "column": col,
                    "from_values": unique_values[:3],
                    "to_value": str(result["winner"]) if result["winner"] is not None else None,
                    "rule": result["rule_applied"],
                    "confidence": result["confidence"],
                    "rationale": result["rationale"]
                })
        
        # ==================== CALCULATE SCORES ====================
        resolution_rate = (conflicts_resolved / max(conflicts_detected, 1)) * 100
        avg_confidence = (
            sum(rf["confidence"] for rf in resolved_fields) / len(resolved_fields)
            if resolved_fields else 1.0
        )
        
        # Overall score
        resolution_component = resolution_rate * 0.5
        confidence_component = avg_confidence * 100 * 0.35
        coverage_component = ((conflicts_detected - unresolved_conflicts) / max(conflicts_detected, 1)) * 100 * 0.15
        
        overall_score = resolution_component + confidence_component + coverage_component
        
        if overall_score >= excellent_threshold:
            quality_status = "excellent"
        elif overall_score >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"
        
        # Cap row-level issues
        row_level_issues = row_level_issues[:1000]
        
        # Issue summary
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
        
        # ==================== BUILD RESPONSE DATA ====================
        survivorship_data = {
            "survivorship_score": round(overall_score, 1),
            "quality_status": quality_status,
            "resolved_fields": resolved_fields[:200],
            "resolution_log": resolution_log[:500],
            "statistics": {
                "total_records": total_rows,
                "total_columns": total_columns,
                "clusters_analyzed": len(clusters),
                "conflicts_detected": conflicts_detected,
                "conflicts_resolved": conflicts_resolved,
                "values_survived": values_survived,
                "unresolved_conflicts": unresolved_conflicts,
                "low_confidence_resolutions": low_confidence_resolutions,
                "resolution_rate": round(resolution_rate, 1),
                "average_confidence": round(avg_confidence, 3)
            },
            "rules_applied": dict(rules_applied),
            "resolution_by_field": dict(resolution_by_field),
            "field_types_detected": field_types,
            "summary": f"Survivorship resolution completed. Detected {conflicts_detected} conflicts, "
                      f"resolved {conflicts_resolved} ({resolution_rate:.1f}% resolution rate). "
                      f"Average confidence: {avg_confidence:.2f}.",
            "row_level_issues": row_level_issues[:100],
            "issue_summary": issue_summary,
            "overrides": {
                "match_key_columns": match_key_columns,
                "default_rule": default_rule,
                "min_confidence_threshold": min_confidence_threshold,
                "source_column": source_column,
                "timestamp_column": timestamp_column
            }
        }
        
        # ==================== EXECUTIVE SUMMARY ====================
        executive_summary = [{
            "summary_id": "exec_survivorship_resolver",
            "title": "Survivorship Resolution",
            "value": f"{resolution_rate:.1f}%",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"{conflicts_resolved}/{conflicts_detected} conflicts resolved, "
                          f"Avg confidence: {avg_confidence:.2f}"
        }]
        
        # ==================== AI ANALYSIS TEXT ====================
        ai_analysis_parts = [
            "SURVIVORSHIP RESOLVER ANALYSIS:",
            f"- Resolution Score: {overall_score:.1f}/100 ({quality_status})",
            f"- Conflicts Detected: {conflicts_detected}",
            f"- Conflicts Resolved: {conflicts_resolved} ({resolution_rate:.1f}%)",
            f"- Average Confidence: {avg_confidence:.2f}",
            f"- Clusters Analyzed: {len(clusters)}",
            f"- Unresolved Conflicts: {unresolved_conflicts}"
        ]
        
        if rules_applied:
            top_rules = sorted(rules_applied.items(), key=lambda x: x[1], reverse=True)[:3]
            ai_analysis_parts.append(f"- Top Rules Used: {', '.join(f'{r}({c})' for r, c in top_rules)}")
        
        if low_confidence_resolutions > 0:
            ai_analysis_parts.append(f"- Low Confidence Resolutions: {low_confidence_resolutions}")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # ==================== ALERTS ====================
        alerts = []
        
        if unresolved_conflicts > 0:
            alerts.append({
                "alert_id": "alert_survivorship_unresolved",
                "severity": "high" if unresolved_conflicts > conflicts_detected * 0.2 else "medium",
                "category": "conflict_resolution",
                "message": f"{unresolved_conflicts} conflict(s) could not be confidently resolved",
                "affected_fields_count": unresolved_conflicts,
                "recommendation": "Review low-confidence resolutions and define explicit survivorship rules."
            })
        
        if low_confidence_resolutions > conflicts_resolved * 0.3:
            alerts.append({
                "alert_id": "alert_survivorship_low_confidence",
                "severity": "medium",
                "category": "data_quality",
                "message": f"{low_confidence_resolutions} resolutions have low confidence scores",
                "affected_fields_count": low_confidence_resolutions,
                "recommendation": "Improve data quality or add source priority configuration."
            })
        
        if conflicts_detected == 0 and len(clusters) > 1:
            alerts.append({
                "alert_id": "alert_survivorship_no_conflicts",
                "severity": "info",
                "category": "configuration",
                "message": "No conflicts detected - data may already be consistent",
                "affected_fields_count": 0,
                "recommendation": "Verify match key columns are correctly configured."
            })
        
        if not survivorship_rules and conflicts_detected > 0:
            alerts.append({
                "alert_id": "alert_survivorship_no_rules",
                "severity": "medium",
                "category": "configuration",
                "message": "No explicit survivorship rules defined - using defaults",
                "affected_fields_count": conflicts_detected,
                "recommendation": "Define survivorship_rules for each field for better control."
            })
        
        if overall_score < good_threshold:
            alerts.append({
                "alert_id": "alert_survivorship_quality",
                "severity": "high",
                "category": "overall_quality",
                "message": f"Resolution quality score ({overall_score:.1f}%) below threshold",
                "affected_fields_count": conflicts_detected,
                "recommendation": "Review source data quality and survivorship configuration."
            })
        
        # ==================== ISSUES ====================
        issues = []
        
        for rf in resolved_fields:
            if rf["confidence"] < min_confidence_threshold:
                issues.append({
                    "issue_id": f"issue_survivorship_{rf['cluster_id']}_{rf['column']}",
                    "agent_id": "survivorship-resolver",
                    "field_name": rf["column"],
                    "issue_type": "low_confidence_resolution",
                    "severity": "warning" if rf["confidence"] >= 0.3 else "high",
                    "message": f"Low confidence ({rf['confidence']:.2f}) resolution for '{rf['column']}' in {rf['cluster_id']}"
                })
        
        issues = issues[:50]  # Limit issues
        
        # ==================== RECOMMENDATIONS ====================
        agent_recommendations = []
        
        if unresolved_conflicts > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_survivorship_stewardship",
                "agent_id": "survivorship-resolver",
                "field_name": "all",
                "priority": "high",
                "recommendation": f"Send {unresolved_conflicts} unresolved conflicts to StewardshipFlagger for human review",
                "timeline": "immediate"
            })
        
        if not survivorship_rules:
            agent_recommendations.append({
                "recommendation_id": "rec_survivorship_rules",
                "agent_id": "survivorship-resolver",
                "field_name": "all",
                "priority": "medium",
                "recommendation": "Define explicit survivorship rules for each column",
                "timeline": "1 week"
            })
        
        if not source_priority and source_column:
            agent_recommendations.append({
                "recommendation_id": "rec_survivorship_source_priority",
                "agent_id": "survivorship-resolver",
                "field_name": "source",
                "priority": "medium",
                "recommendation": "Define source priority ranking for better conflict resolution",
                "timeline": "1 week"
            })
        
        fields_needing_rules = [
            col for col, stats in resolution_by_field.items()
            if stats["unresolved"] > stats["resolved"]
        ]
        if fields_needing_rules:
            agent_recommendations.append({
                "recommendation_id": "rec_survivorship_field_rules",
                "agent_id": "survivorship-resolver",
                "field_name": ", ".join(fields_needing_rules[:5]),
                "priority": "high",
                "recommendation": f"Define specific rules for frequently conflicting fields: {', '.join(fields_needing_rules[:5])}",
                "timeline": "1 week"
            })
        
        if timestamp_column is None:
            agent_recommendations.append({
                "recommendation_id": "rec_survivorship_timestamp",
                "agent_id": "survivorship-resolver",
                "field_name": "timestamp_column",
                "priority": "low",
                "recommendation": "Specify a timestamp column to enable recency-based survivorship",
                "timeline": "2 weeks"
            })
        
        agent_recommendations.append({
            "recommendation_id": "rec_survivorship_documentation",
            "agent_id": "survivorship-resolver",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Document survivorship rules and resolution logic for governance compliance",
            "timeline": "3 weeks"
        })

        # Generate resolved output file
        resolved_df = _apply_resolutions_to_df(df, resolved_fields, clusters)
        resolved_file_bytes = _generate_resolved_file(resolved_df, filename)
        resolved_file_base64 = base64.b64encode(resolved_file_bytes).decode('utf-8')

        return {
            "status": "success",
            "agent_id": "survivorship-resolver",
            "agent_name": "Survivorship Resolver",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_records": total_rows,
                "clusters_analyzed": len(clusters),
                "conflicts_detected": conflicts_detected,
                "conflicts_resolved": conflicts_resolved,
                "values_survived": values_survived,
                "unresolved_conflicts": unresolved_conflicts,
                "resolution_rate": round(resolution_rate, 1),
                "average_confidence": round(avg_confidence, 3),
                "total_issues": len(row_level_issues)
            },
            "data": survivorship_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary,
            "cleaned_file": {
                "filename": f"mastered_{filename}",
                "content": resolved_file_base64,
                "size_bytes": len(resolved_file_bytes),
                "format": filename.split('.')[-1].lower()
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "survivorship-resolver",
            "agent_name": "Survivorship Resolver",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _auto_detect_match_keys(df: pl.DataFrame) -> List[str]:
    """Auto-detect potential match key columns."""
    potential_keys = []
    
    for col in df.columns:
        col_lower = col.lower()
        
        key_patterns = [
            r'.*id$', r'.*_id$', r'^id$', r'.*key.*', r'.*code.*',
            r'.*email.*', r'.*phone.*', r'.*customer.*', r'.*account.*'
        ]
        
        for pattern in key_patterns:
            if re.match(pattern, col_lower):
                uniqueness = df[col].n_unique() / df.height if df.height > 0 else 0
                if uniqueness > 0.5:
                    potential_keys.append(col)
                break
    
    return potential_keys[:3]


def _detect_field_types(df: pl.DataFrame) -> Dict[str, str]:
    """Detect semantic field types for each column."""
    field_types = {}
    
    for col in df.columns:
        col_lower = col.lower()
        detected_type = "unknown"
        
        for field_type, patterns in FIELD_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, col_lower):
                    detected_type = field_type
                    break
            if detected_type != "unknown":
                break
        
        field_types[col] = detected_type
    
    return field_types


def _build_record_clusters(df: pl.DataFrame, match_keys: List[str]) -> Dict[str, Dict]:
    """Build clusters of related records based on match keys."""
    clusters = {}
    
    if not match_keys:
        for i in range(df.height):
            clusters[f"cluster_{i}"] = {"rows": [i], "match_values": {}}
        return clusters
    
    cluster_map = defaultdict(list)
    
    for i in range(df.height):
        row = df.row(i)
        key_values = tuple(
            str(row[df.columns.index(col)]) if col in df.columns else ""
            for col in match_keys
        )
        cluster_map[key_values].append(i)
    
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
    
    return df.with_row_index("__temp_idx__").filter(
        pl.col("__temp_idx__").is_in(row_indices)
    ).drop("__temp_idx__")


def _resolve_conflict(
    values: List[Any],
    cluster_data: pl.DataFrame,
    column: str,
    rule: str,
    field_type: str,
    source_column: Optional[str],
    source_priority: Dict[str, int],
    timestamp_column: Optional[str],
    quality_score_columns: Dict[str, str],
    field_validation_rules: Dict[str, Dict],
    df: pl.DataFrame
) -> Dict[str, Any]:
    """Apply survivorship rules to resolve a field conflict."""
    non_null_values = [v for v in values if v is not None and str(v).strip() != '']
    
    if not non_null_values:
        return {
            "winner": None,
            "rule_applied": "no_valid_values",
            "confidence": 0.3,
            "rationale": "No non-null values available",
            "scores": {}
        }
    
    if len(set(str(v) for v in non_null_values)) == 1:
        return {
            "winner": non_null_values[0],
            "rule_applied": "unanimous",
            "confidence": 1.0,
            "rationale": "All non-null values are identical",
            "scores": {}
        }
    
    # Calculate quality scores for each value
    quality_scores = []
    for i, val in enumerate(values):
        if val is None or str(val).strip() == '':
            quality_scores.append(0.0)
            continue
        
        score = _calculate_value_quality_score(
            value=val,
            field_type=field_type,
            field_validation_rules=field_validation_rules.get(column, {})
        )
        quality_scores.append(score)
    
    # Apply the specified rule
    if rule == "freshness" or rule == "most_recent" or rule == "recency":
        return _apply_freshness_rule(values, cluster_data, column, timestamp_column, quality_scores)
    
    elif rule == "quality_score" or rule == "quality":
        return _apply_quality_score_rule(values, quality_scores)
    
    elif rule == "completeness" or rule == "most_complete":
        return _apply_completeness_rule(values, quality_scores)
    
    elif rule == "source_priority":
        return _apply_source_priority_rule(values, cluster_data, source_column, source_priority, quality_scores)
    
    elif rule == "most_frequent" or rule == "frequency":
        return _apply_frequency_rule(values, quality_scores)
    
    elif rule == "longest" or rule == "richness":
        return _apply_richness_rule(values, quality_scores)
    
    elif rule == "format_valid" or rule == "validation":
        return _apply_validation_rule(values, field_type, quality_scores)
    
    elif rule == "min":
        return _apply_min_rule(values)
    
    elif rule == "max":
        return _apply_max_rule(values)
    
    elif rule == "first":
        return {"winner": non_null_values[0], "rule_applied": "first", "confidence": 0.6, "rationale": "First non-null value", "scores": {}}
    
    elif rule == "last":
        return {"winner": non_null_values[-1], "rule_applied": "last", "confidence": 0.6, "rationale": "Last non-null value", "scores": {}}
    
    else:
        # Default: combined quality score
        return _apply_quality_score_rule(values, quality_scores)


def _calculate_value_quality_score(
    value: Any,
    field_type: str,
    field_validation_rules: Dict
) -> float:
    """Calculate a quality score for a single value."""
    if value is None:
        return 0.0
    
    str_val = str(value).strip()
    if not str_val:
        return 0.0
    
    score = 0.5  # Base score
    
    # Completeness bonus
    score += min(0.2, len(str_val) / 100)
    
    # Format validation
    pattern = None
    if field_type == "email":
        pattern = VALIDATION_PATTERNS["email"]
    elif field_type == "phone":
        pattern = VALIDATION_PATTERNS["phone_general"]
    elif field_type == "date":
        pattern = VALIDATION_PATTERNS["date_general"]
    
    if pattern:
        if re.match(pattern, str_val):
            score += 0.3
        else:
            score -= 0.2
    
    # Custom validation rules
    if field_validation_rules:
        if "pattern" in field_validation_rules:
            if re.match(field_validation_rules["pattern"], str_val):
                score += 0.2
            else:
                score -= 0.2
        
        if "min_length" in field_validation_rules:
            if len(str_val) >= field_validation_rules["min_length"]:
                score += 0.1
        
        if "allowed_values" in field_validation_rules:
            if str_val.lower() in [v.lower() for v in field_validation_rules["allowed_values"]]:
                score += 0.2
    
    return min(1.0, max(0.0, score))


def _apply_freshness_rule(
    values: List[Any],
    cluster_data: pl.DataFrame,
    column: str,
    timestamp_column: Optional[str],
    quality_scores: List[float]
) -> Dict[str, Any]:
    """Apply freshness/recency rule."""
    if timestamp_column and timestamp_column in cluster_data.columns:
        try:
            # Find row with most recent timestamp
            timestamps = cluster_data[timestamp_column].to_list()
            valid_indices = [
                (i, ts) for i, ts in enumerate(timestamps)
                if ts is not None and values[i] is not None
            ]
            
            if valid_indices:
                # Sort by timestamp descending
                sorted_indices = sorted(valid_indices, key=lambda x: str(x[1]), reverse=True)
                winner_idx = sorted_indices[0][0]
                
                return {
                    "winner": values[winner_idx],
                    "rule_applied": "freshness",
                    "confidence": 0.85,
                    "rationale": f"Most recent value (timestamp: {timestamps[winner_idx]})",
                    "scores": {"quality": quality_scores[winner_idx]}
                }
        except Exception:
            pass
    
    # Fallback to last non-null value
    non_null = [(i, v) for i, v in enumerate(values) if v is not None]
    if non_null:
        winner_idx = non_null[-1][0]
        return {
            "winner": non_null[-1][1],
            "rule_applied": "freshness_fallback",
            "confidence": 0.6,
            "rationale": "Last available value (no timestamp column)",
            "scores": {"quality": quality_scores[winner_idx]}
        }
    
    return {"winner": None, "rule_applied": "freshness", "confidence": 0.3, "rationale": "No valid values", "scores": {}}


def _apply_quality_score_rule(values: List[Any], quality_scores: List[float]) -> Dict[str, Any]:
    """Apply quality score rule."""
    best_idx = max(range(len(values)), key=lambda i: quality_scores[i])
    
    if values[best_idx] is None:
        non_null = [(i, v) for i, v in enumerate(values) if v is not None]
        if non_null:
            best_idx = max(non_null, key=lambda x: quality_scores[x[0]])[0]
    
    return {
        "winner": values[best_idx],
        "rule_applied": "quality_score",
        "confidence": quality_scores[best_idx],
        "rationale": f"Highest quality score ({quality_scores[best_idx]:.2f})",
        "scores": {"quality": quality_scores[best_idx]}
    }


def _apply_completeness_rule(values: List[Any], quality_scores: List[float]) -> Dict[str, Any]:
    """Apply completeness/most complete rule."""
    non_null = [(i, v) for i, v in enumerate(values) if v is not None]
    
    if not non_null:
        return {"winner": None, "rule_applied": "completeness", "confidence": 0.3, "rationale": "No valid values", "scores": {}}
    
    # Find longest non-null value
    best = max(non_null, key=lambda x: len(str(x[1])))
    best_idx = best[0]
    
    return {
        "winner": best[1],
        "rule_applied": "completeness",
        "confidence": min(0.9, 0.5 + len(str(best[1])) / 100),
        "rationale": f"Most complete value (length: {len(str(best[1]))})",
        "scores": {"quality": quality_scores[best_idx], "length": len(str(best[1]))}
    }


def _apply_source_priority_rule(
    values: List[Any],
    cluster_data: pl.DataFrame,
    source_column: Optional[str],
    source_priority: Dict[str, int],
    quality_scores: List[float]
) -> Dict[str, Any]:
    """Apply source priority rule."""
    if not source_column or source_column not in cluster_data.columns:
        return _apply_quality_score_rule(values, quality_scores)
    
    sources = cluster_data[source_column].to_list()
    best_priority = float('inf')
    best_idx = 0
    
    for i, (val, src) in enumerate(zip(values, sources)):
        if val is None:
            continue
        priority = source_priority.get(str(src), 999)
        if priority < best_priority:
            best_priority = priority
            best_idx = i
    
    confidence = 0.9 if best_priority < 999 else 0.6
    
    return {
        "winner": values[best_idx],
        "rule_applied": "source_priority",
        "confidence": confidence,
        "rationale": f"Highest priority source ({sources[best_idx]}, priority: {best_priority})",
        "scores": {"quality": quality_scores[best_idx], "priority": best_priority}
    }


def _apply_frequency_rule(values: List[Any], quality_scores: List[float]) -> Dict[str, Any]:
    """Apply most frequent value rule."""
    non_null = [str(v) for v in values if v is not None]
    
    if not non_null:
        return {"winner": None, "rule_applied": "frequency", "confidence": 0.3, "rationale": "No valid values", "scores": {}}
    
    counter = Counter(non_null)
    most_common = counter.most_common(1)[0]
    frequency_ratio = most_common[1] / len(non_null)
    
    # Find original value
    for i, v in enumerate(values):
        if str(v) == most_common[0]:
            return {
                "winner": v,
                "rule_applied": "frequency",
                "confidence": min(0.95, 0.5 + frequency_ratio * 0.5),
                "rationale": f"Most frequent value ({most_common[1]}/{len(non_null)} occurrences)",
                "scores": {"quality": quality_scores[i], "frequency": frequency_ratio}
            }
    
    return {"winner": most_common[0], "rule_applied": "frequency", "confidence": 0.7, "rationale": "Most frequent value", "scores": {}}


def _apply_richness_rule(values: List[Any], quality_scores: List[float]) -> Dict[str, Any]:
    """Apply value length/richness rule."""
    non_null = [(i, v) for i, v in enumerate(values) if v is not None]
    
    if not non_null:
        return {"winner": None, "rule_applied": "richness", "confidence": 0.3, "rationale": "No valid values", "scores": {}}
    
    best = max(non_null, key=lambda x: len(str(x[1])))
    
    return {
        "winner": best[1],
        "rule_applied": "richness",
        "confidence": 0.8,
        "rationale": f"Richest/longest value (length: {len(str(best[1]))})",
        "scores": {"quality": quality_scores[best[0]], "length": len(str(best[1]))}
    }


def _apply_validation_rule(values: List[Any], field_type: str, quality_scores: List[float]) -> Dict[str, Any]:
    """Apply format validation rule."""
    pattern = None
    if field_type == "email":
        pattern = VALIDATION_PATTERNS["email"]
    elif field_type == "phone":
        pattern = VALIDATION_PATTERNS["phone_e164"]
    elif field_type == "date":
        pattern = VALIDATION_PATTERNS["date_iso"]
    
    if pattern:
        for i, v in enumerate(values):
            if v is not None and re.match(pattern, str(v)):
                return {
                    "winner": v,
                    "rule_applied": "validation",
                    "confidence": 0.9,
                    "rationale": f"First value matching {field_type} format",
                    "scores": {"quality": quality_scores[i]}
                }
    
    # Fallback to quality score
    return _apply_quality_score_rule(values, quality_scores)


def _apply_min_rule(values: List[Any]) -> Dict[str, Any]:
    """Apply minimum value rule."""
    try:
        non_null = [v for v in values if v is not None]
        winner = min(non_null)
        return {"winner": winner, "rule_applied": "min", "confidence": 0.9, "rationale": "Minimum value", "scores": {}}
    except:
        return {"winner": values[0] if values else None, "rule_applied": "min", "confidence": 0.5, "rationale": "Could not compare values", "scores": {}}


def _apply_max_rule(values: List[Any]) -> Dict[str, Any]:
    """Apply maximum value rule."""
    try:
        non_null = [v for v in values if v is not None]
        winner = max(non_null)
        return {"winner": winner, "rule_applied": "max", "confidence": 0.9, "rationale": "Maximum value", "scores": {}}
    except:
        return {"winner": values[0] if values else None, "rule_applied": "max", "confidence": 0.5, "rationale": "Could not compare values", "scores": {}}


def _apply_resolutions_to_df(
    df: pl.DataFrame,
    resolved_fields: List[Dict],
    clusters: Dict[str, Dict]
) -> pl.DataFrame:
    """Apply resolutions to create a resolved DataFrame (one row per cluster)."""
    if not resolved_fields:
        return df
    
    # Group resolutions by cluster
    cluster_resolutions = defaultdict(dict)
    for rf in resolved_fields:
        cluster_id = rf["cluster_id"]
        column = rf["column"]
        cluster_resolutions[cluster_id][column] = rf["winner"]
    
    # Build resolved DataFrame - one row per cluster
    resolved_data = {col: [] for col in df.columns}
    resolved_data["__cluster_id__"] = []
    resolved_data["__resolution_confidence__"] = []
    
    for cluster_id, cluster_info in clusters.items():
        cluster_rows = cluster_info["rows"]
        if not cluster_rows:
            continue
        
        # Start with first row of cluster
        first_row = df.row(cluster_rows[0])
        
        for col_idx, col in enumerate(df.columns):
            # Use resolved value if available, otherwise use first row value
            if cluster_id in cluster_resolutions and col in cluster_resolutions[cluster_id]:
                resolved_data[col].append(cluster_resolutions[cluster_id][col])
            else:
                resolved_data[col].append(first_row[col_idx])
        
        resolved_data["__cluster_id__"].append(cluster_id)
        
        # Calculate average confidence for this cluster
        cluster_confidences = [
            rf["confidence"] for rf in resolved_fields
            if rf["cluster_id"] == cluster_id
        ]
        avg_conf = sum(cluster_confidences) / len(cluster_confidences) if cluster_confidences else 1.0
        resolved_data["__resolution_confidence__"].append(round(avg_conf, 3))
    
    return pl.DataFrame(resolved_data)


def _generate_resolved_file(df: pl.DataFrame, original_filename: str) -> bytes:
    """Generate resolved data file in CSV format."""
    output = io.BytesIO()
    df.write_csv(output)
    return output.getvalue()
