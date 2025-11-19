"""
Field Standardization Agent

Standardizes field values across datasets with comprehensive normalization strategies.
Handles case normalization, whitespace trimming, synonym replacement, and unit alignment
to ensure data consistency and uniformity.

Input: CSV/JSON/XLSX file (primary)
Output: Standardized field standardization results with effectiveness scores
"""

import pandas as pd
import numpy as np
import io
import time
import re
import base64
from typing import Dict, Any, Optional, List, Set, Tuple


def execute_field_standardization(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Standardize field values in data.

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
    case_strategy = parameters.get("case_strategy", "lowercase")  # lowercase, uppercase, titlecase, none
    trim_whitespace = parameters.get("trim_whitespace", True)
    normalize_internal_spacing = parameters.get("normalize_internal_spacing", True)
    apply_synonyms = parameters.get("apply_synonyms", True)
    synonym_mappings = parameters.get("synonym_mappings", {})  # Dict of column -> {synonym -> standard}
    unit_standardization = parameters.get("unit_standardization", False)
    unit_mappings = parameters.get("unit_mappings", {})  # Dict of column -> {unit -> standard_unit, conversion_factor}
    target_columns = parameters.get("target_columns", [])  # Columns to standardize (all if empty)
    preserve_columns = parameters.get("preserve_columns", [])  # Columns to preserve from standardization
    
    # Scoring weights
    standardization_effectiveness_weight = parameters.get("standardization_effectiveness_weight", 0.5)
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
                "agent_id": "field-standardization",
                "error": f"Unsupported file format: {filename}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.empty:
            return {
                "status": "error",
                "agent_id": "field-standardization",
                "agent_name": "Field Standardization",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Store original data for comparison
        original_df = df.copy()
        
        # Determine columns to process
        if target_columns:
            columns_to_process = [col for col in target_columns if col in df.columns]
        else:
            columns_to_process = [col for col in df.columns if col not in preserve_columns]
        
        # Analyze pre-standardization state
        pre_analysis = _analyze_field_variations(df, columns_to_process)
        
        # Apply standardization operations
        df_standardized, standardization_log, standardization_issues = _apply_standardization(
            df,
            columns_to_process,
            {
                "case_strategy": case_strategy,
                "trim_whitespace": trim_whitespace,
                "normalize_internal_spacing": normalize_internal_spacing,
                "apply_synonyms": apply_synonyms,
                "synonym_mappings": synonym_mappings,
                "unit_standardization": unit_standardization,
                "unit_mappings": unit_mappings
            }
        )
        
        # Analyze post-standardization state
        post_analysis = _analyze_field_variations(df_standardized, columns_to_process)
        
        # Calculate standardization effectiveness
        standardization_score = _calculate_standardization_score(
            pre_analysis,
            post_analysis,
            original_df,
            df_standardized,
            {
                "standardization_effectiveness_weight": standardization_effectiveness_weight,
                "data_retention_weight": data_retention_weight,
                "column_retention_weight": column_retention_weight,
                "excellent_threshold": excellent_threshold,
                "good_threshold": good_threshold
            }
        )
        
        # Determine quality status
        if standardization_score["overall_score"] >= excellent_threshold:
            quality_status = "excellent"
        elif standardization_score["overall_score"] >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"
        
        # Generate ROW-LEVEL-ISSUES
        row_level_issues = []
        
        # Iterate through standardization issues to create row-level entries
        for std_issue in standardization_issues:
            issue_type = "inconsistent_format"  # Default for case/whitespace issues
            severity = "info"
            
            original_val = std_issue.get("original_value", "")
            standardized_val = std_issue.get("standardized_value", "")
            
            # Determine issue type based on change type
            if original_val != standardized_val:
                # Check if it's whitespace issue
                if original_val.strip() == standardized_val:
                    issue_type = "format_violation"
                    severity = "info"
                # Check if it's case issue
                elif original_val.lower() == standardized_val.lower():
                    issue_type = "inconsistent_format"
                    severity = "info"
                # Otherwise it's a standardization/normalization issue
                else:
                    issue_type = "standardization_needed"
                    severity = "info"
            
            if len(row_level_issues) < 1000:
                row_level_issues.append({
                    "row_index": int(std_issue.get("row_index", 0)),
                    "column": str(std_issue.get("column", "")),
                    "issue_type": issue_type,
                    "severity": severity,
                    "message": f"Standardized: '{original_val}' → '{standardized_val}'",
                    "value": original_val,
                    "standardized_value": standardized_val
                })
        
        # Also add row-level issues for values with format inconsistencies (not yet changed)
        for col in columns_to_process:
            if col not in original_df.columns:
                continue
            
            col_analysis = pre_analysis.get("column_analysis", {}).get(col, {})
            
            # Only add issues if column has case or whitespace variations
            if col_analysis.get("case_variations", 0) > 0 or col_analysis.get("whitespace_issues", 0) > 0:
                for row_idx, value in enumerate(original_df[col]):
                    if pd.isna(value) or len(row_level_issues) >= 1000:
                        continue
                    
                    value_str = str(value)
                    has_issue = False
                    issue_type = "format_violation"
                    
                    # Check for leading/trailing whitespace
                    if value_str != value_str.strip():
                        has_issue = True
                        issue_type = "format_violation"
                    
                    # Check for multiple internal spaces
                    elif '  ' in value_str:
                        has_issue = True
                        issue_type = "format_violation"
                    
                    # Check if value appears multiple times with different cases (case variation)
                    elif col_analysis.get("case_variations", 0) > 0:
                        # Try to find if this value has case variants
                        unique_vals = original_df[col].dropna().unique()
                        lowercase_version = value_str.lower()
                        case_variants = [v for v in unique_vals if pd.notna(v) and str(v).lower() == lowercase_version and str(v) != value_str]
                        if case_variants:
                            has_issue = True
                            issue_type = "inconsistent_format"
                    
                    if has_issue:
                        row_level_issues.append({
                            "row_index": int(row_idx),
                            "column": str(col),
                            "issue_type": issue_type,
                            "severity": "info",
                            "message": f"Format inconsistency: '{value_str}' - {issue_type.replace('_', ' ')}",
                            "value": value_str
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
        
        # Aggregate by type
        for issue in row_level_issues:
            issue_type = issue.get("issue_type", "unknown")
            issue_summary["by_type"][issue_type] = issue_summary["by_type"].get(issue_type, 0) + 1
        
        # Aggregate by severity
        for issue in row_level_issues:
            severity = issue.get("severity", "info")
            issue_summary["by_severity"][severity] = issue_summary["by_severity"].get(severity, 0) + 1
        
        # Build standardization analysis
        standardization_analysis = {
            "columns_standardized": len(columns_to_process),
            "total_columns": len(df.columns),
            "pre_standardization": pre_analysis,
            "post_standardization": post_analysis,
            "standardization_operations": {
                "case_normalization": case_strategy != "none",
                "whitespace_trimming": trim_whitespace,
                "internal_spacing_normalized": normalize_internal_spacing,
                "synonyms_applied": apply_synonyms and bool(synonym_mappings),
                "units_aligned": unit_standardization and bool(unit_mappings)
            },
            "improvements": _calculate_improvements(pre_analysis, post_analysis),
            "recommendations": _generate_recommendations(
                pre_analysis, post_analysis, columns_to_process
            )
        }
        
        # Build results
        standardization_data = {
            "standardization_score": standardization_score,
            "quality_status": quality_status,
            "standardization_analysis": standardization_analysis,
            "standardization_log": standardization_log,
            "summary": f"Field standardization completed. Quality: {quality_status}. Processed {len(columns_to_process)} columns across {len(original_df)} rows.",
            "row_level_issues": row_level_issues[:100],  # Limit to first 100
            "issue_summary": issue_summary,
            "overrides": {
                "case_strategy": case_strategy,
                "trim_whitespace": trim_whitespace,
                "normalize_internal_spacing": normalize_internal_spacing,
                "apply_synonyms": apply_synonyms,
                "synonym_mappings": synonym_mappings,
                "unit_standardization": unit_standardization,
                "unit_mappings": unit_mappings,
                "target_columns": target_columns,
                "preserve_columns": preserve_columns,
                "standardization_effectiveness_weight": standardization_effectiveness_weight,
                "data_retention_weight": data_retention_weight,
                "column_retention_weight": column_retention_weight,
                "excellent_threshold": excellent_threshold,
                "good_threshold": good_threshold
            }
        }
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        values_changed = standardization_analysis["improvements"].get("total_values_standardized", 0)
        variations_reduced = standardization_analysis["improvements"].get("total_variations_reduced", 0)
        executive_summary = [{
            "summary_id": "exec_field_standardization",
            "title": "Field Standardization Status",
            "value": f"{standardization_score['overall_score']:.1f}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"Quality: {quality_status}, Values Changed: {values_changed}, {len(columns_to_process)} columns standardized, {variations_reduced} variations reduced, {standardization_score['metrics']['standardization_effectiveness']:.1f}% improvement"
        }]
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_parts = []
        ai_analysis_parts.append(f"FIELD STANDARDIZATION ANALYSIS:")
        ai_analysis_parts.append(f"- Standardization Score: {standardization_score['overall_score']:.1f}/100 (Effectiveness: {standardization_score['metrics']['standardization_effectiveness']:.1f}, Data Retention: {standardization_score['metrics']['data_retention_rate']:.1f}, Column Retention: {standardization_score['metrics']['column_retention_rate']:.1f})")
        ai_analysis_parts.append(f"- Standardization Applied: {values_changed} values standardized, {variations_reduced} variations reduced, {standardization_score['metrics']['standardization_effectiveness']:.1f}% improvement")
        
        ai_analysis_parts.append(f"- Columns Processed: {len(columns_to_process)} columns standardized ({', '.join(list(columns_to_process)[:5])}{'...' if len(columns_to_process) > 5 else ''})")
        ai_analysis_parts.append(f"- Data Quality: {standardization_score['metrics']['data_retention_rate']:.1f}% data quality after standardization")
        
        col_improvements = standardization_analysis["improvements"].get("column_improvements", {})
        if len(col_improvements) > 0:
            avg_improvement = sum([v.get('improvement_percentage', 0) for v in col_improvements.values()]) / len(col_improvements)
            ai_analysis_parts.append(f"- Average Improvement: {avg_improvement:.1f}% per column")
        
        if len(standardization_analysis.get('recommendations', [])) > 0:
            ai_analysis_parts.append(f"- Top Recommendation: {standardization_analysis['recommendations'][0].get('recommendation', 'Review standardization strategy')}")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # High variation alert
        total_variations = pre_analysis.get('total_variations', 0)
        if total_variations > len(columns_to_process) * 10:
            alerts.append({
                "alert_id": "alert_standardization_high_variations",
                "severity": "high",
                "category": "field_consistency",
                "message": f"High field variation: {total_variations} variations detected across {len(columns_to_process)} columns",
                "affected_fields_count": len(columns_to_process),
                "recommendation": "Implement standardization rules and data entry validation to reduce field variations."
            })
        
        # Columns needing standardization
        cols_needing_std = pre_analysis.get('columns_needing_standardization', 0)
        if cols_needing_std > len(columns_to_process) * 0.5:
            alerts.append({
                "alert_id": "alert_standardization_column_quality",
                "severity": "high",
                "category": "column_quality",
                "message": f"{cols_needing_std} columns ({(cols_needing_std/len(columns_to_process)*100):.1f}%) need standardization",
                "affected_fields_count": cols_needing_std,
                "recommendation": "Apply comprehensive standardization strategies including case normalization and whitespace handling."
            })
        
        # Low improvement alert
        improvement_pct = standardization_score['metrics'].get('standardization_effectiveness', 0)
        if improvement_pct < 10 and total_variations > 0:
            alerts.append({
                "alert_id": "alert_standardization_low_improvement",
                "severity": "medium",
                "category": "effectiveness",
                "message": f"Low improvement: Only {improvement_pct:.1f}% variation reduction achieved",
                "affected_fields_count": len(columns_to_process),
                "recommendation": "Review standardization strategies. Consider synonym mapping and unit alignment."
            })
        
        # Quality score alert
        if standardization_score["overall_score"] < good_threshold:
            severity = "critical" if standardization_score["overall_score"] < 50 else "high" if standardization_score["overall_score"] < good_threshold else "medium"
            alerts.append({
                "alert_id": "alert_standardization_quality",
                "severity": severity,
                "category": "quality_score",
                "message": f"Standardization quality score: {standardization_score['overall_score']:.1f}/100 ({quality_status})",
                "affected_fields_count": len(columns_to_process),
                "recommendation": "Optimize standardization rules and apply advanced normalization techniques for better results."
            })
        
        # Format inconsistency alert
        post_variations = post_analysis.get('total_variations', 0)
        if post_variations > 0:
            alerts.append({
                "alert_id": "alert_standardization_remaining_variations",
                "severity": "medium",
                "category": "field_consistency",
                "message": f"{post_variations} format variations remain after standardization",
                "affected_fields_count": post_analysis.get('columns_needing_standardization', 0),
                "recommendation": "Review synonym mappings and add custom normalization rules for remaining variations."
            })
        
        # Transformation failure alert
        if values_changed < total_variations * 0.5 and total_variations > 0:
            alerts.append({
                "alert_id": "alert_standardization_low_transformation",
                "severity": "high",
                "category": "effectiveness",
                "message": f"Low transformation rate: Only {values_changed} of {total_variations} variations addressed ({(values_changed/total_variations*100):.1f}%)",
                "affected_fields_count": len(columns_to_process),
                "recommendation": "Enable additional standardization options (case normalization, whitespace handling, synonyms)."
            })
        
        # No synonym mapping configured
        if not synonym_mappings and len([c for c, d in pre_analysis.get('column_analysis', {}).items() if d.get('variation_score', 0) > 30]) > 0:
            alerts.append({
                "alert_id": "alert_standardization_no_synonyms",
                "severity": "medium",
                "category": "configuration",
                "message": "No synonym mappings configured despite high field variation. Synonym mapping can significantly improve standardization.",
                "affected_fields_count": len([c for c, d in pre_analysis.get('column_analysis', {}).items() if d.get('variation_score', 0) > 30]),
                "recommendation": "Analyze field values and create synonym mapping rules for common variations."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Convert standardization issues to standardized format (row-level changes)
        for std_issue in standardization_issues[:100]:
            issues.append({
                "issue_id": f"issue_standardization_{std_issue.get('row_index', 0)}_{std_issue.get('column', 'unknown')}",
                "agent_id": "field-standardization",
                "field_name": std_issue.get('column', 'N/A'),
                "issue_type": std_issue.get('issue_type', 'field_standardized'),
                "severity": std_issue.get('severity', 'info'),
                "message": f"Standardized: '{std_issue.get('original_value', '')}' → '{std_issue.get('standardized_value', '')}'"
            })
        
        # Add column-level issues for high variation columns
        for col, data in pre_analysis.get('column_analysis', {}).items():
            if data.get('variation_score', 0) > 50:
                issues.append({
                    "issue_id": f"issue_standardization_high_variation_{col}",
                    "agent_id": "field-standardization",
                    "field_name": col,
                    "issue_type": "high_variation",
                    "severity": "high",
                    "message": f"Column '{col}' has high variation score ({data.get('variation_score', 0):.1f}%) - {data.get('total_unique_values', 0)} unique values detected"
                })
        
        # Add issues for columns with remaining case variations
        for col, data in post_analysis.get('column_analysis', {}).items():
            if data.get('case_variations', 0) > 0:
                issues.append({
                    "issue_id": f"issue_standardization_case_remaining_{col}",
                    "agent_id": "field-standardization",
                    "field_name": col,
                    "issue_type": "case_variation_remaining",
                    "severity": "medium",
                    "message": f"Column '{col}' still has {data.get('case_variations', 0)} case variations after standardization"
                })
        
        # Add issues for columns with whitespace problems
        for col, data in post_analysis.get('column_analysis', {}).items():
            if data.get('whitespace_issues', 0) > 0:
                issues.append({
                    "issue_id": f"issue_standardization_whitespace_{col}",
                    "agent_id": "field-standardization",
                    "field_name": col,
                    "issue_type": "whitespace_issues",
                    "severity": "medium",
                    "message": f"Column '{col}' has {data.get('whitespace_issues', 0)} whitespace formatting issues"
                })
        
        # Add low improvement issue if standardization didn't help much
        if improvement_pct < 10 and total_variations > 0:
            issues.append({
                "issue_id": "issue_standardization_low_impact",
                "agent_id": "field-standardization",
                "field_name": "dataset",
                "issue_type": "low_effectiveness",
                "severity": "high",
                "message": f"Standardization achieved only {improvement_pct:.1f}% improvement despite {total_variations} variations detected - review strategy"
            })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        agent_recommendations = []
        
        # Recommendation 1: Apply synonym mapping for high-variation columns
        high_var_cols = [col for col, data in pre_analysis.get('column_analysis', {}).items() 
                        if data.get('variation_score', 0) > 50]
        if high_var_cols:
            agent_recommendations.append({
                "recommendation_id": "rec_standardization_synonyms",
                "agent_id": "field-standardization",
                "field_name": ", ".join(high_var_cols[:3]),
                "priority": "high",
                "recommendation": f"Apply synonym mapping to {len(high_var_cols)} high-variation column(s) to improve consistency",
                "timeline": "1 week"
            })
        
        # Recommendation 2: Column-specific strategies
        for rec in standardization_analysis.get('recommendations', [])[:3]:
            agent_recommendations.append({
                "recommendation_id": f"rec_standardization_{rec.get('column', 'unknown')}",
                "agent_id": "field-standardization",
                "field_name": rec.get('column', 'N/A'),
                "priority": rec.get('priority', 'medium'),
                "recommendation": f"{rec.get('action', 'Review')}: {rec.get('reason', 'Improve standardization')}",
                "timeline": "1 week" if rec.get('priority') == 'high' else "2 weeks"
            })
        
        # Recommendation 3: Case strategy optimization
        if case_strategy == 'none' and cols_needing_std > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_standardization_case",
                "agent_id": "field-standardization",
                "field_name": "all",
                "priority": "medium",
                "recommendation": "Enable case normalization (lowercase/uppercase/titlecase) to reduce case variations",
                "timeline": "2 weeks"
            })
        
        # Recommendation 4: Whitespace handling
        if not trim_whitespace or not normalize_internal_spacing:
            agent_recommendations.append({
                "recommendation_id": "rec_standardization_whitespace",
                "agent_id": "field-standardization",
                "field_name": "all",
                "priority": "medium",
                "recommendation": "Enable whitespace trimming and internal spacing normalization for better consistency",
                "timeline": "2 weeks"
            })
        
        # Recommendation 5: Data entry validation
        agent_recommendations.append({
            "recommendation_id": "rec_standardization_validation",
            "agent_id": "field-standardization",
            "field_name": "all",
            "priority": "medium",
            "recommendation": "Implement data entry validation rules to enforce standardization at source",
            "timeline": "2-3 weeks"
        })
        
        # Recommendation 6: Continuous monitoring
        agent_recommendations.append({
            "recommendation_id": "rec_standardization_monitoring",
            "agent_id": "field-standardization",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Establish field variation monitoring to detect standardization drift over time",
            "timeline": "3 weeks"
        })
        
        # Recommendation 7: Synonym dictionary development
        if not synonym_mappings and total_variations > len(columns_to_process) * 5:
            agent_recommendations.append({
                "recommendation_id": "rec_standardization_synonym_dev",
                "agent_id": "field-standardization",
                "field_name": "all",
                "priority": "high",
                "recommendation": f"Develop synonym dictionary for {len(columns_to_process)} columns to handle {total_variations} variations",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 8: Automated standardization pipeline
        agent_recommendations.append({
            "recommendation_id": "rec_standardization_automation",
            "agent_id": "field-standardization",
            "field_name": "all",
            "priority": "medium",
            "recommendation": "Implement automated standardization pipeline to apply rules consistently across all data ingestion points",
            "timeline": "2-3 weeks"
        })
        
        # Recommendation 9: Format documentation
        agent_recommendations.append({
            "recommendation_id": "rec_standardization_documentation",
            "agent_id": "field-standardization",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Document standard formats, normalization rules, and synonym mappings for team reference and consistency",
            "timeline": "3 weeks"
        })
        
        # Recommendation 10: Training data quality
        if improvement_pct > 20:
            agent_recommendations.append({
                "recommendation_id": "rec_standardization_training",
                "agent_id": "field-standardization",
                "field_name": "all",
                "priority": "medium",
                "recommendation": f"Train data entry personnel on standard formats to reduce {improvement_pct:.1f}% variation rate at source",
                "timeline": "2 weeks"
            })

        # Generate cleaned file (CSV format)
        cleaned_file_bytes = _generate_cleaned_file(df_standardized, filename)
        cleaned_file_base64 = base64.b64encode(cleaned_file_bytes).decode('utf-8')

        return {
            "status": "success",
            "agent_id": "field-standardization",
            "agent_name": "Field Standardization",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_processed": len(original_df),
                "columns_standardized": len(columns_to_process),
                "values_changed": standardization_analysis["improvements"].get("total_values_standardized", 0),
                "variations_reduced": standardization_analysis["improvements"].get("total_variations_reduced", 0),
                "total_issues": len(standardization_issues)
            },
            "data": standardization_data,
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
            "agent_id": "field-standardization",
            "agent_name": "Field Standardization",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _analyze_field_variations(df: pd.DataFrame, columns: List[str]) -> Dict[str, Any]:
    """Analyze field variations in specified columns."""
    analysis = {}
    total_variations = 0
    
    for col in columns:
        if col not in df.columns:
            continue
        
        # Only analyze string columns
        if df[col].dtype == 'object' or df[col].dtype.name == 'string':
            unique_values = df[col].dropna().unique()
            total_unique = len(unique_values)
            total_non_null = df[col].notna().sum()
            
            # Analyze case variations
            case_variations = _count_case_variations(unique_values)
            
            # Analyze whitespace issues
            whitespace_issues = _count_whitespace_issues(unique_values)
            
            # Calculate variation score (lower is better)
            variation_score = (total_unique / total_non_null * 100) if total_non_null > 0 else 0
            
            analysis[col] = {
                "total_unique_values": int(total_unique),
                "total_non_null_values": int(total_non_null),
                "variation_score": round(variation_score, 2),
                "case_variations": case_variations,
                "whitespace_issues": whitespace_issues,
                "needs_standardization": case_variations > 0 or whitespace_issues > 0
            }
            
            total_variations += case_variations + whitespace_issues
    
    return {
        "column_analysis": analysis,
        "total_variations": total_variations,
        "columns_needing_standardization": sum(
            1 for col_data in analysis.values() if col_data.get("needs_standardization", False)
        )
    }


def _count_case_variations(values: np.ndarray) -> int:
    """Count how many values have case variations."""
    if len(values) == 0:
        return 0
    
    # Group by lowercase version and count groups with multiple originals
    lowercase_groups = {}
    for val in values:
        if pd.isna(val):
            continue
        str_val = str(val)
        lower_val = str_val.lower()
        
        if lower_val not in lowercase_groups:
            lowercase_groups[lower_val] = set()
        lowercase_groups[lower_val].add(str_val)
    
    # Count groups with variations
    variations = sum(1 for group in lowercase_groups.values() if len(group) > 1)
    return variations


def _count_whitespace_issues(values: np.ndarray) -> int:
    """Count how many values have whitespace issues."""
    if len(values) == 0:
        return 0
    
    issues = 0
    for val in values:
        if pd.isna(val):
            continue
        str_val = str(val)
        
        # Check for leading/trailing whitespace
        if str_val != str_val.strip():
            issues += 1
            continue
        
        # Check for multiple internal spaces
        if '  ' in str_val:
            issues += 1
    
    return issues


def _apply_standardization(
    df: pd.DataFrame,
    columns: List[str],
    config: Dict[str, Any]
) -> Tuple[pd.DataFrame, List[str], List[Dict]]:
    """Apply standardization operations to specified columns."""
    df_standardized = df.copy()
    log = []
    row_issues = []
    
    case_strategy = config.get("case_strategy", "lowercase")
    trim_whitespace = config.get("trim_whitespace", True)
    normalize_internal_spacing = config.get("normalize_internal_spacing", True)
    apply_synonyms = config.get("apply_synonyms", True)
    synonym_mappings = config.get("synonym_mappings", {})
    unit_standardization = config.get("unit_standardization", False)
    unit_mappings = config.get("unit_mappings", {})
    
    for col in columns:
        if col not in df_standardized.columns:
            continue
        
        # Only process string columns
        if df_standardized[col].dtype not in ['object', 'string']:
            continue
        
        changes_made = 0
        original_values = df_standardized[col].copy()
        
        # Apply transformations
        for idx, value in df_standardized[col].items():
            if pd.isna(value):
                continue
            
            original_value = str(value)
            standardized_value = original_value
            
            # 1. Trim whitespace
            if trim_whitespace:
                standardized_value = standardized_value.strip()
            
            # 2. Normalize internal spacing
            if normalize_internal_spacing:
                standardized_value = re.sub(r'\s+', ' ', standardized_value)
            
            # 3. Apply case normalization
            if case_strategy == "lowercase":
                standardized_value = standardized_value.lower()
            elif case_strategy == "uppercase":
                standardized_value = standardized_value.upper()
            elif case_strategy == "titlecase":
                standardized_value = standardized_value.title()
            
            # 4. Apply synonym replacement
            if apply_synonyms and col in synonym_mappings:
                for synonym, standard in synonym_mappings[col].items():
                    if standardized_value.lower() == synonym.lower():
                        standardized_value = standard
                        break
            
            # 5. Apply unit standardization
            if unit_standardization and col in unit_mappings:
                standardized_value = _apply_unit_conversion(
                    standardized_value, unit_mappings[col]
                )
            
            # Update if changed
            if standardized_value != original_value:
                df_standardized.at[idx, col] = standardized_value
                changes_made += 1
                
                # Add row-level issue
                if len(row_issues) < 100:
                    row_issues.append({
                        "row_index": int(idx),
                        "column": col,
                        "issue_type": "field_standardized",
                        "original_value": original_value,
                        "standardized_value": standardized_value,
                        "severity": "info"
                    })
        
        if changes_made > 0:
            log.append(
                f"Standardized {changes_made} values in column '{col}' "
                f"({(changes_made / len(df_standardized) * 100):.1f}% of rows)"
            )
    
    return df_standardized, log, row_issues


def _apply_unit_conversion(value: str, unit_config: Dict[str, Any]) -> str:
    """Apply unit conversion to a value string."""
    # Example: "5 ft" -> "60 inches" using conversion rules
    for unit_pattern, conversion in unit_config.items():
        # Simple pattern matching for units
        pattern = r'(\d+(?:\.\d+)?)\s*' + re.escape(unit_pattern)
        match = re.search(pattern, value, re.IGNORECASE)
        
        if match:
            number = float(match.group(1))
            conversion_factor = conversion.get("factor", 1)
            target_unit = conversion.get("target_unit", unit_pattern)
            
            converted_value = number * conversion_factor
            return f"{converted_value} {target_unit}"
    
    return value


def _calculate_improvements(pre_analysis: Dict[str, Any], post_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate improvements from standardization."""
    pre_cols = pre_analysis.get("column_analysis", {})
    post_cols = post_analysis.get("column_analysis", {})
    
    total_variations_reduced = 0
    total_values_standardized = 0
    column_improvements = {}
    
    for col in pre_cols.keys():
        if col not in post_cols:
            continue
        
        pre_data = pre_cols[col]
        post_data = post_cols[col]
        
        # Calculate reductions
        variation_reduction = pre_data.get("total_unique_values", 0) - post_data.get("total_unique_values", 0)
        case_improvement = pre_data.get("case_variations", 0) - post_data.get("case_variations", 0)
        whitespace_improvement = pre_data.get("whitespace_issues", 0) - post_data.get("whitespace_issues", 0)
        
        total_variations_reduced += variation_reduction
        total_values_standardized += case_improvement + whitespace_improvement
        
        column_improvements[col] = {
            "unique_values_reduced": int(variation_reduction),
            "case_variations_fixed": int(case_improvement),
            "whitespace_issues_fixed": int(whitespace_improvement),
            "improvement_percentage": round(
                ((pre_data.get("variation_score", 0) - post_data.get("variation_score", 0)) / 
                 pre_data.get("variation_score", 1)) * 100
                if pre_data.get("variation_score", 0) > 0 else 0,
                2
            )
        }
    
    return {
        "total_variations_reduced": int(total_variations_reduced),
        "total_values_standardized": int(total_values_standardized),
        "column_improvements": column_improvements
    }


def _generate_recommendations(
    pre_analysis: Dict[str, Any],
    post_analysis: Dict[str, Any],
    columns: List[str]
) -> List[Dict[str, Any]]:
    """Generate recommendations based on standardization results."""
    recommendations = []
    
    pre_cols = pre_analysis.get("column_analysis", {})
    post_cols = post_analysis.get("column_analysis", {})
    
    for col in columns:
        if col not in pre_cols or col not in post_cols:
            continue
        
        pre_data = pre_cols[col]
        post_data = post_cols[col]
        
        # Check if still has issues
        if post_data.get("case_variations", 0) > 0:
            recommendations.append({
                "column": col,
                "action": "apply_stricter_case_normalization",
                "reason": f"Column still has {post_data.get('case_variations', 0)} case variations after standardization",
                "priority": "medium"
            })
        
        if post_data.get("whitespace_issues", 0) > 0:
            recommendations.append({
                "column": col,
                "action": "review_whitespace_handling",
                "reason": f"Column still has {post_data.get('whitespace_issues', 0)} whitespace issues",
                "priority": "medium"
            })
        
        # Check if variation is still high
        if post_data.get("variation_score", 0) > 50:
            recommendations.append({
                "column": col,
                "action": "consider_synonym_mapping",
                "reason": f"High variation score ({post_data.get('variation_score', 0):.1f}%) suggests need for synonym mapping or categorical grouping",
                "priority": "high"
            })
    
    # Add general recommendations if no specific ones
    if not recommendations:
        recommendations.append({
            "column": "all",
            "action": "maintain_standards",
            "reason": "Standardization completed successfully. Continue applying these standards to new data.",
            "priority": "low"
        })
    
    return recommendations


def _calculate_standardization_score(
    pre_analysis: Dict[str, Any],
    post_analysis: Dict[str, Any],
    original_df: pd.DataFrame,
    standardized_df: pd.DataFrame,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate standardization effectiveness score."""
    pre_variations = pre_analysis.get("total_variations", 0)
    post_variations = post_analysis.get("total_variations", 0)
    
    # Calculate metrics
    standardization_effectiveness = (
        ((pre_variations - post_variations) / pre_variations * 100)
        if pre_variations > 0 else 100
    )
    
    data_retention_rate = (len(standardized_df) / len(original_df) * 100) if len(original_df) > 0 else 0
    column_retention_rate = (len(standardized_df.columns) / len(original_df.columns) * 100) if len(original_df.columns) > 0 else 0
    
    # Calculate weighted score
    effectiveness_weight = config.get('standardization_effectiveness_weight', 0.5)
    data_weight = config.get('data_retention_weight', 0.3)
    column_weight = config.get('column_retention_weight', 0.2)
    
    overall_score = (
        standardization_effectiveness * effectiveness_weight +
        data_retention_rate * data_weight +
        column_retention_rate * column_weight
    )
    
    return {
        "overall_score": round(overall_score, 1),
        "metrics": {
            "standardization_effectiveness": round(standardization_effectiveness, 1),
            "data_retention_rate": round(data_retention_rate, 1),
            "column_retention_rate": round(column_retention_rate, 1),
            "variations_before": pre_variations,
            "variations_after": post_variations,
            "variations_reduced": pre_variations - post_variations,
            "original_rows": len(original_df),
            "standardized_rows": len(standardized_df),
            "original_columns": len(original_df.columns),
            "standardized_columns": len(standardized_df.columns)
        }
    }


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
