"""
Master Writeback Agent

Creates the final output file after applying all agents' results. This agent
consolidates all transformations, resolutions, and quality improvements from
the Master My Data pipeline into a single authoritative output.

Key Responsibilities:
1. Aggregate results from all pipeline agents
2. Apply final data transformations
3. Generate versioned output with audit metadata
4. Create summary statistics and quality metrics
5. Produce the final mastered dataset

Input: CSV file with agent processing metadata
Output: Final mastered CSV file with complete audit trail
"""

import io
import re
import time
import base64
import hashlib
import polars as pl
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import defaultdict


def execute_master_writeback_agent(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create the final mastered output file consolidating all agent results.

    Args:
        file_contents: File bytes (read as binary)
        filename: Original filename
        parameters: Agent parameters including output configuration

    Returns:
        Standardized output dictionary with final mastered file
    """

    start_time = time.time()
    parameters = parameters or {}

    # Extract parameters with defaults
    include_metadata_columns = parameters.get("include_metadata_columns", True)
    include_audit_trail = parameters.get("include_audit_trail", True)
    output_format = parameters.get("output_format", "csv")
    version_suffix = parameters.get("version_suffix", datetime.utcnow().strftime("%Y%m%d_%H%M%S"))
    drop_internal_columns = parameters.get("drop_internal_columns", True)
    
    # Agent results from pipeline
    pipeline_results = parameters.get("pipeline_results", {})
    lineage_data = parameters.get("lineage_data", [])
    
    # Quality thresholds
    min_quality_score = parameters.get("min_quality_score", 0.0)
    exclude_flagged_records = parameters.get("exclude_flagged_records", False)
    flagged_record_ids = parameters.get("flagged_record_ids", [])
    
    # Scoring thresholds
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file - CSV only
        if not filename.endswith('.csv'):
            return {
                "status": "error",
                "agent_id": "master-writeback-agent",
                "error": f"Unsupported file format: {filename}. Only CSV files are supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        try:
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": "master-writeback-agent",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.height == 0:
            return {
                "status": "error",
                "agent_id": "master-writeback-agent",
                "agent_name": "Master Writeback Agent",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        original_df = df.clone()
        original_row_count = df.height
        original_column_count = len(df.columns)
        
        # ==================== PROCESS DATA ====================
        
        # Track processing statistics
        records_processed = 0
        records_excluded = 0
        records_written = 0
        transformations_applied = 0
        columns_added = 0
        columns_removed = 0
        row_level_issues = []
        
        # Identify internal/metadata columns
        internal_columns = [col for col in df.columns if col.startswith("__")]
        
        # Filter out flagged records if requested
        if exclude_flagged_records and flagged_record_ids:
            # Look for ID columns to match against
            id_columns = [col for col in df.columns if 'id' in col.lower()]
            
            if id_columns:
                for id_col in id_columns:
                    mask = ~df[id_col].is_in(flagged_record_ids)
                    excluded_count = df.height - mask.sum()
                    if excluded_count > 0:
                        df = df.filter(mask)
                        records_excluded += excluded_count
                        break
        
        # Filter by quality score if applicable
        quality_columns = [col for col in df.columns if 'score' in col.lower() or 'confidence' in col.lower() or 'trust' in col.lower()]
        
        for qc in quality_columns:
            try:
                if df[qc].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]:
                    low_quality_mask = df[qc] < min_quality_score
                    excluded = low_quality_mask.sum()
                    if excluded > 0 and min_quality_score > 0:
                        df = df.filter(~low_quality_mask)
                        records_excluded += excluded
                        
                        row_level_issues.append({
                            "row_index": 0,
                            "column": qc,
                            "issue_type": "quality_threshold",
                            "severity": "info",
                            "original_value": min_quality_score,
                            "message": f"{excluded} records excluded due to low {qc}"
                        })
            except Exception:
                pass
        
        # ==================== ADD METADATA COLUMNS ====================
        
        metadata_additions = []
        
        if include_metadata_columns:
            # Add processing timestamp
            df = df.with_columns([
                pl.lit(datetime.utcnow().isoformat() + "Z").alias("__mastered_at__")
            ])
            columns_added += 1
            metadata_additions.append("__mastered_at__")
            
            # Add version
            df = df.with_columns([
                pl.lit(version_suffix).alias("__version__")
            ])
            columns_added += 1
            metadata_additions.append("__version__")
            
            # Add row checksum for data integrity
            checksums = []
            for i in range(df.height):
                row_data = str(df.row(i))
                checksum = hashlib.md5(row_data.encode()).hexdigest()[:16]
                checksums.append(checksum)
            
            df = df.with_columns([
                pl.Series("__row_checksum__", checksums)
            ])
            columns_added += 1
            metadata_additions.append("__row_checksum__")
            
            # Add master record ID
            master_ids = [f"MR_{version_suffix}_{i+1:06d}" for i in range(df.height)]
            df = df.with_columns([
                pl.Series("__master_record_id__", master_ids)
            ])
            columns_added += 1
            metadata_additions.append("__master_record_id__")
        
        # ==================== BUILD AUDIT TRAIL ====================
        
        audit_trail = []
        
        if include_audit_trail:
            # Record this writeback step
            audit_entry = {
                "step": len(lineage_data) + 1,
                "agent_id": "master-writeback-agent",
                "agent_name": "Master Writeback Agent",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "final_writeback",
                "input_records": original_row_count,
                "output_records": df.height,
                "records_excluded": records_excluded,
                "columns_added": columns_added,
                "columns_removed": columns_removed,
                "version": version_suffix
            }
            audit_trail.append(audit_entry)
            
            # Include previous lineage
            for entry in lineage_data:
                if isinstance(entry, dict):
                    audit_trail.insert(0, entry)
        
        # ==================== PREPARE FINAL OUTPUT ====================
        
        final_df = df.clone()
        
        # Optionally drop internal columns for clean output
        clean_df = df.clone()
        if drop_internal_columns:
            cols_to_drop = [col for col in clean_df.columns if col.startswith("__")]
            if cols_to_drop:
                clean_df = clean_df.drop(cols_to_drop)
                columns_removed = len(cols_to_drop)
        
        records_written = clean_df.height
        records_processed = original_row_count
        
        # ==================== CALCULATE STATISTICS ====================
        
        # Data completeness
        completeness_scores = []
        for col in clean_df.columns:
            non_null = clean_df[col].drop_nulls().len()
            completeness = non_null / clean_df.height if clean_df.height > 0 else 0
            completeness_scores.append(completeness)
        
        avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 1.0
        
        # Calculate bytes
        output_bytes = _generate_mastered_file(clean_df, filename)
        bytes_written = len(output_bytes)
        
        # Calculate overall score
        write_success_rate = (records_written / max(records_processed, 1)) * 100
        data_integrity_score = avg_completeness * 100
        
        overall_score = (write_success_rate * 0.4) + (data_integrity_score * 0.4) + (100 if records_excluded == 0 else max(0, 100 - records_excluded) * 0.2)
        
        if overall_score >= excellent_threshold:
            quality_status = "excellent"
        elif overall_score >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"
        
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
        
        writeback_data = {
            "writeback_score": round(overall_score, 1),
            "quality_status": quality_status,
            "output_summary": {
                "original_records": original_row_count,
                "records_processed": records_processed,
                "records_excluded": records_excluded,
                "records_written": records_written,
                "original_columns": original_column_count,
                "final_columns": len(clean_df.columns),
                "columns_added": columns_added,
                "columns_removed": columns_removed,
                "bytes_written": bytes_written,
                "output_format": output_format
            },
            "data_quality": {
                "average_completeness": round(avg_completeness * 100, 1),
                "write_success_rate": round(write_success_rate, 1),
                "data_integrity_score": round(data_integrity_score, 1)
            },
            "versioning": {
                "version": version_suffix,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "include_metadata": include_metadata_columns,
                "metadata_columns_added": metadata_additions
            },
            "audit_trail": audit_trail,
            "column_summary": {
                "final_columns": clean_df.columns,
                "metadata_columns": metadata_additions if include_metadata_columns else [],
                "dropped_internal_columns": internal_columns if drop_internal_columns else []
            },
            "summary": f"Master writeback completed. Wrote {records_written} records ({bytes_written:,} bytes) "
                      f"to mastered output. Excluded {records_excluded} records. "
                      f"Data integrity: {data_integrity_score:.1f}%.",
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary,
            "overrides": {
                "include_metadata_columns": include_metadata_columns,
                "include_audit_trail": include_audit_trail,
                "drop_internal_columns": drop_internal_columns,
                "min_quality_score": min_quality_score,
                "exclude_flagged_records": exclude_flagged_records
            }
        }
        
        # ==================== EXECUTIVE SUMMARY ====================
        
        executive_summary = [{
            "summary_id": "exec_master_writeback",
            "title": "Master Writeback Status",
            "value": f"{records_written:,}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"Wrote {records_written:,} records ({bytes_written:,} bytes), "
                          f"Excluded: {records_excluded}, Integrity: {data_integrity_score:.1f}%"
        }]
        
        # ==================== AI ANALYSIS TEXT ====================
        
        ai_analysis_parts = [
            "MASTER WRITEBACK AGENT ANALYSIS:",
            f"- Writeback Score: {overall_score:.1f}/100 ({quality_status})",
            f"- Records Written: {records_written:,}",
            f"- Records Excluded: {records_excluded}",
            f"- Bytes Written: {bytes_written:,}",
            f"- Data Integrity: {data_integrity_score:.1f}%",
            f"- Write Success Rate: {write_success_rate:.1f}%",
            f"- Version: {version_suffix}"
        ]
        
        if metadata_additions:
            ai_analysis_parts.append(f"- Metadata Columns Added: {', '.join(metadata_additions)}")
        
        if internal_columns and drop_internal_columns:
            ai_analysis_parts.append(f"- Internal Columns Removed: {len(internal_columns)}")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # ==================== ALERTS ====================
        
        alerts = []
        
        if records_excluded > 0:
            severity = "high" if records_excluded > original_row_count * 0.1 else "medium"
            alerts.append({
                "alert_id": "alert_writeback_excluded",
                "severity": severity,
                "category": "data_loss",
                "message": f"{records_excluded} record(s) excluded from final output",
                "affected_fields_count": records_excluded,
                "recommendation": "Review exclusion criteria and flagged records."
            })
        
        if avg_completeness < 0.9:
            alerts.append({
                "alert_id": "alert_writeback_completeness",
                "severity": "medium",
                "category": "data_quality",
                "message": f"Data completeness is {avg_completeness*100:.1f}% (below 90%)",
                "affected_fields_count": len([s for s in completeness_scores if s < 0.9]),
                "recommendation": "Investigate missing data and improve data collection."
            })
        
        if write_success_rate < 100:
            alerts.append({
                "alert_id": "alert_writeback_success_rate",
                "severity": "medium",
                "category": "processing",
                "message": f"Write success rate is {write_success_rate:.1f}%",
                "affected_fields_count": original_row_count - records_written,
                "recommendation": "Review processing pipeline for data loss issues."
            })
        
        if overall_score < good_threshold:
            alerts.append({
                "alert_id": "alert_writeback_quality",
                "severity": "high",
                "category": "overall_quality",
                "message": f"Writeback quality score ({overall_score:.1f}%) below threshold",
                "affected_fields_count": records_written,
                "recommendation": "Review data quality issues before publishing."
            })
        
        # ==================== ISSUES ====================
        
        issues = []
        
        # Low completeness columns
        for i, col in enumerate(clean_df.columns):
            if completeness_scores[i] < 0.5:
                issues.append({
                    "issue_id": f"issue_writeback_completeness_{col}",
                    "agent_id": "master-writeback-agent",
                    "field_name": col,
                    "issue_type": "low_completeness",
                    "severity": "warning",
                    "message": f"Column '{col}' has only {completeness_scores[i]*100:.1f}% completeness"
                })
        
        issues = issues[:30]  # Limit
        
        # ==================== RECOMMENDATIONS ====================
        
        agent_recommendations = []
        
        if records_excluded > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_writeback_review_excluded",
                "agent_id": "master-writeback-agent",
                "field_name": "all",
                "priority": "high",
                "recommendation": f"Review {records_excluded} excluded records and determine if corrections are needed",
                "timeline": "1 week"
            })
        
        agent_recommendations.append({
            "recommendation_id": "rec_writeback_backup",
            "agent_id": "master-writeback-agent",
            "field_name": "all",
            "priority": "high",
            "recommendation": "Create backup of original data before publishing mastered version",
            "timeline": "immediate"
        })
        
        if not include_audit_trail:
            agent_recommendations.append({
                "recommendation_id": "rec_writeback_audit",
                "agent_id": "master-writeback-agent",
                "field_name": "audit_trail",
                "priority": "medium",
                "recommendation": "Enable audit trail for compliance and traceability",
                "timeline": "1 week"
            })
        
        low_completeness_cols = [col for i, col in enumerate(clean_df.columns) if completeness_scores[i] < 0.7]
        if low_completeness_cols:
            agent_recommendations.append({
                "recommendation_id": "rec_writeback_completeness",
                "agent_id": "master-writeback-agent",
                "field_name": ", ".join(low_completeness_cols[:5]),
                "priority": "medium",
                "recommendation": f"Address low completeness in columns: {', '.join(low_completeness_cols[:5])}",
                "timeline": "2 weeks"
            })
        
        agent_recommendations.append({
            "recommendation_id": "rec_writeback_catalog",
            "agent_id": "master-writeback-agent",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Publish mastered dataset to data catalog with documentation",
            "timeline": "3 weeks"
        })
        
        agent_recommendations.append({
            "recommendation_id": "rec_writeback_monitoring",
            "agent_id": "master-writeback-agent",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Set up monitoring for data quality metrics on mastered data",
            "timeline": "1 month"
        })

        # Generate final output file
        mastered_file_bytes = _generate_mastered_file(clean_df, filename)
        mastered_file_base64 = base64.b64encode(mastered_file_bytes).decode('utf-8')

        return {
            "status": "success",
            "agent_id": "master-writeback-agent",
            "agent_name": "Master Writeback Agent",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "records_processed": records_processed,
                "records_written": records_written,
                "records_excluded": records_excluded,
                "bytes_written": bytes_written,
                "columns_final": len(clean_df.columns),
                "data_integrity_score": round(data_integrity_score, 1),
                "write_success_rate": round(write_success_rate, 1),
                "total_issues": len(row_level_issues)
            },
            "data": writeback_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary,
            "cleaned_file": {
                # "filename": f"mastered_{version_suffix}_{filename}",
                "filename": f"mastered_{filename}",
                "content": mastered_file_base64,
                "size_bytes": len(mastered_file_bytes),
                "format": filename.split('.')[-1].lower()
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "master-writeback-agent",
            "agent_name": "Master Writeback Agent",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _generate_mastered_file(df: pl.DataFrame, original_filename: str) -> bytes:
    """Generate the final mastered file in CSV format."""
    output = io.BytesIO()
    df.write_csv(output)
    return output.getvalue()
