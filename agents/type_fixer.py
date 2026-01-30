"""
Type Fixer Agent

Detects and fixes data type inconsistencies in data.
Analyzes column types and applies configurable type conversion strategies.
Input: CSV file (primary)
Output: Standardized type fixing results with effectiveness scores
"""

import polars as pl
import numpy as np
import io
import re
import time
import base64
from typing import Dict, Any, Optional, List


def execute_type_fixer(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Fix data types in data.

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
    auto_convert_numeric = parameters.get("auto_convert_numeric", True)
    auto_convert_datetime = parameters.get("auto_convert_datetime", True)
    auto_convert_category = parameters.get("auto_convert_category", True)
    preserve_mixed_types = parameters.get("preserve_mixed_types", False)
    type_reduction_weight = parameters.get("type_reduction_weight", 0.5)
    data_retention_weight = parameters.get("data_retention_weight", 0.3)
    column_retention_weight = parameters.get("column_retention_weight", 0.2)
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file - CSV only
        if not filename.endswith('.csv'):
            return {
                "status": "error",
                "agent_id": "type-fixer",
                "error": f"Unsupported file format: {filename}. Only CSV files are supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        try:
            # Read CSV with Polars
            # infer_schema_length=10000 to get good type inference initially
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": "type-fixer",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.height == 0:
            return {
                "status": "error",
                "agent_id": "type-fixer",
                "agent_name": "Type Fixer",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Store original data for comparison (clone)
        original_df = df.clone()
        
        # Analyze type issues
        type_analysis = _analyze_type_issues(df)
        
        # Generate type fixing recommendations
        fix_config = _generate_fix_config(
            type_analysis,
            auto_convert_numeric,
            auto_convert_datetime,
            auto_convert_category
        )
        
        # Apply type fixes
        df_fixed, fix_log = _apply_type_fixes(df, fix_config)
        
        # Calculate fixing effectiveness
        fixing_score = _calculate_fixing_score(original_df, df_fixed, type_analysis, {
            "type_reduction_weight": type_reduction_weight,
            "data_retention_weight": data_retention_weight,
            "column_retention_weight": column_retention_weight,
            "excellent_threshold": excellent_threshold,
            "good_threshold": good_threshold
        })
        
        # Determine quality status
        if fixing_score["overall_score"] >= excellent_threshold:
            quality_status = "excellent"
        elif fixing_score["overall_score"] >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"
        
        # Identify type fixing issues
        type_issues = _identify_type_issues(original_df, df_fixed, type_analysis)
        
        # Generate ROW-LEVEL-ISSUES
        row_level_issues = []
        
        # Iterate through each column with type issues and mark affected rows
        for col in type_analysis.get("columns_with_issues", []):
            if col not in original_df.columns:
                continue
            
            type_data = type_analysis.get("type_summary", {}).get(col, {})
            current_type = type_data.get("current_type", "Utf8")
            suggested_type = type_data.get("suggested_type", current_type)
            
            # We need to find rows that violate the suggested type
            # Filter rows
            
            if suggested_type == "numeric" and current_type == "Utf8":
                # Find non-numeric strings
                # Use regex or cast check
                # Regex for numeric: ^-?\d+(\.\d+)?$
                # Polars regex
                numeric_pattern = r"^-?\d+(\.\d+)?$"
                
                non_numeric = original_df.with_row_index("row_index").filter(
                    pl.col(col).is_not_null() &
                    ~pl.col(col).str.contains(numeric_pattern)
                )
                
                for row in non_numeric.iter_rows(named=True):
                    if len(row_level_issues) >= 1000: break
                    row_level_issues.append({
                        "row_index": int(row["row_index"]),
                        "column": str(col),
                        "issue_type": "type_mismatch",
                        "severity": "warning",
                        "message": f"Non-numeric value '{row[col]}' found in column '{col}' that should contain numeric values",
                        "value": str(row[col]),
                        "current_type": str(current_type),
                        "suggested_type": str(suggested_type)
                    })

            elif suggested_type == "datetime" and current_type == "Utf8":
                # Find non-datetime strings
                # This is harder with regex as date formats vary.
                # We can try to cast to date and see what fails (returns null)
                # But we need to be careful not to count nulls that were already null.
                
                # Try casting with strict=False (returns null on failure)
                # But we need to know if it failed.
                # original not null AND cast is null => failure
                
                # Note: Polars str.to_datetime requires a format or it tries strict ISO.
                # If we want flexible parsing, we might need to try multiple formats or use a heuristic.
                # For now, let's use a simple regex check for common date patterns if possible, or just skip row-level detail for complex dates if too slow.
                # The original code used `_is_date_string` with regexes.
                
                date_patterns = [
                    r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
                    r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
                    r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
                ]
                combined_pattern = "|".join(date_patterns)
                
                non_date = original_df.with_row_index("row_index").filter(
                    pl.col(col).is_not_null() &
                    ~pl.col(col).str.contains(combined_pattern)
                )
                
                for row in non_date.iter_rows(named=True):
                    if len(row_level_issues) >= 1000: break
                    row_level_issues.append({
                        "row_index": int(row["row_index"]),
                        "column": str(col),
                        "issue_type": "format_violation",
                        "severity": "warning",
                        "message": f"Non-datetime value '{row[col]}' found in column '{col}' that should contain datetime values",
                        "value": str(row[col]),
                        "current_type": str(current_type),
                        "suggested_type": str(suggested_type)
                    })

            elif suggested_type == "integer" and current_type == "Float64":
                # Check for non-integer floats
                # (val % 1 != 0)
                non_int = original_df.with_row_index("row_index").filter(
                    pl.col(col).is_not_null() &
                    (pl.col(col) % 1 != 0)
                )
                
                for row in non_int.iter_rows(named=True):
                    if len(row_level_issues) >= 1000: break
                    row_level_issues.append({
                        "row_index": int(row["row_index"]),
                        "column": str(col),
                        "issue_type": "type_conflict",
                        "severity": "info",
                        "message": f"Float value '{row[col]}' found in column '{col}' that contains only integers",
                        "value": str(row[col]),
                        "current_type": str(current_type),
                        "suggested_type": str(suggested_type)
                    })
            
            if len(row_level_issues) >= 1000: break

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
        
        # Aggregate by type
        for issue in row_level_issues:
            issue_type = issue.get("issue_type", "unknown")
            issue_summary["by_type"][issue_type] = issue_summary["by_type"].get(issue_type, 0) + 1
        
        # Aggregate by severity
        for issue in row_level_issues:
            severity = issue.get("severity", "info")
            issue_summary["by_severity"][severity] = issue_summary["by_severity"].get(severity, 0) + 1
        
        # Build results
        type_fixing_data = {
            "fixing_score": fixing_score,
            "quality_status": quality_status,
            "type_analysis": type_analysis,
            "fix_log": fix_log,
            "summary": f"Type fixing completed. Quality: {quality_status}. Processed {len(original_df)} rows, fixed {len(fix_log)} type issues.",
            "row_level_issues": row_level_issues[:100],  # Limit to first 100
            "issue_summary": issue_summary,
            "defaults": {
                "auto_convert_numeric": True,
                "auto_convert_datetime": True,
                "auto_convert_category": True,
                "preserve_mixed_types": False,
                "type_reduction_weight": 0.5,
                "data_retention_weight": 0.3,
                "column_retention_weight": 0.2,
                "excellent_threshold": 90,
                "good_threshold": 75
            },
            "overrides": {
                "auto_convert_numeric": parameters.get("auto_convert_numeric"),
                "auto_convert_datetime": parameters.get("auto_convert_datetime"),
                "auto_convert_category": parameters.get("auto_convert_category"),
                "preserve_mixed_types": parameters.get("preserve_mixed_types"),
                "type_reduction_weight": parameters.get("type_reduction_weight"),
                "data_retention_weight": parameters.get("data_retention_weight"),
                "column_retention_weight": parameters.get("column_retention_weight"),
                "excellent_threshold": parameters.get("excellent_threshold"),
                "good_threshold": parameters.get("good_threshold")
            },
            "parameters": {
                "auto_convert_numeric": auto_convert_numeric,
                "auto_convert_datetime": auto_convert_datetime,
                "auto_convert_category": auto_convert_category,
                "preserve_mixed_types": preserve_mixed_types,
                "type_reduction_weight": type_reduction_weight,
                "data_retention_weight": data_retention_weight,
                "column_retention_weight": column_retention_weight,
                "excellent_threshold": excellent_threshold,
                "good_threshold": good_threshold
            }
        }
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = [{
            "summary_id": "exec_type_fixing",
            "title": "Type Fixing Status",
            "value": f"{fixing_score['overall_score']:.1f}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"Quality: {quality_status}, Issues Fixed: {len(fix_log)}, {len(type_analysis['columns_with_issues'])} columns had type issues, {fixing_score['metrics']['issue_reduction_rate']:.1f}% success rate"
        }]
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_parts = []
        ai_analysis_parts.append(f"TYPE FIXER ANALYSIS:")
        ai_analysis_parts.append(f"- Fixing Score: {fixing_score['overall_score']:.1f}/100 (Issue Reduction: {fixing_score['metrics']['issue_reduction_rate']:.1f}, Data Retention: {fixing_score['metrics']['data_retention_rate']:.1f}, Column Retention: {fixing_score['metrics']['column_retention_rate']:.1f})")
        ai_analysis_parts.append(f"- Type Issues Fixed: {len(fix_log)} issues resolved across {len(type_analysis['columns_with_issues'])} columns, {fixing_score['metrics']['issue_reduction_rate']:.1f}% success rate")
        
        cols_with_issues = type_analysis['columns_with_issues']
        ai_analysis_parts.append(f"- Columns Fixed: {', '.join(list(cols_with_issues)[:5])}{'...' if len(cols_with_issues) > 5 else ''}")
        ai_analysis_parts.append(f"- Data Integrity: {fixing_score['metrics']['data_retention_rate']:.1f}% data integrity maintained after type conversions")
        ai_analysis_parts.append(f"- Conversions Applied: {len(fix_log)} type conversions performed")
        
        if len(type_analysis.get('recommendations', [])) > 0:
            ai_analysis_parts.append(f"- Top Recommendation: {type_analysis['recommendations'][0].get('recommendation', 'Review type conversion strategy')}")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # High type mismatch alert
        if type_analysis['total_issues'] > len(df.columns) * 0.3:
            alerts.append({
                "alert_id": "alert_types_high_mismatches",
                "severity": "critical",
                "category": "type_integrity",
                "message": f"High type mismatch rate: {type_analysis['total_issues']} issues across {len(cols_with_issues)} columns ({(type_analysis['total_issues']/len(df.columns)*100):.1f}% of columns)",
                "affected_fields_count": len(cols_with_issues),
                "recommendation": "Review data schema and implement strict type validation at data ingestion."
            })
        
        # Failed conversions alert
        failed_fixes = type_analysis['total_issues'] - len(fix_log)
        if failed_fixes > 0:
            alerts.append({
                "alert_id": "alert_types_conversion_failures",
                "severity": "high",
                "category": "type_conversion",
                "message": f"{failed_fixes} type conversion(s) failed out of {type_analysis['total_issues']} attempted",
                "affected_fields_count": failed_fixes,
                "recommendation": "Review failed conversions and implement data cleaning before type conversion."
            })
        
        # Data integrity after conversion
        if fixing_score['metrics']['data_retention_rate'] < 95:
            alerts.append({
                "alert_id": "alert_types_data_integrity",
                "severity": "high",
                "category": "data_integrity",
                "message": f"Data integrity: {fixing_score['metrics']['data_retention_rate']:.1f}% after type conversions (below 95% threshold)",
                "affected_fields_count": len(cols_with_issues),
                "recommendation": "Validate type conversions did not corrupt data values. Review conversion logs for errors."
            })
        
        # Quality score alert
        if fixing_score["overall_score"] < good_threshold:
            severity = "critical" if fixing_score["overall_score"] < 50 else "high" if fixing_score["overall_score"] < good_threshold else "medium"
            alerts.append({
                "alert_id": "alert_types_quality",
                "severity": severity,
                "category": "quality_score",
                "message": f"Type fixing quality score: {fixing_score['overall_score']:.1f}/100 ({quality_status})",
                "affected_fields_count": len(cols_with_issues),
                "recommendation": "Optimize type conversion strategies and handle edge cases for better results."
            })
        
        # Mixed type columns alert
        mixed_type_cols = [col for col, data in type_analysis.get('type_summary', {}).items() 
                          if 'mixed' in str(data.get('issues', [])).lower()]
        if len(mixed_type_cols) > 0:
            alerts.append({
                "alert_id": "alert_types_mixed_columns",
                "severity": "high",
                "category": "type_consistency",
                "message": f"{len(mixed_type_cols)} column(s) contain mixed data types requiring type coercion",
                "affected_fields_count": len(mixed_type_cols),
                "recommendation": "Standardize data types at source or implement strict type validation during data entry."
            })
        
        # Precision loss alert
        float_to_int_conversions = [log for log in fix_log if 'float' in log.lower() and 'integer' in log.lower()]
        if len(float_to_int_conversions) > 0:
            alerts.append({
                "alert_id": "alert_types_precision_loss",
                "severity": "medium",
                "category": "data_integrity",
                "message": f"{len(float_to_int_conversions)} conversion(s) from float to integer may result in precision loss",
                "affected_fields_count": len(float_to_int_conversions),
                "recommendation": "Verify that precision loss is acceptable for these columns or preserve as float."
            })
        
        # No auto-conversion enabled alert
        if not auto_convert_numeric and not auto_convert_datetime:
            alerts.append({
                "alert_id": "alert_types_no_auto_conversion",
                "severity": "medium",
                "category": "configuration",
                "message": "Auto-conversion disabled for numeric and datetime types - manual type fixing required",
                "affected_fields_count": type_analysis['total_issues'],
                "recommendation": "Enable auto-conversion settings to automatically fix common type mismatches."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Convert type issues to standardized format (column-level type mismatches)
        for type_issue in type_issues[:100]:
            issues.append({
                "issue_id": f"issue_types_{type_issue.get('column', 'unknown')}_type_mismatch",
                "agent_id": "type-fixer",
                "field_name": type_issue.get('column', 'N/A'),
                "issue_type": type_issue.get('issue_type', 'type_mismatch'),
                "severity": type_issue.get('severity', 'warning'),
                "message": type_issue.get('description', 'Type mismatch detected')
            })
        
        # Add detailed column-leveldatatype issues
        for col, type_data in type_analysis.get('type_summary', {}).items():
            issues.append({
                "issue_id": f"issue_types_column_{col}_type_issue",
                "agent_id": "type-fixer",
                "field_name": str(col),
                "issue_type": "incorrect_datatype",
                "severity": "high",
                "message": f"Column '{col}' has type '{type_data.get('current_type')}' but should be '{type_data.get('suggested_type')}': {'; '.join(type_data.get('issues', []))}"
            })
        
        # Add conversion failure issues
        failed_conversions = [log for log in fix_log if 'error' in log.lower() or 'failed' in log.lower()]
        for i, failure in enumerate(failed_conversions[:20]):
            issues.append({
                "issue_id": f"issue_types_conversion_failure_{i}",
                "agent_id": "type-fixer",
                "field_name": "multiple",
                "issue_type": "conversion_failure",
                "severity": "critical",
                "message": f"Type conversion failed: {failure}"
            })
        
        # Add data integrity issue if conversions caused data loss
        if fixing_score['metrics']['data_retention_rate'] < 100:
            issues.append({
                "issue_id": "issue_types_data_loss",
                "agent_id": "type-fixer",
                "field_name": "dataset",
                "issue_type": "data_retention",
                "severity": "high",
                "message": f"Data retention: {fixing_score['metrics']['data_retention_rate']:.1f}% - some rows lost during type conversions"
            })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        agent_recommendations = []
        
        # Recommendation 1: Schema validation
        if type_analysis['total_issues'] > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_types_schema_validation",
                "agent_id": "type-fixer",
                "field_name": "all",
                "priority": "critical" if type_analysis['total_issues'] > len(df.columns) * 0.5 else "high",
                "recommendation": f"Implement schema validation at data ingestion to prevent {type_analysis['total_issues']} type mismatches",
                "timeline": "immediate" if type_analysis['total_issues'] > len(df.columns) * 0.5 else "1 week"
            })
        
        # Recommendation 2: Column-specific fixes
        for rec in type_analysis.get('recommendations', [])[:3]:
            agent_recommendations.append({
                "recommendation_id": f"rec_types_{rec.get('column', 'unknown')}",
                "agent_id": "type-fixer",
                "field_name": rec.get('column', 'N/A'),
                "priority": rec.get('priority', 'medium'),
                "recommendation": f"{rec.get('action', 'Review')}: {rec.get('reason', 'Fix type mismatch')}",
                "timeline": "1 week" if rec.get('priority') == 'high' else "2 weeks"
            })
        
        # Recommendation 3: Handle failed conversions
        if failed_fixes > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_types_failed_conversions",
                "agent_id": "type-fixer",
                "field_name": "multiple",
                "priority": "high",
                "recommendation": f"Review and fix {failed_fixes} failed type conversions with pre-cleaning or custom conversion logic",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 4: Auto-conversion settings
        agent_recommendations.append({
            "recommendation_id": "rec_types_auto_conversion",
            "agent_id": "type-fixer",
            "field_name": "configuration",
            "priority": "medium",
            "recommendation": "Enable auto-conversion for numeric and datetime types to streamline type fixing process",
            "timeline": "2 weeks"
        })
        
        # Recommendation 5: Data validation
        agent_recommendations.append({
            "recommendation_id": "rec_types_validation",
            "agent_id": "type-fixer",
            "field_name": "all",
            "priority": "medium",
            "recommendation": "Add data validation rules to ensure converted values maintain semantic meaning",
            "timeline": "2 weeks"
        })
        
        # Recommendation 6: Type documentation
        agent_recommendations.append({
            "recommendation_id": "rec_types_documentation",
            "agent_id": "type-fixer",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Document expected data types for each column to prevent future type mismatches",
            "timeline": "3 weeks"
        })
        
        # Recommendation 7: Mixed type handling
        if len(mixed_type_cols) > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_types_mixed_handling",
                "agent_id": "type-fixer",
                "field_name": ", ".join(mixed_type_cols[:3]),
                "priority": "high",
                "recommendation": f"Implement data cleaning for {len(mixed_type_cols)} mixed-type column(s) before type conversion",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 8: Schema enforcement
        agent_recommendations.append({
            "recommendation_id": "rec_types_schema_enforcement",
            "agent_id": "type-fixer",
            "field_name": "all",
            "priority": "high",
            "recommendation": "Implement database schema enforcement to prevent type mismatches at the storage layer",
            "timeline": "2-3 weeks"
        })
        
        # Recommendation 9: Monitoring
        agent_recommendations.append({
            "recommendation_id": "rec_types_monitoring",
            "agent_id": "type-fixer",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Set up type consistency monitoring to detect type drift and conversion failures",
            "timeline": "3 weeks"
        })
        
        # Recommendation 10: Pre-processing pipeline
        agent_recommendations.append({
            "recommendation_id": "rec_types_preprocessing",
            "agent_id": "type-fixer",
            "field_name": "all",
            "priority": "medium",
            "recommendation": "Build pre-processing pipeline to clean and normalize data before type conversion attempts",
            "timeline": "2-3 weeks"
        })

        # Generate cleaned file (CSV format)
        cleaned_file_bytes = _generate_cleaned_file(df_fixed, filename)
        cleaned_file_base64 = base64.b64encode(cleaned_file_bytes).decode('utf-8')

        return {
            "status": "success",
            "agent_id": "type-fixer",
            "agent_name": "Type Fixer",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_processed": len(df_fixed),
                "type_issues_fixed": len(fix_log),
                "original_type_issues": type_analysis['total_issues'],
                "remaining_type_issues": type_analysis['total_issues'] - len(fix_log),
                "total_issues": len(type_issues)
            },
            "data": type_fixing_data,
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
            "agent_id": "type-fixer",
            "agent_name": "Type Fixer",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _analyze_type_issues(df: pl.DataFrame) -> Dict[str, Any]:
    """Analyze data type inconsistencies in the dataset."""
    type_analysis = {
        "total_columns": len(df.columns),
        "columns_with_issues": [],
        "total_issues": 0,
        "type_summary": {},
        "recommendations": []
    }
    
    for col in df.columns:
        # Polars dtype
        current_dtype = str(df[col].dtype)
        issues = []
        suggested_type = current_dtype
        
        # Check for mixed types in Utf8 columns
        if current_dtype == 'Utf8':
            # Sample data
            col_data = df.select(pl.col(col)).drop_nulls().head(100)
            
            if col_data.height > 0:
                # Check numeric
                numeric_pattern = r"^-?\d+(\.\d+)?$"
                numeric_count = col_data.filter(pl.col(col).str.contains(numeric_pattern)).height
                
                # Check date
                date_patterns = [
                    r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
                    r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
                    r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
                ]
                combined_date_pattern = "|".join(date_patterns)
                date_count = col_data.filter(pl.col(col).str.contains(combined_date_pattern)).height
                
                total_sampled = col_data.height
                
                numeric_pct = (numeric_count / total_sampled) * 100
                date_pct = (date_count / total_sampled) * 100
                
                if numeric_pct > 70:
                    issues.append("Should be numeric type")
                    suggested_type = "numeric"
                elif date_pct > 70:
                    issues.append("Should be datetime type")
                    suggested_type = "datetime"
        
        # Check for incorrectly typed numeric columns (Float that are all Int)
        elif current_dtype in ['Float32', 'Float64']:
            # Check if all non-null values are integers
            # (val % 1 == 0)
            is_all_int = df.select(
                (pl.col(col).drop_nulls() % 1 == 0).all()
            ).item()
            
            if is_all_int:
                issues.append("Float column contains only integer values")
                suggested_type = "integer"
        
        if issues:
            type_analysis["columns_with_issues"].append(str(col))
            type_analysis["total_issues"] += 1
            
            # Get sample values
            sample_vals = df.select(pl.col(col)).head(5).to_series().to_list()
            sample_vals_str = [str(x) for x in sample_vals]
            
            type_analysis["type_summary"][str(col)] = {
                "current_type": current_dtype,
                "suggested_type": suggested_type,
                "issues": issues,
                "sample_values": sample_vals_str
            }
            
            priority = "high" if len(issues) > 1 else "medium"
            type_analysis["recommendations"].append({
                "column": str(col),
                "action": f"convert_to_{suggested_type}",
                "reason": "; ".join(issues),
                "priority": priority
            })
    
    return type_analysis


def _generate_fix_config(
    type_analysis: Dict[str, Any],
    auto_numeric: bool,
    auto_datetime: bool,
    auto_category: bool
) -> Dict[str, Any]:
    """Generate type fixing configuration based on analysis."""
    config = {"column_fixes": {}}
    
    for col, issue_data in type_analysis.get("type_summary", {}).items():
        if not auto_numeric and issue_data.get("suggested_type") == "numeric":
            continue
        if not auto_datetime and issue_data.get("suggested_type") == "datetime":
            continue
        if not auto_category and issue_data.get("suggested_type") == "category":
            continue
        
        config["column_fixes"][col] = issue_data.get("suggested_type", "string")
    
    return config


def _apply_type_fixes(df: pl.DataFrame, fix_config: Dict[str, Any]) -> tuple:
    """Apply type fixes to the dataframe."""
    df_fixed = df.clone()
    fix_log = []
    
    column_fixes = fix_config.get('column_fixes', {})
    
    for col, target_type in column_fixes.items():
        if col not in df_fixed.columns:
            continue
            
        try:
            original_type = str(df_fixed[col].dtype)
            
            if target_type == 'numeric':
                # Try cast to Float64, strict=False (null on error)
                # Or infer?
                # Polars cast to Float64 handles strings
                df_fixed = df_fixed.with_columns(pl.col(col).cast(pl.Float64, strict=False))
                fix_log.append(f"Converted '{col}' from {original_type} to numeric")
                
            elif target_type == 'integer':
                # Cast to Int64
                df_fixed = df_fixed.with_columns(pl.col(col).cast(pl.Int64, strict=False))
                fix_log.append(f"Converted '{col}' from {original_type} to integer")
                
            elif target_type == 'datetime':
                # Try to cast to datetime with flexible parsing
                # We use map_elements to handle multiple formats
                def parse_date(val):
                    if val is None: return None
                    val_str = str(val).strip()
                    if not val_str: return None
                    
                    from datetime import datetime
                    formats = [
                        "%Y-%m-%d", "%Y-%m-%d %H:%M:%S",
                        "%d-%m-%Y", "%d-%m-%Y %H:%M:%S",
                        "%d/%m/%Y", "%d/%m/%Y %H:%M:%S",
                        "%m/%d/%Y", "%m/%d/%Y %H:%M:%S",
                        "%d-%b-%y", "%d-%b-%Y",  # 02-Jan-25
                        "%Y/%m/%d", "%d.%m.%Y"
                    ]
                    
                    for fmt in formats:
                        try:
                            return datetime.strptime(val_str, fmt)
                        except ValueError:
                            continue
                    return None

                # First try standard polars conversion (fast)
                # If that fails (nulls), we might want to try custom parsing?
                # But strict=False returns nulls.
                # Better to just use custom parsing for the whole column if we suspect mixed formats,
                # or just use it. map_elements is slower but safer for "fixing".
                
                df_fixed = df_fixed.with_columns(
                    pl.col(col).map_elements(parse_date, return_dtype=pl.Datetime).alias(col)
                )
                fix_log.append(f"Converted '{col}' from {original_type} to datetime")
                
            elif target_type == 'string':
                df_fixed = df_fixed.with_columns(pl.col(col).cast(pl.Utf8))
                fix_log.append(f"Converted '{col}' from {original_type} to string")
                
            elif target_type == 'category':
                df_fixed = df_fixed.with_columns(pl.col(col).cast(pl.Categorical))
                fix_log.append(f"Converted '{col}' from {original_type} to category")
                
        except Exception as e:
            fix_log.append(f"Error converting '{col}' to {target_type}: {str(e)}")
    
    return df_fixed, fix_log


def _calculate_fixing_score(
    original_df: pl.DataFrame,
    fixed_df: pl.DataFrame,
    type_analysis: Dict[str, Any],
    config: dict
) -> Dict[str, Any]:
    """Calculate type fixing effectiveness score."""
    original_issues = type_analysis.get('total_issues', 0)
    
    # Re-analyze to get remaining issues
    remaining_analysis = _analyze_type_issues(fixed_df)
    remaining_issues = remaining_analysis.get('total_issues', 0)
    
    # Calculate metrics
    issue_reduction_rate = ((original_issues - remaining_issues) / original_issues * 100) if original_issues > 0 else 100
    data_retention_rate = (len(fixed_df) / len(original_df) * 100) if len(original_df) > 0 else 0
    column_retention_rate = (len(fixed_df.columns) / len(original_df.columns) * 100) if len(original_df.columns) > 0 else 0
    
    # Calculate weighted score
    issue_weight = float(config.get('type_reduction_weight', 0.5))
    data_weight = float(config.get('data_retention_weight', 0.3))
    column_weight = float(config.get('column_retention_weight', 0.2))
    
    overall_score = (
        float(issue_reduction_rate) * issue_weight +
        float(data_retention_rate) * data_weight +
        float(column_retention_rate) * column_weight
    )
    
    # Determine fixing quality
    excellent_threshold = float(config.get('excellent_threshold', 90))
    good_threshold = float(config.get('good_threshold', 75))
    
    if overall_score >= excellent_threshold:
        quality = "excellent"
        quality_color = "green"
    elif overall_score >= good_threshold:
        quality = "good"
        quality_color = "yellow"
    else:
        quality = "needs_improvement"
        quality_color = "red"
    
    return _convert_numpy_types({
        "overall_score": round(overall_score, 1),
        "quality": quality,
        "quality_color": quality_color,
        "metrics": {
            "issue_reduction_rate": round(issue_reduction_rate, 1),
            "data_retention_rate": round(data_retention_rate, 1),
            "column_retention_rate": round(column_retention_rate, 1),
            "original_issues": original_issues,
            "remaining_issues": remaining_issues,
            "original_rows": len(original_df),
            "fixed_rows": len(fixed_df),
            "original_columns": len(original_df.columns),
            "fixed_columns": len(fixed_df.columns)
        },
        "weights_used": {
            "type_reduction_weight": issue_weight,
            "data_retention_weight": data_weight,
            "column_retention_weight": column_weight
        }
    })


def _identify_type_issues(
    original_df: pl.DataFrame,
    fixed_df: pl.DataFrame,
    type_analysis: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Identify type-level issues in the DataFrame."""
    issues = []
    
    # Add issues from type analysis
    for col, type_data in type_analysis.get("type_summary", {}).items():
        for issue_text in type_data.get("issues", []):
            issues.append({
                "column": str(col),
                "issue_type": "type_mismatch",
                "description": issue_text,
                "severity": "warning",
                "original_type": type_data.get("current_type"),
                "suggested_type": type_data.get("suggested_type")
            })
    
    return issues


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


def _generate_cleaned_file(df: pl.DataFrame, original_filename: str) -> bytes:
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
    df.write_csv(output)
    return output.getvalue()
