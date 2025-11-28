"""
Key Identifier Agent

Analyzes the structural properties of a dataset and proposes candidate primary keys,
foreign keys, and entity keys based on statistical inference and heuristics.

Key Types Identified:
- Candidate Primary Key (PK): Columns with high uniqueness (>99%) and low null density (0%)
- Candidate Foreign Key (FK): Columns with high overlap with known primary keys of other tables
- Candidate Entity Key: Columns with moderate uniqueness vital for entity matching (e.g., EmailAddress)

Input: CSV file (primary)
Output: Key analysis with candidate keys, confidence scores, and recommendations
"""

import polars as pl
import numpy as np
import io
import time
import re
import base64
from typing import Dict, Any, Optional, List


def execute_key_identifier(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Identify candidate keys in dataset.

    Args:
        file_contents: File bytes (read as binary)
        filename: Original filename (used to detect format)
        parameters: Agent parameters from tool.json

    Returns:
        Standardized output dictionary with key analysis
    """

    start_time = time.time()
    parameters = parameters or {}

    # Extract parameters with defaults
    pk_uniqueness_threshold = parameters.get("pk_uniqueness_threshold", 99.0)  # % uniqueness for PK candidate
    pk_null_threshold = parameters.get("pk_null_threshold", 0.0)  # Max % nulls for PK candidate
    entity_key_uniqueness_min = parameters.get("entity_key_uniqueness_min", 50.0)  # Min uniqueness for entity key
    entity_key_uniqueness_max = parameters.get("entity_key_uniqueness_max", 99.0)  # Max uniqueness for entity key
    fk_overlap_threshold = parameters.get("fk_overlap_threshold", 70.0)  # % overlap for FK detection
    reference_tables = parameters.get("reference_tables", {})  # Dict of table_name -> {column: [values]}
    analyze_composite_keys = parameters.get("analyze_composite_keys", True)
    max_composite_key_columns = parameters.get("max_composite_key_columns", 3)
    
    # Scoring weights
    uniqueness_weight = parameters.get("uniqueness_weight", 0.4)
    null_density_weight = parameters.get("null_density_weight", 0.3)
    pattern_weight = parameters.get("pattern_weight", 0.3)
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file - CSV only
        if not filename.endswith('.csv'):
            return {
                "status": "error",
                "agent_id": "key-identifier",
                "error": f"Unsupported file format: {filename}. Only CSV files are supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        try:
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": "key-identifier",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.height == 0:
            return {
                "status": "error",
                "agent_id": "key-identifier",
                "agent_name": "Key Identifier",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        total_rows = df.height
        total_columns = len(df.columns)
        
        # Analyze each column for key potential
        column_analysis = []
        candidate_primary_keys = []
        candidate_foreign_keys = []
        candidate_entity_keys = []
        
        for col in df.columns:
            col_data = df[col]
            null_count = col_data.null_count()
            null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0
            
            # Calculate uniqueness
            unique_count = col_data.n_unique()
            non_null_count = total_rows - null_count
            uniqueness_pct = (unique_count / non_null_count * 100) if non_null_count > 0 else 0
            
            # Detect patterns
            pattern_info = _detect_key_patterns(col, col_data)
            
            # Calculate key confidence score
            key_score = _calculate_key_score(
                uniqueness_pct, 
                null_pct, 
                pattern_info,
                {
                    "uniqueness_weight": uniqueness_weight,
                    "null_density_weight": null_density_weight,
                    "pattern_weight": pattern_weight
                }
            )
            
            # Determine key type
            key_type = None
            key_confidence = 0.0
            key_reasoning = []
            
            # Check for Primary Key candidate
            if uniqueness_pct >= pk_uniqueness_threshold and null_pct <= pk_null_threshold:
                key_type = "primary_key"
                key_confidence = min(100, uniqueness_pct * 0.5 + (100 - null_pct) * 0.3 + pattern_info.get("id_pattern_score", 0) * 0.2)
                key_reasoning.append(f"High uniqueness ({uniqueness_pct:.1f}%)")
                key_reasoning.append(f"Low null density ({null_pct:.1f}%)")
                if pattern_info.get("is_id_pattern"):
                    key_reasoning.append(f"Matches ID pattern: {pattern_info.get('pattern_type')}")
                
                candidate_primary_keys.append({
                    "column": col,
                    "confidence": round(key_confidence, 2),
                    "uniqueness_percentage": round(uniqueness_pct, 2),
                    "null_percentage": round(null_pct, 2),
                    "pattern_type": pattern_info.get("pattern_type"),
                    "reasoning": key_reasoning,
                    "sample_values": _get_sample_values(col_data, 5)
                })
            
            # Check for Entity Key candidate
            elif entity_key_uniqueness_min <= uniqueness_pct < entity_key_uniqueness_max:
                key_type = "entity_key"
                key_confidence = min(100, uniqueness_pct * 0.4 + (100 - null_pct) * 0.3 + pattern_info.get("entity_pattern_score", 0) * 0.3)
                key_reasoning.append(f"Moderate uniqueness ({uniqueness_pct:.1f}%)")
                if pattern_info.get("is_entity_pattern"):
                    key_reasoning.append(f"Matches entity pattern: {pattern_info.get('entity_type')}")
                
                candidate_entity_keys.append({
                    "column": col,
                    "confidence": round(key_confidence, 2),
                    "uniqueness_percentage": round(uniqueness_pct, 2),
                    "null_percentage": round(null_pct, 2),
                    "entity_type": pattern_info.get("entity_type"),
                    "reasoning": key_reasoning,
                    "sample_values": _get_sample_values(col_data, 5)
                })
            
            # Check for Foreign Key candidate (against reference tables if provided)
            if reference_tables:
                for ref_table, ref_columns in reference_tables.items():
                    for ref_col, ref_values in ref_columns.items():
                        overlap = _calculate_overlap(col_data, ref_values)
                        if overlap >= fk_overlap_threshold:
                            key_type = "foreign_key"
                            key_confidence = overlap
                            key_reasoning.append(f"High overlap ({overlap:.1f}%) with {ref_table}.{ref_col}")
                            
                            candidate_foreign_keys.append({
                                "column": col,
                                "confidence": round(key_confidence, 2),
                                "references": {
                                    "table": ref_table,
                                    "column": ref_col
                                },
                                "overlap_percentage": round(overlap, 2),
                                "reasoning": key_reasoning,
                                "sample_values": _get_sample_values(col_data, 5)
                            })
            
            # Also check for FK patterns without reference tables
            if not key_type and pattern_info.get("is_fk_pattern"):
                key_type = "potential_foreign_key"
                key_confidence = pattern_info.get("fk_pattern_score", 50.0)
                key_reasoning.append(f"Column name suggests foreign key reference")
                
                candidate_foreign_keys.append({
                    "column": col,
                    "confidence": round(key_confidence, 2),
                    "references": None,
                    "pattern_detected": pattern_info.get("fk_reference_hint"),
                    "reasoning": key_reasoning,
                    "sample_values": _get_sample_values(col_data, 5)
                })
            
            column_analysis.append({
                "column": col,
                "data_type": str(col_data.dtype),
                "null_count": int(null_count),
                "null_percentage": round(null_pct, 2),
                "unique_count": int(unique_count),
                "uniqueness_percentage": round(uniqueness_pct, 2),
                "key_score": round(key_score, 2),
                "key_type": key_type,
                "key_confidence": round(key_confidence, 2) if key_type else None,
                "pattern_info": pattern_info
            })
        
        # Analyze composite key candidates
        composite_key_candidates = []
        if analyze_composite_keys and len(candidate_primary_keys) == 0:
            composite_key_candidates = _analyze_composite_keys(
                df, 
                column_analysis, 
                max_composite_key_columns,
                pk_uniqueness_threshold
            )
        
        # Sort candidates by confidence
        candidate_primary_keys = sorted(candidate_primary_keys, key=lambda x: x["confidence"], reverse=True)
        candidate_foreign_keys = sorted(candidate_foreign_keys, key=lambda x: x["confidence"], reverse=True)
        candidate_entity_keys = sorted(candidate_entity_keys, key=lambda x: x["confidence"], reverse=True)
        composite_key_candidates = sorted(composite_key_candidates, key=lambda x: x["confidence"], reverse=True)
        
        # Calculate overall analysis score
        total_key_candidates = len(candidate_primary_keys) + len(candidate_entity_keys)
        has_pk = len(candidate_primary_keys) > 0 or len(composite_key_candidates) > 0
        
        if has_pk and total_key_candidates > 0:
            analysis_score = 100.0
            quality_status = "excellent"
        elif total_key_candidates > 0:
            analysis_score = 75.0
            quality_status = "good"
        else:
            analysis_score = 50.0
            quality_status = "needs_improvement"
        
        # Generate ROW-LEVEL-ISSUES
        row_level_issues = []
        
        # Check for duplicate values in PK candidates
        for pk_candidate in candidate_primary_keys[:3]:
            col = pk_candidate["column"]
            col_data = df[col]
            
            # Find duplicate values
            value_counts = col_data.value_counts(sort=True)
            duplicates = value_counts.filter(pl.col("count") > 1)
            
            if duplicates.height > 0:
                # Get rows with duplicate values
                dup_values = duplicates[col].to_list()[:10]  # Limit to 10 duplicate values
                
                for dup_val in dup_values:
                    if len(row_level_issues) >= 1000:
                        break
                    
                    dup_rows = df.with_row_index("row_index").filter(pl.col(col) == dup_val)
                    
                    for row in dup_rows.iter_rows(named=True):
                        if len(row_level_issues) >= 1000:
                            break
                        row_level_issues.append({
                            "row_index": int(row["row_index"]),
                            "column": col,
                            "issue_type": "duplicate_key_value",
                            "severity": "warning",
                            "message": f"Duplicate value '{dup_val}' in potential primary key column '{col}'",
                            "value": str(dup_val)
                        })
        
        # Check for null values in PK candidates
        for pk_candidate in candidate_primary_keys[:3]:
            col = pk_candidate["column"]
            
            null_rows = df.with_row_index("row_index").filter(pl.col(col).is_null())
            
            for row in null_rows.iter_rows(named=True):
                if len(row_level_issues) >= 1000:
                    break
                row_level_issues.append({
                    "row_index": int(row["row_index"]),
                    "column": col,
                    "issue_type": "null_key_value",
                    "severity": "critical",
                    "message": f"Null value in potential primary key column '{col}'",
                    "value": None
                })
        
        # Cap at 1000 issues
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
        
        # Build key analysis data
        key_analysis_data = {
            "analysis_score": round(analysis_score, 1),
            "quality_status": quality_status,
            "column_analysis": column_analysis,
            "candidate_primary_keys": candidate_primary_keys,
            "candidate_foreign_keys": candidate_foreign_keys,
            "candidate_entity_keys": candidate_entity_keys,
            "composite_key_candidates": composite_key_candidates,
            "summary": f"Key analysis completed. Found {len(candidate_primary_keys)} primary key candidates, "
                      f"{len(candidate_entity_keys)} entity key candidates, "
                      f"{len(candidate_foreign_keys)} foreign key candidates.",
            "row_level_issues": row_level_issues[:100],
            "issue_summary": issue_summary,
            "overrides": {
                "pk_uniqueness_threshold": pk_uniqueness_threshold,
                "pk_null_threshold": pk_null_threshold,
                "entity_key_uniqueness_min": entity_key_uniqueness_min,
                "entity_key_uniqueness_max": entity_key_uniqueness_max,
                "fk_overlap_threshold": fk_overlap_threshold,
                "analyze_composite_keys": analyze_composite_keys,
                "max_composite_key_columns": max_composite_key_columns
            }
        }
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        best_pk = candidate_primary_keys[0]["column"] if candidate_primary_keys else "None identified"
        best_pk_confidence = candidate_primary_keys[0]["confidence"] if candidate_primary_keys else 0
        
        executive_summary = [{
            "summary_id": "exec_key_identifier",
            "title": "Key Identification Status",
            "value": f"{analysis_score:.1f}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"Best PK Candidate: {best_pk} ({best_pk_confidence:.1f}% confidence), "
                          f"{len(candidate_primary_keys)} PK, {len(candidate_entity_keys)} Entity, "
                          f"{len(candidate_foreign_keys)} FK candidates"
        }]
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_parts = []
        ai_analysis_parts.append(f"KEY IDENTIFIER ANALYSIS:")
        ai_analysis_parts.append(f"- Analysis Score: {analysis_score:.1f}/100 ({quality_status})")
        ai_analysis_parts.append(f"- Primary Key Candidates: {len(candidate_primary_keys)}")
        
        if candidate_primary_keys:
            top_pk = candidate_primary_keys[0]
            ai_analysis_parts.append(f"  Best: '{top_pk['column']}' ({top_pk['confidence']:.1f}% confidence, {top_pk['uniqueness_percentage']:.1f}% unique)")
        
        ai_analysis_parts.append(f"- Entity Key Candidates: {len(candidate_entity_keys)}")
        if candidate_entity_keys:
            top_ek = candidate_entity_keys[0]
            ai_analysis_parts.append(f"  Best: '{top_ek['column']}' ({top_ek['confidence']:.1f}% confidence)")
        
        ai_analysis_parts.append(f"- Foreign Key Candidates: {len(candidate_foreign_keys)}")
        
        if composite_key_candidates:
            ai_analysis_parts.append(f"- Composite Key Options: {len(composite_key_candidates)}")
            top_ck = composite_key_candidates[0]
            ai_analysis_parts.append(f"  Best: {top_ck['columns']} ({top_ck['confidence']:.1f}% confidence)")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # No primary key found
        if len(candidate_primary_keys) == 0 and len(composite_key_candidates) == 0:
            alerts.append({
                "alert_id": "alert_keys_no_pk",
                "severity": "critical",
                "category": "key_integrity",
                "message": "No primary key candidate identified. Dataset lacks a unique record identifier.",
                "affected_fields_count": total_columns,
                "recommendation": "Consider adding a synthetic ID column or identifying composite key combinations."
            })
        
        # Multiple strong PK candidates
        strong_pks = [pk for pk in candidate_primary_keys if pk["confidence"] >= 90]
        if len(strong_pks) > 1:
            alerts.append({
                "alert_id": "alert_keys_multiple_pk",
                "severity": "medium",
                "category": "key_ambiguity",
                "message": f"Multiple strong primary key candidates ({len(strong_pks)}): {', '.join([pk['column'] for pk in strong_pks[:3]])}",
                "affected_fields_count": len(strong_pks),
                "recommendation": "Review business logic to determine the most appropriate primary key."
            })
        
        # PK with duplicates
        pks_with_dups = [pk for pk in candidate_primary_keys if pk["uniqueness_percentage"] < 100]
        if pks_with_dups:
            alerts.append({
                "alert_id": "alert_keys_pk_duplicates",
                "severity": "high",
                "category": "data_quality",
                "message": f"Primary key candidates have duplicate values: {', '.join([pk['column'] for pk in pks_with_dups[:3]])}",
                "affected_fields_count": len(pks_with_dups),
                "recommendation": "Resolve duplicate values before designating as primary key."
            })
        
        # Missing foreign key references
        unverified_fks = [fk for fk in candidate_foreign_keys if fk.get("references") is None]
        if unverified_fks:
            alerts.append({
                "alert_id": "alert_keys_unverified_fk",
                "severity": "medium",
                "category": "key_verification",
                "message": f"Potential foreign keys detected but not verified: {', '.join([fk['column'] for fk in unverified_fks[:3]])}",
                "affected_fields_count": len(unverified_fks),
                "recommendation": "Provide reference tables to verify foreign key relationships."
            })
        
        # Entity keys with high null percentage
        entity_keys_with_nulls = [ek for ek in candidate_entity_keys if ek["null_percentage"] > 10]
        if entity_keys_with_nulls:
            alerts.append({
                "alert_id": "alert_keys_entity_nulls",
                "severity": "high",
                "category": "data_completeness",
                "message": f"Entity key candidates have high null rates: {', '.join([ek['column'] for ek in entity_keys_with_nulls[:3]])}",
                "affected_fields_count": len(entity_keys_with_nulls),
                "recommendation": "Address null values in entity key columns for effective record matching."
            })
        
        # Quality score alert
        if analysis_score < good_threshold:
            alerts.append({
                "alert_id": "alert_keys_quality",
                "severity": "high" if analysis_score < 50 else "medium",
                "category": "quality_score",
                "message": f"Key identification quality score: {analysis_score:.1f}/100 ({quality_status})",
                "affected_fields_count": total_columns,
                "recommendation": "Review data structure and consider adding identifier columns."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Issues for PK candidates
        for pk in candidate_primary_keys:
            if pk["uniqueness_percentage"] < 100:
                issues.append({
                    "issue_id": f"issue_keys_pk_uniqueness_{pk['column']}",
                    "agent_id": "key-identifier",
                    "field_name": pk['column'],
                    "issue_type": "pk_not_fully_unique",
                    "severity": "high",
                    "message": f"Primary key candidate '{pk['column']}' has {100 - pk['uniqueness_percentage']:.2f}% duplicate values"
                })
            
            if pk["null_percentage"] > 0:
                issues.append({
                    "issue_id": f"issue_keys_pk_nulls_{pk['column']}",
                    "agent_id": "key-identifier",
                    "field_name": pk['column'],
                    "issue_type": "pk_has_nulls",
                    "severity": "critical",
                    "message": f"Primary key candidate '{pk['column']}' has {pk['null_percentage']:.2f}% null values"
                })
        
        # Issues for entity keys
        for ek in candidate_entity_keys:
            if ek["null_percentage"] > 20:
                issues.append({
                    "issue_id": f"issue_keys_ek_nulls_{ek['column']}",
                    "agent_id": "key-identifier",
                    "field_name": ek['column'],
                    "issue_type": "entity_key_high_nulls",
                    "severity": "medium",
                    "message": f"Entity key '{ek['column']}' has {ek['null_percentage']:.2f}% null values affecting matching capability"
                })
        
        # No key identified issue
        if not candidate_primary_keys and not composite_key_candidates:
            issues.append({
                "issue_id": "issue_keys_no_identifier",
                "agent_id": "key-identifier",
                "field_name": "dataset",
                "issue_type": "no_primary_key",
                "severity": "critical",
                "message": "No primary key or composite key identified. Records cannot be uniquely identified."
            })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        agent_recommendations = []
        
        # Recommendation 1: Best PK selection
        if candidate_primary_keys:
            best_pk = candidate_primary_keys[0]
            agent_recommendations.append({
                "recommendation_id": "rec_keys_primary_key",
                "agent_id": "key-identifier",
                "field_name": best_pk['column'],
                "priority": "critical",
                "recommendation": f"Designate '{best_pk['column']}' as primary key ({best_pk['confidence']:.1f}% confidence, {best_pk['uniqueness_percentage']:.1f}% unique)",
                "timeline": "immediate"
            })
        elif composite_key_candidates:
            best_ck = composite_key_candidates[0]
            agent_recommendations.append({
                "recommendation_id": "rec_keys_composite_key",
                "agent_id": "key-identifier",
                "field_name": ", ".join(best_ck['columns']),
                "priority": "critical",
                "recommendation": f"Use composite key {best_ck['columns']} as primary key ({best_ck['confidence']:.1f}% confidence)",
                "timeline": "immediate"
            })
        else:
            agent_recommendations.append({
                "recommendation_id": "rec_keys_add_id",
                "agent_id": "key-identifier",
                "field_name": "dataset",
                "priority": "critical",
                "recommendation": "Add synthetic ID column (auto-increment or UUID) as primary key",
                "timeline": "immediate"
            })
        
        # Recommendation 2: Entity key usage
        if candidate_entity_keys:
            agent_recommendations.append({
                "recommendation_id": "rec_keys_entity_matching",
                "agent_id": "key-identifier",
                "field_name": ", ".join([ek['column'] for ek in candidate_entity_keys[:3]]),
                "priority": "high",
                "recommendation": f"Use entity keys for record matching in EntityResolver: {', '.join([ek['column'] for ek in candidate_entity_keys[:3]])}",
                "timeline": "1 week"
            })
        
        # Recommendation 3: FK verification
        if unverified_fks:
            agent_recommendations.append({
                "recommendation_id": "rec_keys_verify_fk",
                "agent_id": "key-identifier",
                "field_name": ", ".join([fk['column'] for fk in unverified_fks[:3]]),
                "priority": "medium",
                "recommendation": "Verify foreign key relationships by providing reference table data",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 4: Data quality for keys
        if pks_with_dups or entity_keys_with_nulls:
            agent_recommendations.append({
                "recommendation_id": "rec_keys_data_quality",
                "agent_id": "key-identifier",
                "field_name": "key_columns",
                "priority": "high",
                "recommendation": "Run deduplication and null handling on key columns before key designation",
                "timeline": "1 week"
            })
        
        # Recommendation 5: Index creation
        if candidate_primary_keys or candidate_foreign_keys:
            agent_recommendations.append({
                "recommendation_id": "rec_keys_indexing",
                "agent_id": "key-identifier",
                "field_name": "all_key_columns",
                "priority": "medium",
                "recommendation": "Create database indexes on identified key columns for query performance",
                "timeline": "2 weeks"
            })
        
        # Recommendation 6: Documentation
        agent_recommendations.append({
            "recommendation_id": "rec_keys_documentation",
            "agent_id": "key-identifier",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Document key relationships and constraints for data governance",
            "timeline": "3 weeks"
        })

        return {
            "status": "success",
            "agent_id": "key-identifier",
            "agent_name": "Key Identifier",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_columns_analyzed": total_columns,
                "total_rows": total_rows,
                "primary_key_candidates": len(candidate_primary_keys),
                "foreign_key_candidates": len(candidate_foreign_keys),
                "entity_key_candidates": len(candidate_entity_keys),
                "composite_key_candidates": len(composite_key_candidates),
                "total_issues": len(row_level_issues)
            },
            "data": key_analysis_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "key-identifier",
            "agent_name": "Key Identifier",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _detect_key_patterns(column_name: str, col_data: pl.Series) -> Dict[str, Any]:
    """Detect patterns that indicate key columns."""
    col_lower = column_name.lower()
    result = {
        "is_id_pattern": False,
        "is_entity_pattern": False,
        "is_fk_pattern": False,
        "pattern_type": None,
        "entity_type": None,
        "fk_reference_hint": None,
        "id_pattern_score": 0,
        "entity_pattern_score": 0,
        "fk_pattern_score": 0
    }
    
    # ID pattern detection (column names)
    id_patterns = [
        (r'^id$', 100),
        (r'_id$', 95),
        (r'^.*_id$', 90),
        (r'^pk_', 100),
        (r'^primary_key', 100),
        (r'^record_id', 95),
        (r'^row_id', 90),
        (r'^uuid', 95),
        (r'^guid', 95),
        (r'^key$', 80),
        (r'^identifier', 85),
        (r'^code$', 70),
        (r'_code$', 65),
        (r'_number$', 60),
        (r'^serial', 80),
        (r'^index$', 70)
    ]
    
    for pattern, score in id_patterns:
        if re.search(pattern, col_lower):
            result["is_id_pattern"] = True
            result["pattern_type"] = pattern
            result["id_pattern_score"] = max(result["id_pattern_score"], score)
            break
    
    # Entity pattern detection
    entity_patterns = [
        (r'email', 'email', 90),
        (r'e_mail', 'email', 90),
        (r'phone', 'phone', 85),
        (r'mobile', 'phone', 85),
        (r'telephone', 'phone', 85),
        (r'ssn', 'ssn', 95),
        (r'social_security', 'ssn', 95),
        (r'tax_id', 'tax_id', 90),
        (r'ein', 'ein', 90),
        (r'license', 'license', 80),
        (r'passport', 'passport', 90),
        (r'customer_no', 'customer_number', 85),
        (r'account_no', 'account_number', 85),
        (r'employee_id', 'employee_id', 90),
        (r'member_id', 'member_id', 85),
        (r'user_id', 'user_id', 85),
        (r'username', 'username', 80)
    ]
    
    for pattern, entity_type, score in entity_patterns:
        if re.search(pattern, col_lower):
            result["is_entity_pattern"] = True
            result["entity_type"] = entity_type
            result["entity_pattern_score"] = max(result["entity_pattern_score"], score)
            break
    
    # FK pattern detection
    fk_patterns = [
        (r'^fk_', None, 100),
        (r'_fk$', None, 100),
        (r'^foreign_', None, 95),
        (r'_ref$', None, 80),
        (r'^ref_', None, 80),
        (r'customer_id', 'customers', 85),
        (r'user_id', 'users', 85),
        (r'product_id', 'products', 85),
        (r'order_id', 'orders', 85),
        (r'category_id', 'categories', 85),
        (r'department_id', 'departments', 85),
        (r'employee_id', 'employees', 85),
        (r'supplier_id', 'suppliers', 85),
        (r'vendor_id', 'vendors', 85),
        (r'parent_id', 'self', 85),
        (r'manager_id', 'employees', 80)
    ]
    
    for pattern, ref_hint, score in fk_patterns:
        if re.search(pattern, col_lower):
            result["is_fk_pattern"] = True
            result["fk_reference_hint"] = ref_hint
            result["fk_pattern_score"] = max(result["fk_pattern_score"], score)
            break
    
    # Value pattern detection (for string columns)
    if col_data.dtype == pl.Utf8:
        sample = col_data.drop_nulls().head(100)
        if sample.len() > 0:
            # Check for UUID pattern
            uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            uuid_matches = sample.str.contains(uuid_pattern, literal=False).sum()
            if uuid_matches / sample.len() > 0.8:
                result["is_id_pattern"] = True
                result["pattern_type"] = "UUID"
                result["id_pattern_score"] = max(result["id_pattern_score"], 95)
            
            # Check for email pattern
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            email_matches = sample.str.contains(email_pattern, literal=False).sum()
            if email_matches / sample.len() > 0.8:
                result["is_entity_pattern"] = True
                result["entity_type"] = "email"
                result["entity_pattern_score"] = max(result["entity_pattern_score"], 90)
    
    # Numeric sequential check (for integer columns)
    elif col_data.dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64]:
        non_null = col_data.drop_nulls()
        if non_null.len() > 10:
            # Check if values are sequential (auto-increment pattern)
            sorted_vals = non_null.sort()
            diffs = sorted_vals.diff().drop_nulls()
            if diffs.len() > 0:
                # Check if most differences are 1 (sequential)
                ones_count = (diffs == 1).sum()
                if ones_count / diffs.len() > 0.9:
                    result["is_id_pattern"] = True
                    result["pattern_type"] = "auto_increment"
                    result["id_pattern_score"] = max(result["id_pattern_score"], 90)
    
    return result


def _calculate_key_score(
    uniqueness_pct: float,
    null_pct: float,
    pattern_info: Dict[str, Any],
    weights: Dict[str, float]
) -> float:
    """Calculate overall key score for a column."""
    uniqueness_score = min(100, uniqueness_pct)
    null_score = 100 - null_pct
    pattern_score = max(
        pattern_info.get("id_pattern_score", 0),
        pattern_info.get("entity_pattern_score", 0),
        pattern_info.get("fk_pattern_score", 0)
    )
    
    overall_score = (
        uniqueness_score * weights.get("uniqueness_weight", 0.4) +
        null_score * weights.get("null_density_weight", 0.3) +
        pattern_score * weights.get("pattern_weight", 0.3)
    )
    
    return overall_score


def _get_sample_values(col_data: pl.Series, n: int = 5) -> List[str]:
    """Get sample values from a column."""
    sample = col_data.drop_nulls().unique().head(n)
    return [str(v) for v in sample.to_list()]


def _calculate_overlap(col_data: pl.Series, reference_values: List) -> float:
    """Calculate overlap percentage between column values and reference values."""
    col_values = set(col_data.drop_nulls().to_list())
    ref_values = set(reference_values)
    
    if len(col_values) == 0:
        return 0.0
    
    overlap = col_values.intersection(ref_values)
    return (len(overlap) / len(col_values)) * 100


def _analyze_composite_keys(
    df: pl.DataFrame,
    column_analysis: List[Dict[str, Any]],
    max_columns: int,
    uniqueness_threshold: float
) -> List[Dict[str, Any]]:
    """Analyze potential composite key combinations."""
    composite_candidates = []
    
    # Get columns sorted by key score (exclude already identified PKs)
    potential_cols = [
        ca for ca in column_analysis 
        if ca["key_type"] != "primary_key" and ca["key_score"] > 30
    ]
    potential_cols = sorted(potential_cols, key=lambda x: x["key_score"], reverse=True)
    
    # Take top columns for composite key analysis
    top_cols = [ca["column"] for ca in potential_cols[:min(len(potential_cols), max_columns * 2)]]
    
    if len(top_cols) < 2:
        return composite_candidates
    
    # Try 2-column combinations first
    from itertools import combinations
    
    total_rows = df.height
    
    for combo_size in range(2, min(len(top_cols), max_columns) + 1):
        for combo in combinations(top_cols, combo_size):
            # Calculate uniqueness of the combination
            combo_cols = list(combo)
            
            # Create composite key by concatenating columns
            try:
                composite_df = df.select(combo_cols)
                unique_combos = composite_df.unique().height
                null_combos = composite_df.filter(
                    pl.any_horizontal([pl.col(c).is_null() for c in combo_cols])
                ).height
                
                uniqueness_pct = (unique_combos / total_rows * 100) if total_rows > 0 else 0
                null_pct = (null_combos / total_rows * 100) if total_rows > 0 else 0
                
                if uniqueness_pct >= uniqueness_threshold and null_pct < 5:
                    confidence = uniqueness_pct * 0.6 + (100 - null_pct) * 0.4
                    
                    composite_candidates.append({
                        "columns": combo_cols,
                        "confidence": round(confidence, 2),
                        "uniqueness_percentage": round(uniqueness_pct, 2),
                        "null_percentage": round(null_pct, 2),
                        "reasoning": [
                            f"Combination of {len(combo_cols)} columns",
                            f"Combined uniqueness: {uniqueness_pct:.1f}%",
                            f"Null rate: {null_pct:.1f}%"
                        ]
                    })
            except Exception:
                continue
    
    return composite_candidates
