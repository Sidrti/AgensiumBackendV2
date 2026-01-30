"""
Quarantine Agent

Identifies, isolates, and manages bad, invalid, or suspicious data to prevent corruption
of the main processing pipeline.

Key Features:
1. Detects Invalid/Corrupted Data
   - Missing required fields
   - Incorrect data types
   - Out-of-range numeric values
   - Invalid boolean formats (e.g., yes/no → true/false)
   - Broken or duplicate records
   - Schema mismatches
   - Inconsistent date formats

2. Removes Faulty Records from Main Pipeline
   - Extracts problematic records
   - Redirects to quarantine area
   - Maintains clean data flow

3. Stores in Quarantine Zone
   - Raw invalid record
   - Error/issue that caused quarantine
   - Timestamp
   - Optional metadata (file name, batch ID, etc.)

4. Generates Logs and Reports
   - Comprehensive quarantine logs
   - Statistics on quarantined data
   - Quality metrics and impact analysis
"""

import polars as pl
import numpy as np
import io
import time
import base64
import json
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import re
from agents.agent_utils import safe_get_list, safe_get_dict

def execute_quarantine_agent(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute quarantine agent to identify and isolate invalid data.

    Args:
        file_contents: File bytes (read as binary)
        filename: Original filename (used to detect format)
        parameters: Agent parameters from tool.json

    Returns:
        Standardized output dictionary
    """

    start_time = time.time()
    parameters = parameters or {}

    # Extract and parse parameters with defaults
    required_fields = safe_get_list(parameters, "required_fields", [])
    range_constraints = safe_get_dict(parameters, "range_constraints", {})
    format_constraints = safe_get_dict(parameters, "format_constraints", {})
    expected_schema = safe_get_dict(parameters, "expected_schema", {})
    detect_missing_fields = parameters.get("detect_missing_fields", True)
    detect_type_mismatches = parameters.get("detect_type_mismatches", True)
    detect_out_of_range = parameters.get("detect_out_of_range", True)
    detect_invalid_formats = parameters.get("detect_invalid_formats", True)
    detect_broken_records = parameters.get("detect_broken_records", True)
    detect_schema_mismatches = parameters.get("detect_schema_mismatches", True)
    quarantine_reduction_weight = parameters.get("quarantine_reduction_weight", 0.5)
    data_integrity_weight = parameters.get("data_integrity_weight", 0.3)
    processing_efficiency_weight = parameters.get("processing_efficiency_weight", 0.2)
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file based on format - CSV ONLY
        if not filename.endswith('.csv'):
             return {
                "status": "error",
                "agent_id": "quarantine-agent",
                "error": f"Unsupported file format: {filename}. Only CSV is supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        try:
            # Read as String to capture all values for validation
            # infer_schema_length=0 forces all columns to be read as String (Utf8)
            df = pl.read_csv(io.BytesIO(file_contents), infer_schema_length=0, ignore_errors=True)
        except Exception as e:
             return {
                "status": "error",
                "agent_id": "quarantine-agent",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.height == 0:
            return {
                "status": "error",
                "agent_id": "quarantine-agent",
                "agent_name": "Quarantine Agent",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Add row index
        df = df.with_row_index("row_index")
        original_df = df.clone()

        quarantined_data, quarantine_log, quarantine_analysis = _analyze_and_quarantine(
            df,
            required_fields,
            range_constraints,
            format_constraints,
            expected_schema,
            {
                "detect_missing_fields": detect_missing_fields,
                "detect_type_mismatches": detect_type_mismatches,
                "detect_out_of_range": detect_out_of_range,
                "detect_invalid_formats": detect_invalid_formats,
                "detect_broken_records": detect_broken_records,
                "detect_schema_mismatches": detect_schema_mismatches
            }
        )

        # Remove quarantined records from main data
        quarantined_indices = set(quarantined_data["row_index"].to_list())
        df_clean = df.filter(~pl.col("row_index").is_in(quarantined_indices))

        # Calculate quality scores
        quality_score = _calculate_quarantine_score(
            original_df, df_clean, quarantined_data, quarantine_analysis, {
                "quarantine_reduction_weight": quarantine_reduction_weight,
                "data_integrity_weight": data_integrity_weight,
                "processing_efficiency_weight": processing_efficiency_weight,
                "excellent_threshold": excellent_threshold,
                "good_threshold": good_threshold
            }
        )

        # Determine quality status
        if quality_score["overall_score"] >= excellent_threshold:
            quality_status = "excellent"
        elif quality_score["overall_score"] >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"

        # Generate cleaned file (CSV format)
        # Remove row_index before export
        df_clean_export = df_clean.drop("row_index")
        cleaned_file_bytes = _generate_cleaned_file(df_clean_export, filename)
        cleaned_file_base64 = base64.b64encode(cleaned_file_bytes).decode('utf-8')

        # Build results
        quarantine_data = {
            "quality_score": quality_score,
            "quality_status": quality_status,
            "quarantine_analysis": quarantine_analysis,
            "quarantine_log": quarantine_log,
            "summary": f"Quarantine agent completed. Identified {quarantined_data.height} problematic records. Quality: {quality_status}.",
            "row_level_issues": _extract_row_level_issues(quarantined_data, quarantine_analysis),
            "defaults": {
                "required_fields": [],
                "range_constraints": {},
                "format_constraints": {},
                "expected_schema": {},
                "detect_missing_fields": True,
                "detect_type_mismatches": True,
                "detect_out_of_range": True,
                "detect_invalid_formats": True,
                "detect_broken_records": True,
                "detect_schema_mismatches": True,
                "quarantine_reduction_weight": 0.5,
                "data_integrity_weight": 0.3,
                "processing_efficiency_weight": 0.2,
                "excellent_threshold": 90,
                "good_threshold": 75
            },
            "overrides": {
                "required_fields": parameters.get("required_fields"),
                "range_constraints": parameters.get("range_constraints"),
                "format_constraints": parameters.get("format_constraints"),
                "expected_schema": parameters.get("expected_schema"),
                "detect_missing_fields": parameters.get("detect_missing_fields"),
                "detect_type_mismatches": parameters.get("detect_type_mismatches"),
                "detect_out_of_range": parameters.get("detect_out_of_range"),
                "detect_invalid_formats": parameters.get("detect_invalid_formats"),
                "detect_broken_records": parameters.get("detect_broken_records"),
                "detect_schema_mismatches": parameters.get("detect_schema_mismatches"),
                "quarantine_reduction_weight": parameters.get("quarantine_reduction_weight"),
                "data_integrity_weight": parameters.get("data_integrity_weight"),
                "processing_efficiency_weight": parameters.get("processing_efficiency_weight"),
                "excellent_threshold": parameters.get("excellent_threshold"),
                "good_threshold": parameters.get("good_threshold")
            },
            "parameters": {
                "required_fields": required_fields,
                "range_constraints": range_constraints,
                "format_constraints": format_constraints,
                "expected_schema": expected_schema,
                "detect_missing_fields": detect_missing_fields,
                "detect_type_mismatches": detect_type_mismatches,
                "detect_out_of_range": detect_out_of_range,
                "detect_invalid_formats": detect_invalid_formats,
                "detect_broken_records": detect_broken_records,
                "detect_schema_mismatches": detect_schema_mismatches,
                "quarantine_reduction_weight": quarantine_reduction_weight,
                "data_integrity_weight": data_integrity_weight,
                "processing_efficiency_weight": processing_efficiency_weight,
                "excellent_threshold": excellent_threshold,
                "good_threshold": good_threshold
            }
        }
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = [{
            "summary_id": "exec_quarantine",
            "title": "Data Quarantine Status",
            "value": f"{quality_score['overall_score']:.1f}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"Quality: {quality_status}, Quarantined: {quarantined_data.height} records ({round((quarantined_data.height / original_df.height * 100) if original_df.height > 0 else 0, 2):.1f}%), Clean: {df_clean.height} records, {len(quarantine_analysis.get('issue_types', {}))} issue types"
        }]
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_parts = []
        ai_analysis_parts.append(f"QUARANTINE AGENT ANALYSIS:")
        ai_analysis_parts.append(f"- Quality Score: {quality_score['overall_score']:.1f}/100 (Quarantine Reduction: {quality_score['metrics']['quarantine_reduction_rate']:.1f}, Data Integrity: {quality_score['metrics']['data_integrity_rate']:.1f}, Processing Efficiency: {quality_score['metrics']['processing_efficiency_rate']:.1f})")
        
        quarantine_pct = round((quarantined_data.height / original_df.height * 100) if original_df.height > 0 else 0, 2)
        ai_analysis_parts.append(f"- Quarantine Stats: {quarantined_data.height} records quarantined ({quarantine_pct:.1f}%), {df_clean.height} clean records ({100 - quarantine_pct:.1f}%)")
        
        issue_types = quarantine_analysis.get('issue_types', {})
        ai_analysis_parts.append(f"- Issue Types: {len(issue_types)} distinct types - {', '.join([f'{k}: {v}' for k, v in list(issue_types.items())[:5]])}")
        
        severity_breakdown = quarantine_analysis.get('severity_breakdown', {})
        ai_analysis_parts.append(f"- Severity Breakdown: Critical: {severity_breakdown.get('critical', 0)}, High: {severity_breakdown.get('high', 0)}, Medium: {severity_breakdown.get('medium', 0)}, Low: {severity_breakdown.get('low', 0)}")
        ai_analysis_parts.append(f"- Data Integrity Rate: {quality_score['metrics']['data_integrity_rate']:.1f}%, Processing Efficiency: {quality_score['metrics']['processing_efficiency_rate']:.1f}%")
        
        if quarantined_data.height > 0:
            ai_analysis_parts.append(f"- Recommendation: Review {quarantined_data.height} quarantined records and investigate root causes of data quality issues")
        else:
            ai_analysis_parts.append(f"- Recommendation: No data quality issues detected - dataset is clean and ready for processing")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # ==================== GENERATE ROW-LEVEL-ISSUES ====================
        row_level_issues = []
        
        # Extract row-level issues from quarantine analysis
        for issue in quarantine_analysis.get("quarantine_issues", [])[:500]:
            row_level_issues.append({
                "row_index": int(issue.get("row_index", 0)),
                "column": issue.get("column", "unknown"),
                "issue_type": "quarantine_flagged" if issue.get("issue_type") == "corrupted_record" else issue.get("issue_type", "data_anomaly"),
                "severity": issue.get("severity", "high"),
                "message": issue.get("description", "Data quality issue detected"),
                "value": None,
                "detection_method": issue.get("issue_type", "unknown")
            })
        
        # Add rows with multiple issues as "suspicious_row" indicators
        row_issue_counts = {}
        for issue in row_level_issues:
            row_idx = issue["row_index"]
            row_issue_counts[row_idx] = row_issue_counts.get(row_idx, 0) + 1
        
        # Identify suspicious rows (multiple issues in single row)
        for row_idx, count in row_issue_counts.items():
            if count >= 2 and len(row_level_issues) < 1000:
                row_level_issues.append({
                    "row_index": int(row_idx),
                    "column": "global",
                    "issue_type": "suspicious_row",
                    "severity": "critical" if count >= 3 else "warning",
                    "message": f"Row {row_idx} has {count} quality issues detected - suspicious data pattern",
                    "value": None,
                    "issue_count": count
                })
        
        # Add severity-based flagging for system-level concerns
        critical_issue_count = severity_breakdown.get("critical", 0)
        if critical_issue_count > 0 and len(row_level_issues) < 1000:
            row_level_issues.append({
                "row_index": 0,  # System-level indicator
                "column": "global",
                "issue_type": "high_risk_flag",
                "severity": "critical",
                "message": f"Dataset contains {critical_issue_count} critical-severity quarantine issues - data integrity at risk",
                "value": None,
                "critical_issue_count": critical_issue_count
            })
        
        # Add data quality anomaly for rows in quarantine zone
        if quarantined_data.height > 0:
            # We need to get the reason from the dataframe if we added it, or from issues
            # In _analyze_and_quarantine we added _quarantine_reason
            
            # Let's iterate over the first 100 rows of quarantined_data
            for row in quarantined_data.head(100).iter_rows(named=True):
                reason = row.get("_quarantine_reason", "Data quality anomaly")
                row_level_issues.append({
                    "row_index": int(row["row_index"]),
                    "column": "global",
                    "issue_type": "data_anomaly",
                    "severity": "critical",
                    "message": f"Row flagged for quarantine: {reason}",
                    "value": None,
                    "quarantined": True
                })
        
        # Cap at 1000 issues
        row_level_issues = row_level_issues[:1000]
        
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
            issue_type = issue.get("issue_type", "data_anomaly")
            severity = issue.get("severity", "info")
            
            if issue_type not in issue_summary["by_type"]:
                issue_summary["by_type"][issue_type] = 0
            issue_summary["by_type"][issue_type] += 1
            
            if severity in issue_summary["by_severity"]:
                issue_summary["by_severity"][severity] += 1
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        quarantine_pct = round((quarantined_data.height / original_df.height * 100) if original_df.height > 0 else 0, 2)
        severity_breakdown = quarantine_analysis.get('severity_breakdown', {})
        critical_issues = severity_breakdown.get('critical', 0)
        high_issues = severity_breakdown.get('high', 0)
        issue_types = quarantine_analysis.get('issue_types', {})
        missing_field_count = issue_types.get('missing_required_field', 0)
        type_mismatch_count = issue_types.get('type_mismatch', 0)
        schema_mismatch_count = issue_types.get('schema_mismatch', 0)
        
        # Alert 1: High quarantine volume (critical threshold)
        if quarantine_pct > 30:
            alerts.append({
                "alert_id": "alert_quarantine_001_volume_critical",
                "severity": "critical",
                "category": "data_quality",
                "message": f"CRITICAL: {quarantined_data.height} records ({quarantine_pct:.1f}%) quarantined - exceeds 30% threshold",
                "affected_fields_count": len(issue_types),
                "recommendation": "URGENT: Data quality degradation detected. Review source data immediately and implement stricter validation at ingestion."
            })
        elif quarantine_pct > 15:
            alerts.append({
                "alert_id": "alert_quarantine_001_volume_high",
                "severity": "high",
                "category": "data_quality",
                "message": f"High quarantine volume: {quarantined_data.height} records ({quarantine_pct:.1f}%) quarantined",
                "affected_fields_count": len(issue_types),
                "recommendation": "Investigate quarantine patterns. Data source quality may need improvement."
            })
        elif quarantine_pct > 5:
            alerts.append({
                "alert_id": "alert_quarantine_001_volume_medium",
                "severity": "medium",
                "category": "data_quality",
                "message": f"Moderate quarantine volume: {quarantined_data.height} records ({quarantine_pct:.1f}%) quarantined",
                "affected_fields_count": len(issue_types),
                "recommendation": "Monitor quarantine trends for patterns indicating systemic issues."
            })
        
        # Alert 2: Critical severity issues
        if critical_issues > 0:
            alerts.append({
                "alert_id": "alert_quarantine_002_critical_severity",
                "severity": "critical",
                "category": "data_integrity",
                "message": f"Critical data integrity issues: {critical_issues} record(s) with critical-severity problems",
                "affected_fields_count": critical_issues,
                "recommendation": "Address all critical issues immediately. These indicate severe data quality violations requiring urgent remediation."
            })
        
        # Alert 3: High severity issues
        if high_issues > original_df.height * 0.05:
            alerts.append({
                "alert_id": "alert_quarantine_003_high_severity",
                "severity": "high",
                "category": "data_quality",
                "message": f"High-severity issues detected: {high_issues} records with high-severity violations",
                "affected_fields_count": high_issues,
                "recommendation": "Prioritize fixing high-severity violations to improve dataset quality."
            })
        
        # Alert 4: Data integrity score
        if quality_score['metrics']['data_integrity_rate'] < 80:
            alerts.append({
                "alert_id": "alert_quarantine_004_integrity_score",
                "severity": "high" if quality_score['metrics']['data_integrity_rate'] < 70 else "medium",
                "category": "data_integrity",
                "message": f"Data integrity rate: {quality_score['metrics']['data_integrity_rate']:.1f}% (below 80% threshold)",
                "affected_fields_count": quarantined_data.height,
                "recommendation": "Improve data validation processes at source. Low integrity rate indicates missing or insufficient validation rules."
            })
        
        # Alert 5: Missing required fields violations
        if missing_field_count > 0:
            alerts.append({
                "alert_id": "alert_quarantine_005_missing_fields",
                "severity": "critical" if missing_field_count > original_df.height * 0.1 else "high",
                "category": "data_integrity",
                "message": f"Missing required fields: {missing_field_count} records missing mandatory fields",
                "affected_fields_count": missing_field_count,
                "recommendation": "Enforce required field validation at data ingestion. Missing mandatory fields indicate incomplete data capture."
            })
        
        # Alert 6: Type mismatches
        if type_mismatch_count > 0:
            alerts.append({
                "alert_id": "alert_quarantine_006_type_mismatches",
                "severity": "high" if type_mismatch_count > original_df.height * 0.05 else "medium",
                "category": "data_quality",
                "message": f"Type mismatches detected: {type_mismatch_count} records with incorrect data types",
                "affected_fields_count": type_mismatch_count,
                "recommendation": "Implement type validation and conversion rules. Type mismatches cause processing failures and data integrity issues."
            })
        
        # Alert 7: Schema mismatches
        if schema_mismatch_count > 0:
            alerts.append({
                "alert_id": "alert_quarantine_007_schema_mismatch",
                "severity": "critical",
                "category": "data_integrity",
                "message": f"Schema mismatches: {quarantined_data.height} records fail schema validation",
                "affected_fields_count": quarantined_data.height,
                "recommendation": "Validate and align data source schema. Schema mismatches prevent all record processing."
            })
        
        # Alert 8: Corrupted/invalid records
        corrupted_count = issue_types.get('corrupted_record', 0) + issue_types.get('invalid_format', 0) + issue_types.get('out_of_range', 0)
        if corrupted_count > 0:
            alerts.append({
                "alert_id": "alert_quarantine_008_corrupted_invalid",
                "severity": "high" if corrupted_count > original_df.height * 0.1 else "medium",
                "category": "data_quality",
                "message": f"Corrupted/invalid records: {corrupted_count} records with format violations or out-of-range values",
                "affected_fields_count": corrupted_count,
                "recommendation": "Review validation rules and data source quality. Invalid formats and corrupted records impact pipeline reliability."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Convert quarantine issues to standardized format with enhanced severity mapping
        for idx, q_issue in enumerate(quarantine_analysis.get('quarantine_issues', [])[:100]):
            issue_type = q_issue.get('issue_type', 'unknown')
            severity = q_issue.get('severity', 'medium')
            
            # Map severity more precisely based on issue type
            if issue_type in ['missing_required_field', 'schema_mismatch', 'corrupted_record']:
                severity = 'critical'
            elif issue_type in ['type_mismatch', 'out_of_range']:
                severity = 'high'
            elif issue_type == 'invalid_format':
                severity = 'medium'
            
            issues.append({
                "issue_id": f"issue_quarantine_{issue_type}_{idx}_{q_issue.get('row_index', 0)}",
                "agent_id": "quarantine-agent",
                "field_name": q_issue.get('column', 'N/A'),
                "issue_type": issue_type,
                "severity": severity,
                "message": q_issue.get('description', 'Data quarantine issue detected')
            })
        
        # Add aggregated issue summaries for issue type patterns
        for issue_type, count in issue_types.items():
            if count > 0 and len(issues) < 100:
                issues.append({
                    "issue_id": f"issue_quarantine_aggregate_{issue_type}",
                    "agent_id": "quarantine-agent",
                    "field_name": "all",
                    "issue_type": f"{issue_type}_pattern",
                    "severity": "critical" if issue_type in ['missing_required_field', 'schema_mismatch'] else "high" if issue_type == 'type_mismatch' else "medium",
                    "message": f"{count} record(s) identified with {issue_type} - indicating systemic {issue_type.replace('_', ' ')} issue"
                })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        agent_recommendations = []
        
        # Recommendation 1: Address critical issues
        if critical_issues > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_quarantine_critical",
                "agent_id": "quarantine-agent",
                "field_name": "multiple",
                "priority": "critical",
                "recommendation": f"Immediately review and fix {critical_issues} critical data integrity issues in quarantined records",
                "timeline": "immediate"
            })
        
        # Recommendation 2: Investigate data source
        if quarantined_data.height > original_df.height * 0.2:
            agent_recommendations.append({
                "recommendation_id": "rec_quarantine_source",
                "agent_id": "quarantine-agent",
                "field_name": "all",
                "priority": "high",
                "recommendation": f"Investigate data source quality - {quarantine_pct:.1f}% quarantine rate is excessive",
                "timeline": "1 week"
            })
        
        # Recommendation 3: Top issue types
        top_issue_types = sorted(issue_types.items(), key=lambda x: x[1], reverse=True)[:3]
        for idx, (issue_type, count) in enumerate(top_issue_types):
            agent_recommendations.append({
                "recommendation_id": f"rec_quarantine_issue_{idx}",
                "agent_id": "quarantine-agent",
                "field_name": "various",
                "priority": "high" if count > original_df.height * 0.1 else "medium",
                "recommendation": f"Address {issue_type} issues ({count} occurrences) with targeted validation rules",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 4: Schema validation
        if 'schema_mismatch' in issue_types:
            agent_recommendations.append({
                "recommendation_id": "rec_quarantine_schema",
                "agent_id": "quarantine-agent",
                "field_name": "schema",
                "priority": "high",
                "recommendation": "Implement schema validation at data ingestion to prevent schema mismatches",
                "timeline": "2 weeks"
            })
        
        # Recommendation 5: Review quarantined data
        if quarantined_data.height > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_quarantine_review",
                "agent_id": "quarantine-agent",
                "field_name": "all",
                "priority": "medium",
                "recommendation": f"Manually review quarantined data file to identify patterns and recovery opportunities",
                "timeline": "2 weeks"
            })
        
        # Recommendation 6: Update detection rules
        agent_recommendations.append({
            "recommendation_id": "rec_quarantine_rules",
            "agent_id": "quarantine-agent",
            "field_name": "configuration",
            "priority": "medium",
            "recommendation": "Fine-tune quarantine detection rules based on observed patterns to reduce false positives",
            "timeline": "3 weeks"
        })
        
        # Recommendation 7: Monitor trends
        agent_recommendations.append({
            "recommendation_id": "rec_quarantine_monitoring",
            "agent_id": "quarantine-agent",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Establish quarantine rate monitoring to detect data quality degradation early",
            "timeline": "3 weeks"
        })

        return {
            "status": "success",
            "agent_id": "quarantine-agent",
            "agent_name": "Quarantine Agent",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_processed": original_df.height,
                "quarantined_records": quarantined_data.height,
                "clean_records": df_clean.height,
                "quarantine_percentage": round((quarantined_data.height / original_df.height * 100) if original_df.height > 0 else 0, 2),
                "quarantine_issues_found": len(quarantine_analysis.get("quarantine_issues", []))
            },
            "data": quarantine_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
            "executive_summary" : executive_summary,
            "ai_analysis_text" : ai_analysis_text,
            "cleaned_file": {
                "filename": f"cleaned_{filename}",
                "content": cleaned_file_base64,
                "size_bytes": len(cleaned_file_bytes),
                "format": filename.split('.')[-1].lower()
            },
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "agent_id": "quarantine-agent",
            "agent_name": "Quarantine Agent",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _analyze_and_quarantine(
    df: pl.DataFrame,
    required_fields: List[str],
    range_constraints: Dict[str, Dict[str, float]],
    format_constraints: Dict[str, str],
    expected_schema: Dict[str, str],
    detection_flags: Dict[str, bool]
) -> Tuple[pl.DataFrame, List[str], Dict[str, Any]]:
    """
    Analyze data for issues and separate quarantine candidates.
    
    Returns:
        Tuple of (quarantined_dataframe, log_entries, analysis_dict)
    """
    quarantine_indices = set()
    quarantine_log = []
    quarantine_issues = []

    # 1. DETECT MISSING REQUIRED FIELDS
    if detection_flags.get("detect_missing_fields", True) and required_fields:
        for col in required_fields:
            if col in df.columns:
                # Check for null or empty string
                missing_df = df.filter(pl.col(col).is_null() | (pl.col(col) == ""))
                
                if missing_df.height > 0:
                    indices = missing_df["row_index"].to_list()
                    quarantine_indices.update(indices)
                    quarantine_log.append(f"Missing required field '{col}': {len(indices)} rows")
                    
                    for idx in indices[:100]:
                        quarantine_issues.append({
                            "row_index": int(idx),
                            "column": col,
                            "issue_type": "missing_required_field",
                            "severity": "critical",
                            "description": f"Required field '{col}' is missing"
                        })

    # 2. DETECT TYPE MISMATCHES
    if detection_flags.get("detect_type_mismatches", True):
        for col in df.columns:
            if col == "row_index": continue
            expected_type = expected_schema.get(col, None)
            
            if expected_type:
                mismatch_indices = []
                
                if expected_type in ["numeric", "integer", "float"]:
                    # Check if can be cast to Float64
                    mismatch_df = df.filter(
                        (pl.col(col).is_not_null()) & (pl.col(col) != "") &
                        (pl.col(col).cast(pl.Float64, strict=False).is_null())
                    )
                    mismatch_indices = mismatch_df["row_index"].to_list()

                elif expected_type == "boolean":
                     # Check if value is in true/false/1/0/yes/no
                     valid_bools = ['true', 'false', '1', '0', 'yes', 'no']
                     mismatch_df = df.filter(
                        (pl.col(col).is_not_null()) & (pl.col(col) != "") &
                        (~pl.col(col).str.to_lowercase().is_in(valid_bools))
                     )
                     mismatch_indices = mismatch_df["row_index"].to_list()
                
                if mismatch_indices:
                    quarantine_indices.update(mismatch_indices)
                    quarantine_log.append(f"Type mismatch in '{col}': expected {expected_type} ({len(mismatch_indices)} rows)")
                    for idx in mismatch_indices[:50]:
                         quarantine_issues.append({
                            "row_index": int(idx),
                            "column": col,
                            "issue_type": "type_mismatch",
                            "severity": "high",
                            "description": f"Type mismatch: expected {expected_type}"
                        })

    # 3. DETECT OUT-OF-RANGE VALUES
    if detection_flags.get("detect_out_of_range", True) and range_constraints:
        for col, constraints in range_constraints.items():
            if col in df.columns:
                min_val = constraints.get("min", None)
                max_val = constraints.get("max", None)
                
                valid_numeric_df = df.filter(
                    (pl.col(col).is_not_null()) & (pl.col(col) != "") &
                    (pl.col(col).cast(pl.Float64, strict=False).is_not_null())
                )
                
                if valid_numeric_df.height > 0:
                    numeric_col = valid_numeric_df.select(["row_index", pl.col(col).cast(pl.Float64).alias("val")])
                    
                    out_of_range_df = numeric_col.filter(
                        ((pl.lit(min_val).is_not_null()) & (pl.col("val") < min_val)) |
                        ((pl.lit(max_val).is_not_null()) & (pl.col("val") > max_val))
                    )
                    
                    indices = out_of_range_df["row_index"].to_list()
                    if indices:
                        quarantine_indices.update(indices)
                        quarantine_log.append(f"Out-of-range values in '{col}': {len(indices)} rows")
                        for row in out_of_range_df.head(50).iter_rows(named=True):
                             quarantine_issues.append({
                                "row_index": int(row["row_index"]),
                                "column": col,
                                "issue_type": "out_of_range",
                                "severity": "high",
                                "description": f"Value {row['val']} outside range [{min_val}, {max_val}]"
                            })

    # 4. DETECT INVALID FORMATS
    if detection_flags.get("detect_invalid_formats", True) and format_constraints:
        for col, pattern in format_constraints.items():
            if col in df.columns:
                # Use regex
                invalid_df = df.filter(
                    (pl.col(col).is_not_null()) & (pl.col(col) != "") &
                    (~pl.col(col).str.contains(pattern))
                )
                
                indices = invalid_df["row_index"].to_list()
                if indices:
                    quarantine_indices.update(indices)
                    quarantine_log.append(f"Invalid format in '{col}': {len(indices)} rows (pattern: {pattern})")
                    for row in invalid_df.head(50).iter_rows(named=True):
                        quarantine_issues.append({
                            "row_index": int(row["row_index"]),
                            "column": col,
                            "issue_type": "invalid_format",
                            "severity": "medium",
                            "description": f"Value '{row[col]}' does not match pattern '{pattern}'"
                        })

    # 5. DETECT BROKEN/CORRUPTED RECORDS
    if detection_flags.get("detect_broken_records", True):
        # Check for all nulls (empty strings in our case since we read as string)
        # Or actual nulls
        
        # Check for rows where all columns (except row_index) are null or empty
        cols_to_check = [c for c in df.columns if c != "row_index"]
        if cols_to_check:
            all_null_df = df.filter(
                pl.all_horizontal([(pl.col(c).is_null() | (pl.col(c) == "")) for c in cols_to_check])
            )
            
            indices = all_null_df["row_index"].to_list()
            if indices:
                quarantine_indices.update(indices)
                quarantine_log.append(f"Corrupted/broken records detected: {len(indices)} rows (empty)")
                for idx in indices[:50]:
                    quarantine_issues.append({
                        "row_index": int(idx),
                        "column": "record",
                        "issue_type": "corrupted_record",
                        "severity": "critical",
                        "description": "Record appears to be corrupted or broken (empty)"
                    })
        
        # Check for suspicious patterns (SQL injection)
        suspicious_patterns = [
            r"(?i)(?:drop\s+table|delete\s+from|insert\s+into|update\s+|select\s+\*)",
            r"['\"]?\s*OR\s+['\"]?1['\"]?\s*=['\"]?1",
            r"<script[^>]*>.*?</script>",
            r"javascript:",
        ]
        
        for col in cols_to_check:
            # Only check string-like columns? We read everything as string.
            for pattern in suspicious_patterns:
                suspicious_df = df.filter(
                    (pl.col(col).is_not_null()) &
                    (pl.col(col).str.contains(pattern))
                )
                
                indices = suspicious_df["row_index"].to_list()
                if indices:
                    quarantine_indices.update(indices)
                    # Log once per column/pattern combo maybe?
                    for idx in indices[:50]:
                         quarantine_issues.append({
                            "row_index": int(idx),
                            "column": col,
                            "issue_type": "corrupted_record",
                            "severity": "critical",
                            "description": f"Suspicious pattern detected in '{col}'"
                        })

    # 6. DETECT SCHEMA MISMATCHES
    if detection_flags.get("detect_schema_mismatches", True) and expected_schema:
        schema_mismatch_cols = set(expected_schema.keys()) - set(df.columns)
        
        if schema_mismatch_cols:
            quarantine_log.append(
                f"Schema mismatch: missing columns {schema_mismatch_cols}. All records affected."
            )
            # Quarantine all records if critical schema mismatch
            if len(schema_mismatch_cols) >= len(expected_schema) * 0.5:
                quarantine_indices.update(df["row_index"].to_list())
                quarantine_issues.append({
                    "row_index": 0,
                    "column": "schema",
                    "issue_type": "schema_mismatch",
                    "severity": "critical",
                    "description": f"Critical schema mismatch: missing {len(schema_mismatch_cols)} required columns"
                })

    # Isolate quarantined records
    quarantined_df = df.filter(pl.col("row_index").is_in(quarantine_indices))
    
    # Add metadata columns
    quarantined_df = quarantined_df.with_columns(
        pl.lit(datetime.utcnow().isoformat()).alias("_quarantine_timestamp")
    )
    
    # Add reason
    # Create a mapping dataframe
    if quarantine_issues:
        # Prioritize issues: critical > high > medium
        # Sort issues by severity
        severity_map = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_issues = sorted(quarantine_issues, key=lambda x: severity_map.get(x.get("severity", "low"), 4))
        
        # Keep first issue for each row
        unique_issues = {}
        for issue in sorted_issues:
            idx = issue["row_index"]
            if idx not in unique_issues:
                unique_issues[idx] = issue["description"]
            else:
                unique_issues[idx] = "Multiple issues detected"
        
        # Create DataFrame for join
        reasons_df = pl.DataFrame({
            "row_index": list(unique_issues.keys()),
            "_quarantine_reason": list(unique_issues.values())
        })
        
        # Join
        # We need to cast row_index to match types if needed, but both should be int/u32
        # pl.DataFrame creates Int64 by default for python ints
        # df.with_row_index creates UInt32
        
        reasons_df = reasons_df.with_columns(pl.col("row_index").cast(pl.UInt32))
        quarantined_df = quarantined_df.join(reasons_df, on="row_index", how="left")
    else:
        quarantined_df = quarantined_df.with_columns(pl.lit("Unknown").alias("_quarantine_reason"))

    quarantine_analysis = {
        "total_rows_analyzed": df.height,
        "total_quarantined": quarantined_df.height,
        "quarantine_percentage": round((quarantined_df.height / df.height * 100) if df.height > 0 else 0, 2),
        "quarantine_issues": quarantine_issues,
        "issue_types": _count_issue_types(quarantine_issues),
        "severity_breakdown": _count_severity_breakdown(quarantine_issues),
        "timestamp": datetime.utcnow().isoformat()
    }

    return quarantined_df, quarantine_log, quarantine_analysis

def _count_issue_types(issues: List[Dict]) -> Dict[str, int]:
    """Count issues by type."""
    counts = {}
    for issue in issues:
        issue_type = issue.get("issue_type", "unknown")
        counts[issue_type] = counts.get(issue_type, 0) + 1
    return counts


def _count_severity_breakdown(issues: List[Dict]) -> Dict[str, int]:
    """Count issues by severity."""
    counts = {}
    for issue in issues:
        severity = issue.get("severity", "unknown")
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def _calculate_quarantine_score(
    original_df: pl.DataFrame,
    cleaned_df: pl.DataFrame,
    quarantined_df: pl.DataFrame,
    quarantine_analysis: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate quarantine effectiveness score."""
    total_rows = original_df.height
    clean_rows = cleaned_df.height
    quarantined_rows = quarantined_df.height
    
    # Calculate metrics
    quarantine_reduction_rate = (quarantined_rows / total_rows * 100) if total_rows > 0 else 0
    data_integrity_rate = (clean_rows / total_rows * 100) if total_rows > 0 else 0
    processing_efficiency_rate = 100 if quarantined_rows < total_rows * 0.5 else 50
    
    # Calculate weighted score
    q_weight = config.get('quarantine_reduction_weight', 0.5)
    i_weight = config.get('data_integrity_weight', 0.3)
    e_weight = config.get('processing_efficiency_weight', 0.2)
    
    overall_score = (
        quarantine_reduction_rate * q_weight +
        data_integrity_rate * i_weight +
        processing_efficiency_rate * e_weight
    )
    
    return {
        "overall_score": round(overall_score, 1),
        "metrics": {
            "quarantine_reduction_rate": round(quarantine_reduction_rate, 1),
            "data_integrity_rate": round(data_integrity_rate, 1),
            "processing_efficiency_rate": round(processing_efficiency_rate, 1),
            "total_rows_analyzed": total_rows,
            "quarantined_rows": quarantined_rows,
            "clean_rows": clean_rows,
            "issue_count": len(quarantine_analysis.get("quarantine_issues", []))
        }
    }


def _extract_row_level_issues(quarantined_df: pl.DataFrame, quarantine_analysis: Dict) -> List[Dict]:
    """Extract row-level issue details."""
    issues = []
    
    for issue in quarantine_analysis.get("quarantine_issues", [])[:100]:
        issues.append({
            "row_index": issue.get("row_index"),
            "column": issue.get("column"),
            "issue_type": issue.get("issue_type"),
            "severity": issue.get("severity"),
            "description": issue.get("description")
        })
    
    return issues


def _generate_cleaned_file(df: pl.DataFrame, original_filename: str) -> bytes:
    """
    Generate cleaned data file (after quarantine removal).
    
    Args:
        df: Cleaned dataframe
        original_filename: Original filename to determine format
        
    Returns:
        File contents as bytes
    """
    output = io.BytesIO()
    df.write_csv(output)
    return output.getvalue()
