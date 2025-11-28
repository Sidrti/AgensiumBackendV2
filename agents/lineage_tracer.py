"""
Lineage Tracer Agent

Records each agent's execution step-by-step, creating a complete audit trail of:
- What agents ran and in what order
- Data transformations applied at each step
- Source tracking and dependency mapping

Key Responsibilities:
1. Track pipeline execution order
2. Record transformations and their sources
3. Build dependency graphs between data elements
4. Support data governance and compliance requirements

Input: CSV file (primary) + Optional agent execution context
Output: Lineage tracking results with execution trail, transformations, and source mappings
"""

import io
import re
import time
import base64
import hashlib
import polars as pl
from typing import Dict, Any, Optional, List
from datetime import datetime


def execute_lineage_tracer(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Trace data lineage and build execution audit trail.

    Args:
        file_contents: File bytes (read as binary)
        filename: Original filename (used to detect format)
        parameters: Agent parameters including execution context and lineage history

    Returns:
        Standardized output dictionary with lineage tracking results
    """

    start_time = time.time()
    parameters = parameters or {}

    # Extract parameters with defaults
    previous_lineage = parameters.get("previous_lineage", [])  # Lineage from prior agents
    source_system = parameters.get("source_system", "unknown")
    source_metadata = parameters.get("source_metadata", {})
    track_column_lineage = parameters.get("track_column_lineage", True)
    track_row_fingerprints = parameters.get("track_row_fingerprints", False)
    max_fingerprint_rows = parameters.get("max_fingerprint_rows", 1000)
    execution_context = parameters.get("execution_context", {})
    
    # Scoring thresholds
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file - CSV only
        if not filename.endswith('.csv'):
            return {
                "status": "error",
                "agent_id": "lineage-tracer",
                "error": f"Unsupported file format: {filename}. Only CSV files are supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        try:
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": "lineage-tracer",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.height == 0:
            return {
                "status": "error",
                "agent_id": "lineage-tracer",
                "agent_name": "Lineage Tracer",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        total_rows = df.height
        total_columns = len(df.columns)
        current_timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Generate dataset fingerprint
        dataset_fingerprint = _generate_dataset_fingerprint(df, filename)
        
        # ==================== BUILD LINEAGE ENTRY ====================
        current_lineage_entry = {
            "step_id": f"lineage_{int(time.time() * 1000)}",
            "agent_id": "lineage-tracer",
            "agent_name": "Lineage Tracer",
            "timestamp": current_timestamp,
            "source": {
                "filename": filename,
                "system": source_system,
                "metadata": source_metadata,
                "fingerprint": dataset_fingerprint
            },
            "dataset_stats": {
                "rows": total_rows,
                "columns": total_columns,
                "column_names": df.columns,
                "schema": {col: str(df[col].dtype) for col in df.columns}
            },
            "execution_context": execution_context,
            "transformations_detected": []
        }
        
        # ==================== COLUMN LINEAGE TRACKING ====================
        column_lineage = []
        
        if track_column_lineage:
            for col in df.columns:
                col_stats = _analyze_column_for_lineage(df[col], col)
                column_lineage.append({
                    "column_name": col,
                    "data_type": str(df[col].dtype),
                    "source_column": col,  # Same as current unless transformed
                    "source_system": source_system,
                    "transformation_history": [],
                    "statistics": col_stats,
                    "fingerprint": _generate_column_fingerprint(df[col])
                })
        
        # ==================== ROW FINGERPRINTING ====================
        row_fingerprints = []
        
        if track_row_fingerprints:
            sample_size = min(total_rows, max_fingerprint_rows)
            sample_df = df.head(sample_size)
            
            for i in range(sample_df.height):
                row = sample_df.row(i)
                row_str = "|".join(str(v) if v is not None else "" for v in row)
                fingerprint = hashlib.md5(row_str.encode()).hexdigest()[:16]
                row_fingerprints.append({
                    "row_index": i,
                    "fingerprint": fingerprint
                })
        
        # ==================== DETECT TRANSFORMATIONS ====================
        # Compare with previous lineage if available
        detected_transformations = []
        
        if previous_lineage:
            prev_entry = previous_lineage[-1] if previous_lineage else None
            if prev_entry:
                # Detect column additions/removals
                prev_columns = set(prev_entry.get("dataset_stats", {}).get("column_names", []))
                curr_columns = set(df.columns)
                
                added_columns = curr_columns - prev_columns
                removed_columns = prev_columns - curr_columns
                
                for col in added_columns:
                    detected_transformations.append({
                        "type": "column_added",
                        "column": col,
                        "description": f"Column '{col}' was added"
                    })
                
                for col in removed_columns:
                    detected_transformations.append({
                        "type": "column_removed",
                        "column": col,
                        "description": f"Column '{col}' was removed"
                    })
                
                # Detect row count changes
                prev_rows = prev_entry.get("dataset_stats", {}).get("rows", 0)
                if prev_rows != total_rows:
                    detected_transformations.append({
                        "type": "row_count_changed",
                        "previous_count": prev_rows,
                        "current_count": total_rows,
                        "difference": total_rows - prev_rows,
                        "description": f"Row count changed from {prev_rows} to {total_rows}"
                    })
                
                # Detect schema changes
                prev_schema = prev_entry.get("dataset_stats", {}).get("schema", {})
                curr_schema = {col: str(df[col].dtype) for col in df.columns}
                
                for col in curr_columns.intersection(prev_columns):
                    if col in prev_schema and prev_schema.get(col) != curr_schema.get(col):
                        detected_transformations.append({
                            "type": "type_changed",
                            "column": col,
                            "previous_type": prev_schema.get(col),
                            "current_type": curr_schema.get(col),
                            "description": f"Column '{col}' type changed from {prev_schema.get(col)} to {curr_schema.get(col)}"
                        })
        
        current_lineage_entry["transformations_detected"] = detected_transformations
        
        # ==================== BUILD COMPLETE LINEAGE ====================
        complete_lineage = list(previous_lineage) + [current_lineage_entry]
        
        # Calculate lineage depth and statistics
        lineage_depth = len(complete_lineage)
        sources_identified = len(set(
            entry.get("source", {}).get("system", "unknown") 
            for entry in complete_lineage
        ))
        transformations_tracked = sum(
            len(entry.get("transformations_detected", [])) 
            for entry in complete_lineage
        )
        
        # ==================== CALCULATE QUALITY SCORE ====================
        # Score based on lineage completeness and tracking
        lineage_completeness = 100 if source_system != "unknown" else 70
        column_coverage = 100 if track_column_lineage else 50
        transformation_tracking = 100 if detected_transformations or not previous_lineage else 80
        
        overall_score = (lineage_completeness * 0.4 + column_coverage * 0.3 + transformation_tracking * 0.3)
        
        if overall_score >= excellent_threshold:
            quality_status = "excellent"
        elif overall_score >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"
        
        # ==================== BUILD ROW-LEVEL ISSUES ====================
        row_level_issues = []
        
        # Flag any columns without clear source
        if source_system == "unknown":
            for col in df.columns:
                row_level_issues.append({
                    "row_index": -1,
                    "column": col,
                    "issue_type": "unknown_source",
                    "severity": "info",
                    "original_value": None,
                    "message": f"Column '{col}' source system is unknown"
                })
        
        # Cap row-level issues
        row_level_issues = row_level_issues[:1000]
        
        # Calculate issue summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {},
            "affected_rows": 0,
            "affected_columns": sorted(list(set(issue["column"] for issue in row_level_issues)))
        }
        
        for issue in row_level_issues:
            issue_type = issue.get("issue_type", "unknown")
            issue_summary["by_type"][issue_type] = issue_summary["by_type"].get(issue_type, 0) + 1
            severity = issue.get("severity", "info")
            issue_summary["by_severity"][severity] = issue_summary["by_severity"].get(severity, 0) + 1
        
        # ==================== BUILD LINEAGE DATA ====================
        lineage_data = {
            "lineage_score": round(overall_score, 1),
            "quality_status": quality_status,
            "current_entry": current_lineage_entry,
            "complete_lineage": complete_lineage,
            "column_lineage": column_lineage,
            "row_fingerprints": row_fingerprints[:100],  # Limit for response size
            "detected_transformations": detected_transformations,
            "statistics": {
                "lineage_depth": lineage_depth,
                "sources_identified": sources_identified,
                "transformations_tracked": transformations_tracked,
                "columns_tracked": len(column_lineage),
                "rows_fingerprinted": len(row_fingerprints)
            },
            "summary": f"Lineage tracking completed. Depth: {lineage_depth} steps, "
                      f"{sources_identified} source(s) identified, "
                      f"{transformations_tracked} transformation(s) tracked.",
            "row_level_issues": row_level_issues[:100],
            "issue_summary": issue_summary,
            "overrides": {
                "source_system": source_system,
                "track_column_lineage": track_column_lineage,
                "track_row_fingerprints": track_row_fingerprints
            }
        }
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = [{
            "summary_id": "exec_lineage_tracer",
            "title": "Data Lineage Status",
            "value": f"{overall_score:.1f}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"Lineage Depth: {lineage_depth}, Sources: {sources_identified}, "
                          f"Transformations Tracked: {transformations_tracked}"
        }]
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_parts = []
        ai_analysis_parts.append(f"LINEAGE TRACER ANALYSIS:")
        ai_analysis_parts.append(f"- Lineage Score: {overall_score:.1f}/100 ({quality_status})")
        ai_analysis_parts.append(f"- Pipeline Depth: {lineage_depth} step(s)")
        ai_analysis_parts.append(f"- Sources Identified: {sources_identified}")
        ai_analysis_parts.append(f"- Transformations Tracked: {transformations_tracked}")
        ai_analysis_parts.append(f"- Columns Tracked: {len(column_lineage)}")
        
        if detected_transformations:
            ai_analysis_parts.append(f"- Recent Transformations:")
            for trans in detected_transformations[:3]:
                ai_analysis_parts.append(f"  • {trans['description']}")
        
        if source_system == "unknown":
            ai_analysis_parts.append(f"- WARNING: Source system not specified")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # Alert: Unknown source
        if source_system == "unknown":
            alerts.append({
                "alert_id": "alert_lineage_unknown_source",
                "severity": "medium",
                "category": "lineage_tracking",
                "message": "Data source system is not specified - lineage may be incomplete",
                "affected_fields_count": total_columns,
                "recommendation": "Specify source_system parameter for complete lineage tracking."
            })
        
        # Alert: Large transformation detected
        if any(t["type"] == "row_count_changed" and abs(t.get("difference", 0)) > total_rows * 0.2 for t in detected_transformations):
            alerts.append({
                "alert_id": "alert_lineage_large_change",
                "severity": "high",
                "category": "data_integrity",
                "message": "Significant row count change detected (>20%)",
                "affected_fields_count": 1,
                "recommendation": "Review transformation that caused large data change."
            })
        
        # Alert: Schema changes
        schema_changes = [t for t in detected_transformations if t["type"] == "type_changed"]
        if schema_changes:
            alerts.append({
                "alert_id": "alert_lineage_schema_change",
                "severity": "medium",
                "category": "schema_evolution",
                "message": f"{len(schema_changes)} column type change(s) detected",
                "affected_fields_count": len(schema_changes),
                "recommendation": "Verify type changes are intentional and downstream compatible."
            })
        
        # Alert: First lineage entry
        if lineage_depth == 1:
            alerts.append({
                "alert_id": "alert_lineage_first_entry",
                "severity": "info",
                "category": "lineage_tracking",
                "message": "This is the first lineage entry - no previous history available",
                "affected_fields_count": 0,
                "recommendation": "Future processing will build upon this baseline."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        if source_system == "unknown":
            issues.append({
                "issue_id": "issue_lineage_source",
                "agent_id": "lineage-tracer",
                "field_name": "source_system",
                "issue_type": "missing_metadata",
                "severity": "warning",
                "message": "Source system not specified for lineage tracking"
            })
        
        for trans in detected_transformations:
            if trans["type"] in ["column_removed", "type_changed"]:
                issues.append({
                    "issue_id": f"issue_lineage_{trans['type']}_{trans.get('column', 'unknown')}",
                    "agent_id": "lineage-tracer",
                    "field_name": trans.get("column", "dataset"),
                    "issue_type": trans["type"],
                    "severity": "info",
                    "message": trans["description"]
                })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        agent_recommendations = []
        
        # Recommendation 1: Specify source
        if source_system == "unknown":
            agent_recommendations.append({
                "recommendation_id": "rec_lineage_source",
                "agent_id": "lineage-tracer",
                "field_name": "source_system",
                "priority": "high",
                "recommendation": "Specify source_system parameter for complete lineage tracking",
                "timeline": "immediate"
            })
        
        # Recommendation 2: Enable row fingerprinting for critical data
        if not track_row_fingerprints:
            agent_recommendations.append({
                "recommendation_id": "rec_lineage_fingerprints",
                "agent_id": "lineage-tracer",
                "field_name": "all",
                "priority": "medium",
                "recommendation": "Enable row fingerprinting for audit trail of individual records",
                "timeline": "1 week"
            })
        
        # Recommendation 3: Review schema changes
        if schema_changes:
            agent_recommendations.append({
                "recommendation_id": "rec_lineage_schema",
                "agent_id": "lineage-tracer",
                "field_name": ", ".join([t["column"] for t in schema_changes[:3]]),
                "priority": "medium",
                "recommendation": f"Review {len(schema_changes)} schema change(s) for downstream compatibility",
                "timeline": "1 week"
            })
        
        # Recommendation 4: Document lineage
        agent_recommendations.append({
            "recommendation_id": "rec_lineage_documentation",
            "agent_id": "lineage-tracer",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Export and document lineage for compliance and governance",
            "timeline": "2 weeks"
        })
        
        # Recommendation 5: Automate lineage capture
        agent_recommendations.append({
            "recommendation_id": "rec_lineage_automation",
            "agent_id": "lineage-tracer",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Integrate lineage tracking into automated data pipelines",
            "timeline": "1 month"
        })

        return {
            "status": "success",
            "agent_id": "lineage-tracer",
            "agent_name": "Lineage Tracer",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows": total_rows,
                "total_columns": total_columns,
                "lineage_depth": lineage_depth,
                "sources_identified": sources_identified,
                "transformations_tracked": transformations_tracked,
                "columns_tracked": len(column_lineage),
                "rows_fingerprinted": len(row_fingerprints),
                "total_issues": len(row_level_issues)
            },
            "data": lineage_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary,
            "lineage": complete_lineage  # Export for downstream agents
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "lineage-tracer",
            "agent_name": "Lineage Tracer",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _generate_dataset_fingerprint(df: pl.DataFrame, filename: str) -> str:
    """Generate a unique fingerprint for the dataset."""
    fingerprint_data = f"{filename}|{df.height}|{len(df.columns)}|{','.join(df.columns)}"
    
    # Add sample data for more unique fingerprint
    if df.height > 0:
        first_row = df.row(0)
        last_row = df.row(-1)
        fingerprint_data += f"|{first_row}|{last_row}"
    
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]


def _generate_column_fingerprint(col_data: pl.Series) -> str:
    """Generate a fingerprint for a column based on its values."""
    stats_str = f"{col_data.dtype}|{col_data.len()}|{col_data.null_count()}|{col_data.n_unique()}"
    
    # Add sample values
    sample = col_data.drop_nulls().head(5).to_list()
    stats_str += f"|{sample}"
    
    return hashlib.md5(stats_str.encode()).hexdigest()[:16]


def _analyze_column_for_lineage(col_data: pl.Series, col_name: str) -> Dict[str, Any]:
    """Analyze a column for lineage tracking statistics."""
    return {
        "null_count": col_data.null_count(),
        "null_percentage": round(col_data.null_count() / col_data.len() * 100, 2) if col_data.len() > 0 else 0,
        "unique_count": col_data.n_unique(),
        "unique_percentage": round(col_data.n_unique() / col_data.len() * 100, 2) if col_data.len() > 0 else 0,
        "sample_values": [str(v) for v in col_data.drop_nulls().head(3).to_list()]
    }
