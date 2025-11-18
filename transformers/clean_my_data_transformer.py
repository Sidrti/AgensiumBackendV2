"""
Clean My Data Transformer

Combines outputs from cleaning and validation agents into a final unified response.
Agents include:
- null-handler: Null value detection and imputation
- outlier-remover: Outlier detection and handling
- type-fixer: Type conversion and fixing
- governance-checker: Governance compliance validation
- test-coverage-agent: Test coverage validation

This transformer:
1. Takes individual agent outputs
2. Aggregates findings across agents
3. Creates cross-agent alerts and recommendations
4. Generates executive summary
5. Delegates download generation to dedicated download module
6. Creates structured final response
"""

from typing import Dict, List, Any
from datetime import datetime
from ai.analysis_summary_ai import AnalysisSummaryAI
from downloads.clean_my_data_downloads import CleanMyDataDownloads


def transform_clean_my_data_response(
    agent_results: Dict[str, Any],
    execution_time_ms: int,
    analysis_id: str
) -> Dict[str, Any]:
    """
    Transform individual agent outputs into final unified response.
    
    Args:
        agent_results: Dictionary of agent_id -> agent output
        execution_time_ms: Total execution time
        analysis_id: Unique analysis identifier
        
    Returns:
        Final unified response matching clean-my-data response format
    """
    
    # Extract individual agent outputs
    cleanse_previewer_output = agent_results.get("cleanse-previewer", {})
    null_handler_output = agent_results.get("null-handler", {})
    outlier_output = agent_results.get("outlier-remover", {})
    type_fixer_output = agent_results.get("type-fixer", {})
    duplicate_resolver_output = agent_results.get("duplicate-resolver", {})
    field_standardization_output = agent_results.get("field-standardization", {})
    quarantine_output = agent_results.get("quarantine-agent", {})
    governance_output = agent_results.get("governance-checker", {})
    test_coverage_output = agent_results.get("test-coverage-agent", {})
    
    # Aggregate findings
    all_alerts = []
    all_issues = []
    all_recommendations = []
    executive_summary = []
    
    # ==================== CLEANSE PREVIEWER ALERTS & ISSUES ====================
    if cleanse_previewer_output.get("status") == "success":
        preview_data = cleanse_previewer_output.get("data", {})
        preview_score = preview_data.get("preview_score", {})
        preview_analysis = preview_data.get("preview_analysis", {})
        overall_impact = preview_analysis.get("overall_impact", {})
        
        overall_score = preview_score.get("overall_score", 0)
        safe_to_execute = overall_impact.get("safe_to_execute", True)
        high_impact_rules = overall_impact.get("high_impact_rules", 0)
        
        if not safe_to_execute or high_impact_rules > 0:
            severity = "critical" if not safe_to_execute else "high"
            all_alerts.append({
                "alert_id": "alert_cleanse_preview",
                "severity": severity,
                "category": "data_cleaning",
                "message": f"Preview shows high-impact operations: {high_impact_rules} high-risk rules detected. Safety: {preview_analysis.get('execution_safety', 'UNKNOWN')}",
                "affected_fields_count": overall_impact.get("total_rules", 0),
                "recommendation": f"Review {high_impact_rules} high-impact rules before execution. {len(overall_impact.get('warnings', []))} warnings generated."
            })
        
        # Add impact issues
        for issue in preview_data.get("impact_issues", []):
            all_issues.append({
                "issue_id": f"issue_preview_{issue.get('rule_id', 'unknown')}",
                "agent_id": "cleanse-previewer",
                "field_name": issue.get("rule_id", ""),
                "issue_type": issue.get("issue_type", "preview_warning"),
                "severity": issue.get("severity", "medium"),
                "message": issue.get("description", "Preview impact detected")
            })
    
    # ==================== NULL HANDLER ALERTS & ISSUES ====================
    if null_handler_output.get("status") == "success":
        null_data = null_handler_output.get("data", {})
        cleaning_score = null_data.get("cleaning_score", {})
        null_analysis = null_data.get("null_analysis", {})
        
        overall_score = cleaning_score.get("overall_score", 0)
        
        if overall_score < 80:
            severity = "high" if overall_score < 60 else "medium"
            all_alerts.append({
                "alert_id": "alert_null_quality",
                "severity": severity,
                "category": "data_cleaning",
                "message": f"Null handling quality: {overall_score:.1f}/100 ({cleaning_score.get('quality_status', 'unknown')})",
                "affected_fields_count": len(null_analysis.get("columns_with_nulls", [])),
                "recommendation": f"Review null handling strategy. {len(null_analysis.get('recommendations', []))} columns require attention."
            })
        
        # Add field-level null issues
        for col in null_analysis.get("columns_with_nulls", []):
            col_summary = null_analysis.get("null_summary", {}).get(col, {})
            null_pct = col_summary.get("null_percentage", 0)
            
            if null_pct > 30:
                all_issues.append({
                    "issue_id": f"issue_null_{col}",
                    "agent_id": "null-handler",
                    "field_name": col,
                    "issue_type": "missing_values",
                    "severity": "high" if null_pct > 70 else "medium" if null_pct > 50 else "warning",
                    "message": f"High null percentage: {null_pct:.1f}% (null_count: {col_summary.get('null_count', 0)})"
                })
    
    # ==================== OUTLIER REMOVER ALERTS & ISSUES ====================
    if outlier_output.get("status") == "success":
        outlier_data = outlier_output.get("data", {})
        outlier_score = outlier_data.get("outlier_score", {})
        outlier_analysis = outlier_data.get("outlier_analysis", {})
        
        overall_score = outlier_score.get("overall_score", 0)
        
        if overall_score < 80:
            severity = "high" if overall_score < 60 else "medium"
            total_outliers = sum(
                col_data.get("outlier_count", 0)
                for col_data in outlier_analysis.get("outlier_summary", {}).values()
            )
            
            all_alerts.append({
                "alert_id": "alert_outlier_quality",
                "severity": severity,
                "category": "data_cleaning",
                "message": f"Outlier removal quality: {overall_score:.1f}/100 ({outlier_score.get('quality_status', 'unknown')})",
                "affected_fields_count": len(outlier_analysis.get("numeric_columns", [])),
                "recommendation": f"Review outlier handling. {total_outliers} outliers detected across {len(outlier_analysis.get('numeric_columns', []))} numeric columns."
            })
        
        # Add field-level outlier issues
        for col, col_analysis in outlier_analysis.get("outlier_summary", {}).items():
            outlier_pct = col_analysis.get("outlier_percentage", 0)
            outlier_count = col_analysis.get("outlier_count", 0)
            
            if outlier_pct > 5:
                all_issues.append({
                    "issue_id": f"issue_outlier_{col}",
                    "agent_id": "outlier-remover",
                    "field_name": col,
                    "issue_type": "outlier_detected",
                    "severity": "high" if outlier_pct > 20 else "medium" if outlier_pct > 10 else "warning",
                    "message": f"Outliers detected: {outlier_count} rows ({outlier_pct:.1f}%) using {col_analysis.get('method_used', 'unknown')} method"
                })
    
    # ==================== TYPE FIXER ALERTS & ISSUES ====================
    if type_fixer_output.get("status") == "success":
        type_data = type_fixer_output.get("data", {})
        fixing_score = type_data.get("fixing_score", {})
        type_analysis = type_data.get("type_analysis", {})
        
        overall_score = fixing_score.get("overall_score", 0)
        
        if overall_score < 80:
            severity = "high" if overall_score < 60 else "medium"
            all_alerts.append({
                "alert_id": "alert_type_fixing_quality",
                "severity": severity,
                "category": "data_cleaning",
                "message": f"Type fixing quality: {overall_score:.1f}/100 ({fixing_score.get('quality', 'unknown')})",
                "affected_fields_count": len(type_analysis.get("columns_with_issues", [])),
                "recommendation": f"Review type conversion strategy. {len(type_analysis.get('columns_with_issues', []))} columns have type mismatches."
            })
        
        # Add field-level type issues
        for col, col_analysis in type_analysis.get("type_summary", {}).items():
            suggested = col_analysis.get("suggested_type", "")
            current = col_analysis.get("current_type", "")
            
            all_issues.append({
                "issue_id": f"issue_type_{col}",
                "agent_id": "type-fixer",
                "field_name": col,
                "issue_type": "type_mismatch",
                "severity": "high" if len(col_analysis.get("issues", [])) > 1 else "medium",
                "message": f"Type mismatch: currently '{current}', should be '{suggested}'. {'; '.join(col_analysis.get('issues', []))}"
            })
    
    # ==================== QUARANTINE AGENT ALERTS & ISSUES ====================
    if quarantine_output.get("status") == "success":
        quarantine_data = quarantine_output.get("data", {})
        quality_score = quarantine_data.get("quality_score", {})
        quarantine_analysis = quarantine_data.get("quarantine_analysis", {})
        
        overall_score = quality_score.get("overall_score", 0)
        quarantined_records = quarantine_analysis.get("total_quarantined", 0)
        
        # Alert if quality score is low or significant data quarantined
        if overall_score < 80:
            severity = "high" if overall_score < 60 else "medium"
            all_alerts.append({
                "alert_id": "alert_quarantine_quality",
                "severity": severity,
                "category": "data_quality",
                "message": f"Data quality concern: {quarantined_records} problematic records identified and quarantined",
                "affected_fields_count": len(quarantine_analysis.get("issue_types", {})),
                "recommendation": f"Review {quarantined_records} quarantined records. Check for systematic data quality issues."
            })
        
        # Add issue-type specific alerts
        issue_types = quarantine_analysis.get("issue_types", {})
        for issue_type, count in issue_types.items():
            if count > 0:
                all_alerts.append({
                    "alert_id": f"alert_quarantine_{issue_type}",
                    "severity": "critical" if issue_type in ["missing_required_field", "corrupted_record", "schema_mismatch"] else "high" if count > 5 else "medium",
                    "category": "data_quality",
                    "message": f"{issue_type.replace('_', ' ').title()}: {count} records identified",
                    "affected_fields_count": count,
                    "recommendation": f"Investigate and correct the source of {issue_type.replace('_', ' ')} issues."
                })
        
        # Add row-level quarantine issues
        for issue in quarantine_analysis.get("quarantine_issues", [])[:50]:
            all_issues.append({
                "issue_id": f"issue_quarantine_{issue.get('row_index', 'unknown')}_{issue.get('column', 'unknown')}",
                "agent_id": "quarantine-agent",
                "field_name": issue.get("column", ""),
                "issue_type": issue.get("issue_type", "unknown"),
                "severity": issue.get("severity", "medium"),
                "message": issue.get("description", "Record quarantined due to data quality issue")
            })
    
    # ==================== DUPLICATE RESOLVER ALERTS & ISSUES ====================
    if duplicate_resolver_output.get("status") == "success":
        dedup_data = duplicate_resolver_output.get("data", {})
        dedup_score = dedup_data.get("dedup_score", {})
        duplicate_analysis = dedup_data.get("duplicate_analysis", {})
        
        overall_score = dedup_score.get("overall_score", 0)
        total_duplicates = duplicate_analysis.get("total_duplicates", 0)
        
        if total_duplicates > 0:
            severity = "high" if total_duplicates > len(duplicate_analysis.get("duplicate_summary", {})) * 10 else "medium"
            all_alerts.append({
                "alert_id": "alert_duplicates",
                "severity": severity,
                "category": "data_cleaning",
                "message": f"Duplicate records detected: {total_duplicates} duplicates found ({duplicate_analysis.get('duplicate_summary', {}).get('exact', {}).get('duplicate_percentage', 0):.1f}% of data)",
                "affected_fields_count": total_duplicates,
                "recommendation": f"Run duplicate resolver to remove {total_duplicates} duplicate records and improve data quality."
            })
        
        # Add duplicate issues per detection method
        for method, method_data in duplicate_analysis.get("duplicate_summary", {}).items():
            if isinstance(method_data, dict) and method_data.get("duplicate_count", 0) > 0:
                all_issues.append({
                    "issue_id": f"issue_duplicate_{method}",
                    "agent_id": "duplicate-resolver",
                    "field_name": method,
                    "issue_type": "duplicate_record",
                    "severity": "high" if method_data.get("duplicate_percentage", 0) > 5 else "medium",
                    "message": f"{method.replace('_', ' ').title()}: {method_data.get('duplicate_count', 0)} duplicates ({method_data.get('duplicate_percentage', 0):.2f}%)"
                })
    
    # ==================== FIELD STANDARDIZATION ALERTS & ISSUES ====================
    if field_standardization_output.get("status") == "success":
        standardization_data = field_standardization_output.get("data", {})
        standardization_score = standardization_data.get("standardization_score", {})
        standardization_analysis = standardization_data.get("standardization_analysis", {})
        
        overall_score = standardization_score.get("overall_score", 0)
        columns_standardized = standardization_analysis.get("columns_standardized", 0)
        improvements = standardization_analysis.get("improvements", {})
        variations_reduced = improvements.get("total_variations_reduced", 0)
        
        if overall_score < 80:
            severity = "high" if overall_score < 60 else "medium"
            all_alerts.append({
                "alert_id": "alert_field_standardization",
                "severity": severity,
                "category": "data_cleaning",
                "message": f"Field standardization quality: {overall_score:.1f}/100 ({standardization_data.get('quality_status', 'unknown')})",
                "affected_fields_count": columns_standardized,
                "recommendation": f"Review standardization strategy. {columns_standardized} columns processed with {variations_reduced} variations reduced."
            })
        
        # Add field-level standardization issues
        pre_analysis = standardization_analysis.get("pre_standardization", {})
        post_analysis = standardization_analysis.get("post_standardization", {})
        
        for col, col_improvements in improvements.get("column_improvements", {}).items():
            if col_improvements.get("improvement_percentage", 0) < 50:
                all_issues.append({
                    "issue_id": f"issue_standardization_{col}",
                    "agent_id": "field-standardization",
                    "field_name": col,
                    "issue_type": "standardization_incomplete",
                    "severity": "medium",
                    "message": f"Limited improvement in standardization: {col_improvements.get('improvement_percentage', 0):.1f}% improvement. Consider additional synonym mappings."
                })
    
    # ==================== GOVERNANCE ALERTS & ISSUES ====================
    if governance_output.get("status") == "success":
        governance_data = governance_output.get("data", {})
        governance_scores = governance_data.get("governance_scores", {})
        compliance_status = governance_data.get("compliance_status", "unknown")
        overall_score = governance_scores.get("overall", 0)
        
        if compliance_status != "compliant":
            severity = "high" if compliance_status == "non_compliant" else "medium"
            all_alerts.append({
                "alert_id": "alert_governance",
                "severity": severity,
                "category": "governance",
                "message": f"Governance compliance: {overall_score:.1f}/100 - Status: {compliance_status}",
                "affected_fields_count": len(governance_data.get("fields_analyzed", [])),
                "recommendation": f"Address governance gaps. Review lineage, consent, and classification requirements."
            })
        
        # Add governance issues
        for issue in governance_data.get("governance_issues", [])[:10]:
            all_issues.append({
                "issue_id": f"issue_gov_{issue.get('field_name', 'unknown')}",
                "agent_id": "governance-checker",
                "field_name": issue.get("field_name", ""),
                "issue_type": issue.get("issue_type", "governance_violation"),
                "severity": issue.get("severity", "medium"),
                "message": issue.get("description", "Governance issue detected")
            })
    
    # ==================== TEST COVERAGE ALERTS & ISSUES ====================
    if test_coverage_output.get("status") == "success":
        test_data = test_coverage_output.get("data", {})
        test_scores = test_data.get("test_coverage_scores", {})
        coverage_status = test_data.get("coverage_status", "unknown")
        overall_score = test_scores.get("overall", 0)
        
        if coverage_status != "excellent":
            severity = "high" if coverage_status == "needs_improvement" else "medium"
            all_alerts.append({
                "alert_id": "alert_test_coverage",
                "severity": severity,
                "category": "testing",
                "message": f"Test coverage: {overall_score:.1f}/100 - Status: {coverage_status}",
                "affected_fields_count": len(test_data.get("fields_analyzed", [])),
                "recommendation": "Improve test coverage for uniqueness, range, and format constraints."
            })
        
        # Add test coverage issues
        for issue in test_data.get("test_coverage_issues", [])[:10]:
            all_issues.append({
                "issue_id": f"issue_test_{issue.get('field_name', 'unknown')}",
                "agent_id": "test-coverage-agent",
                "field_name": issue.get("field_name", ""),
                "issue_type": issue.get("issue_type", "test_validation_failure"),
                "severity": issue.get("severity", "medium"),
                "message": issue.get("description", "Test coverage issue detected")
            })
    
    # ==================== GENERATE RECOMMENDATIONS ====================
    
    # Cleanse previewer recommendations
    if cleanse_previewer_output.get("status") == "success":
        preview_data = cleanse_previewer_output.get("data", {})
        preview_analysis = preview_data.get("preview_analysis", {})
        
        for rec in preview_analysis.get("recommendations", [])[:5]:
            all_recommendations.append({
                "recommendation_id": f"rec_preview_{rec.get('action', 'unknown')}",
                "agent_id": "cleanse-previewer",
                "field_name": ",".join(rec.get("affected_rules", [])) if "affected_rules" in rec else "multiple",
                "priority": rec.get("priority", "medium"),
                "recommendation": f"{rec.get('action', 'Unknown action')}: {rec.get('reason', '')}",
                "timeline": "immediate" if rec.get("priority") == "critical" else "1 week" if rec.get("priority") == "high" else "2 weeks"
            })
    
    # Quarantine recommendations
    if quarantine_output.get("status") == "success":
        quarantine_data = quarantine_output.get("data", {})
        quarantine_analysis = quarantine_data.get("quarantine_analysis", {})
        quality_score = quarantine_data.get("quality_score", {})
        quarantined_records = quarantine_analysis.get("total_quarantined", 0)
        
        if quarantined_records > 0:
            priority = "high" if quarantined_records > 100 else "medium"
            all_recommendations.append({
                "recommendation_id": "rec_quarantine_review",
                "agent_id": "quarantine-agent",
                "field_name": "multiple",
                "priority": priority,
                "recommendation": f"Review {quarantined_records} quarantined records. Investigate root causes of data quality issues.",
                "timeline": "1 week" if priority == "high" else "2 weeks"
            })
        
        # Issue-specific recommendations
        issue_types = quarantine_analysis.get("issue_types", {})
        for issue_type, count in issue_types.items():
            if count > 0:
                all_recommendations.append({
                    "recommendation_id": f"rec_quarantine_{issue_type}",
                    "agent_id": "quarantine-agent",
                    "field_name": issue_type,
                    "priority": "high" if issue_type in ["missing_required_field", "schema_mismatch"] else "medium",
                    "recommendation": f"Fix {issue_type.replace('_', ' ')} issues: {count} records affected. Implement validation at data source.",
                    "timeline": "1 week" if issue_type in ["missing_required_field", "schema_mismatch"] else "2 weeks"
                })
    
    # Null handling recommendations
    if null_handler_output.get("status") == "success":
        null_data = null_handler_output.get("data", {})
        null_analysis = null_data.get("null_analysis", {})
        
        for rec in null_analysis.get("recommendations", [])[:5]:
            all_recommendations.append({
                "recommendation_id": f"rec_null_{rec.get('column', 'unknown')}",
                "agent_id": "null-handler",
                "field_name": rec.get("column", ""),
                "priority": rec.get("priority", "medium"),
                "recommendation": f"{rec.get('action', 'Unknown action')}: {rec.get('reason', '')}",
                "timeline": "1 week" if rec.get("priority") == "high" else "2 weeks" if rec.get("priority") == "medium" else "3 weeks"
            })
    
    # Outlier handling recommendations
    if outlier_output.get("status") == "success":
        outlier_data = outlier_output.get("data", {})
        outlier_analysis = outlier_data.get("outlier_analysis", {})
        
        for rec in outlier_analysis.get("recommendations", [])[:5]:
            all_recommendations.append({
                "recommendation_id": f"rec_outlier_{rec.get('column', 'unknown')}",
                "agent_id": "outlier-remover",
                "field_name": rec.get("column", ""),
                "priority": rec.get("priority", "medium"),
                "recommendation": f"{rec.get('action', 'Unknown action')}: {rec.get('reason', '')}",
                "timeline": "1 week" if rec.get("priority") == "high" else "2 weeks" if rec.get("priority") == "medium" else "3 weeks"
            })
    
    # Type fixing recommendations
    if type_fixer_output.get("status") == "success":
        type_data = type_fixer_output.get("data", {})
        type_analysis = type_data.get("type_analysis", {})
        
        for rec in type_analysis.get("recommendations", [])[:5]:
            all_recommendations.append({
                "recommendation_id": f"rec_type_{rec.get('column', 'unknown')}",
                "agent_id": "type-fixer",
                "field_name": rec.get("column", ""),
                "priority": rec.get("priority", "medium"),
                "recommendation": f"Convert '{rec.get('column', '')}' to {rec.get('action', 'unknown type')} - {rec.get('reason', '')}",
                "timeline": "1 week" if rec.get("priority") == "high" else "2 weeks" if rec.get("priority") == "medium" else "3 weeks"
            })
    
    # Duplicate resolver recommendations
    if duplicate_resolver_output.get("status") == "success":
        dedup_data = duplicate_resolver_output.get("data", {})
        duplicate_analysis = dedup_data.get("duplicate_analysis", {})
        
        if duplicate_analysis.get("total_duplicates", 0) > 0:
            all_recommendations.append({
                "recommendation_id": "rec_duplicate_resolution",
                "agent_id": "duplicate-resolver",
                "field_name": "multiple",
                "priority": "high" if duplicate_analysis.get("total_duplicates", 0) > 100 else "medium",
                "recommendation": f"Remove {duplicate_analysis.get('total_duplicates', 0)} duplicate records to improve data quality and uniqueness",
                "timeline": "1 week"
            })
        
        for rec in duplicate_analysis.get("recommendations", [])[:3]:
            all_recommendations.append({
                "recommendation_id": f"rec_dedup_{rec.get('action', 'unknown')}",
                "agent_id": "duplicate-resolver",
                "field_name": "multiple",
                "priority": rec.get("priority", "medium"),
                "recommendation": rec.get("reason", ""),
                "timeline": "1 week" if rec.get("priority") == "high" else "2 weeks"
            })
    
    # Field standardization recommendations
    if field_standardization_output.get("status") == "success":
        standardization_data = field_standardization_output.get("data", {})
        standardization_analysis = standardization_data.get("standardization_analysis", {})
        
        for rec in standardization_analysis.get("recommendations", [])[:5]:
            all_recommendations.append({
                "recommendation_id": f"rec_standardization_{rec.get('column', 'unknown')}",
                "agent_id": "field-standardization",
                "field_name": rec.get("column", ""),
                "priority": rec.get("priority", "medium"),
                "recommendation": f"{rec.get('action', 'Unknown action')}: {rec.get('reason', '')}",
                "timeline": "1 week" if rec.get("priority") == "high" else "2 weeks" if rec.get("priority") == "medium" else "3 weeks"
            })
    
    # ==================== GENERATE EXECUTIVE SUMMARY ====================
    
    # Overall cleaning quality summary
    overall_quality = 0
    quality_count = 0
    
    if null_handler_output.get("status") == "success":
        null_score = null_handler_output.get("data", {}).get("cleaning_score", {}).get("overall_score", 0)
        overall_quality += null_score
        quality_count += 1
    
    if outlier_output.get("status") == "success":
        outlier_score = outlier_output.get("data", {}).get("outlier_score", {}).get("overall_score", 0)
        overall_quality += outlier_score
        quality_count += 1
    
    if type_fixer_output.get("status") == "success":
        type_score = type_fixer_output.get("data", {}).get("fixing_score", {}).get("overall_score", 0)
        overall_quality += type_score
        quality_count += 1
    
    if duplicate_resolver_output.get("status") == "success":
        dedup_score = duplicate_resolver_output.get("data", {}).get("dedup_score", {}).get("overall_score", 0)
        overall_quality += dedup_score
        quality_count += 1
    
    if field_standardization_output.get("status") == "success":
        standardization_score = field_standardization_output.get("data", {}).get("standardization_score", {}).get("overall_score", 0)
        overall_quality += standardization_score
        quality_count += 1
    
    if cleanse_previewer_output.get("status") == "success":
        preview_score = cleanse_previewer_output.get("data", {}).get("preview_score", {}).get("overall_score", 0)
        overall_quality += preview_score
        quality_count += 1
    
    if quality_count > 0:
        overall_quality = overall_quality / quality_count
        quality_grade = "A" if overall_quality >= 90 else "B" if overall_quality >= 80 else "C" if overall_quality >= 70 else "D" if overall_quality >= 60 else "F"
        quality_status = "excellent" if overall_quality >= 90 else "good" if overall_quality >= 75 else "fair"
        
        executive_summary.append({
            "summary_id": "exec_cleaning_quality",
            "title": "Data Cleaning Quality Score",
            "value": f"{overall_quality:.1f}",
            "status": quality_status,
            "description": f"Grade {quality_grade}: {overall_quality:.1f}/100"
        })
    
    # Governance compliance summary
    if governance_output.get("status") == "success":
        gov_score = governance_output.get("data", {}).get("governance_scores", {}).get("overall", 0)
        gov_status = governance_output.get("data", {}).get("compliance_status", "unknown")
        
        executive_summary.append({
            "summary_id": "exec_governance",
            "title": "Governance Compliance Status",
            "value": f"{gov_score:.1f}",
            "status": "compliant" if gov_status == "compliant" else "review_needed" if gov_status == "needs_review" else "non_compliant",
            "description": f"Compliance: {gov_status.replace('_', ' ').title()}"
        })
    
    # Test coverage summary
    if test_coverage_output.get("status") == "success":
        test_score = test_coverage_output.get("data", {}).get("test_coverage_scores", {}).get("overall", 0)
        test_status = test_coverage_output.get("data", {}).get("coverage_status", "unknown")
        
        executive_summary.append({
            "summary_id": "exec_test_coverage",
            "title": "Test Coverage Status",
            "value": f"{test_score:.1f}",
            "status": test_status,
            "description": f"Test Coverage: {test_status.replace('_', ' ').title()}"
        })
    
    # Issues and alerts summary
    executive_summary.append({
        "summary_id": "exec_summary_stats",
        "title": "Analysis Summary",
        "value": f"{len(all_alerts)}",
        "status": "warning" if len(all_alerts) > 0 else "success",
        "description": f"{len(all_alerts)} alerts | {len(all_issues)} issues | {len(all_recommendations)} recommendations"
    })
    
    # ==================== GENERATE AI ANALYSIS SUMMARY ====================
    # Build analysis text from alerts, issues, recommendations, and agent summaries
    analysis_text_parts = []
    
    # Add executive summary
    if executive_summary:
        analysis_text_parts.append("EXECUTIVE SUMMARY:")
        for item in executive_summary:
            analysis_text_parts.append(f"- {item.get('title', '')}: {item.get('description', '')}")
    
    # Add alerts
    if all_alerts:
        analysis_text_parts.append(f"\nALERTS ({len(all_alerts)} total):")
        for alert in all_alerts[:5]:
            analysis_text_parts.append(f"- {alert.get('severity', '').upper()}: {alert.get('message', '')}")
    
    # Add issues summary
    if all_issues:
        analysis_text_parts.append(f"\nISSUES ({len(all_issues)} total):")
        issue_by_type = {}
        for issue in all_issues:
            issue_type = issue.get('issue_type', 'unknown')
            issue_by_type[issue_type] = issue_by_type.get(issue_type, 0) + 1
        for issue_type, count in issue_by_type.items():
            analysis_text_parts.append(f"- {issue_type}: {count} occurrences")
    
    # Add recommendations summary
    if all_recommendations:
        analysis_text_parts.append(f"\nRECOMMENDATIONS ({len(all_recommendations)} total):")
        for rec in all_recommendations[:5]:
            analysis_text_parts.append(f"- {rec.get('priority', 'medium').upper()}: {rec.get('recommendation', '')}")
    
    # Add key metrics from agents
    analysis_text_parts.append("\nAGENT ANALYSIS RESULTS:")
    
    if cleanse_previewer_output.get("status") == "success":
        preview_score = cleanse_previewer_output.get("data", {}).get("preview_score", {}).get("overall_score", 0)
        rules_previewed = cleanse_previewer_output.get("summary_metrics", {}).get("total_rules_previewed", 0)
        safe_to_execute = cleanse_previewer_output.get("summary_metrics", {}).get("safe_to_execute", True)
        analysis_text_parts.append(f"- Cleanse Previewer: Preview Score {preview_score:.1f}/100 ({rules_previewed} rules analyzed, Safety: {'SAFE' if safe_to_execute else 'CAUTION'})")
    
    if quarantine_output.get("status") == "success":
        quarantine_score = quarantine_output.get("data", {}).get("quality_score", {}).get("overall_score", 0)
        quarantined_records = quarantine_output.get("summary_metrics", {}).get("quarantined_records", 0)
        analysis_text_parts.append(f"- Quarantine Agent: Quality Score {quarantine_score:.1f}/100 ({quarantined_records} problematic records isolated)")
    
    if null_handler_output.get("status") == "success":
        null_score = null_handler_output.get("data", {}).get("cleaning_score", {}).get("overall_score", 0)
        total_nulls = sum(
            col.get("null_count", 0) 
            for col in null_handler_output.get("data", {}).get("null_analysis", {}).get("null_summary", {}).values()
        )
        analysis_text_parts.append(f"- Null Handler: Quality Score {null_score:.1f}/100 (handled {total_nulls} null values)")
    
    if outlier_output.get("status") == "success":
        outlier_score = outlier_output.get("data", {}).get("outlier_score", {}).get("overall_score", 0)
        total_outliers = sum(
            col.get("outlier_count", 0)
            for col in outlier_output.get("data", {}).get("outlier_analysis", {}).get("outlier_summary", {}).values()
        )
        analysis_text_parts.append(f"- Outlier Remover: Quality Score {outlier_score:.1f}/100 ({total_outliers} outliers detected)")
    
    if type_fixer_output.get("status") == "success":
        type_score = type_fixer_output.get("data", {}).get("fixing_score", {}).get("overall_score", 0)
        type_issues_fixed = type_fixer_output.get("summary_metrics", {}).get("type_issues_fixed", 0)
        analysis_text_parts.append(f"- Type Fixer: Quality Score {type_score:.1f}/100 ({type_issues_fixed} type issues fixed)")
    
    if field_standardization_output.get("status") == "success":
        standardization_score = field_standardization_output.get("data", {}).get("standardization_score", {}).get("overall_score", 0)
        values_changed = field_standardization_output.get("summary_metrics", {}).get("values_changed", 0)
        variations_reduced = field_standardization_output.get("summary_metrics", {}).get("variations_reduced", 0)
        analysis_text_parts.append(f"- Field Standardization: Quality Score {standardization_score:.1f}/100 ({values_changed} values standardized, {variations_reduced} variations reduced)")
    
    if governance_output.get("status") == "success":
        gov_score = governance_output.get("data", {}).get("governance_scores", {}).get("overall", 0)
        compliance = governance_output.get("data", {}).get("compliance_status", "unknown")
        analysis_text_parts.append(f"- Governance Checker: {gov_score:.1f}/100, Compliance: {compliance}")
    
    if test_coverage_output.get("status") == "success":
        test_score = test_coverage_output.get("data", {}).get("test_coverage_scores", {}).get("overall", 0)
        coverage_status = test_coverage_output.get("data", {}).get("coverage_status", "unknown")
        analysis_text_parts.append(f"- Test Coverage: {test_score:.1f}/100, Status: {coverage_status}")
    
    # Combine all text
    complete_analysis_text = "\n".join(analysis_text_parts)
    
    # Generate summary using AI
    analysis_summary = {
        "status": "pending",
        "summary": "",
        "execution_time_ms": 0,
        "model_used": None
    }
    
    try:
        ai_generator = AnalysisSummaryAI()
        summary_result = ai_generator.generate_summary(
            analysis_text=complete_analysis_text,
            dataset_name="Data Cleaning Analysis"
        )
        analysis_summary = summary_result
    except Exception as e:
        # Fallback to rule-based summary if OpenAI is unavailable
        print(f"Warning: OpenAI summary generation failed: {str(e)}. Using fallback summary.")
        try:
            analysis_summary = {
                "status": "success",
                "summary": f"Data cleaning analysis completed with {len(all_alerts)} alerts and {len(all_recommendations)} recommendations. " +
                          f"Overall quality: {'Excellent' if overall_quality >= 90 else 'Good' if overall_quality >= 75 else 'Fair'}. " +
                          f"Key actions: {', '.join([rec.get('recommendation', '')[:50] for rec in all_recommendations[:2]])}.",
                "execution_time_ms": 0,
                "model_used": "fallback-rule-based"
            }
        except Exception as fallback_error:
            print(f"Error in fallback summary: {str(fallback_error)}")
            analysis_summary = {
                "status": "error",
                "summary": "Unable to generate summary",
                "execution_time_ms": 0,
                "model_used": None
            }
    
    # ==================== GENERATE ROUTING RECOMMENDATIONS ====================
    # Use routing AI agent to recommend next best tool
    routing_decisions = []
    try:
        from ai.routing_decision_ai import RoutingDecisionAI
        
        routing_ai = RoutingDecisionAI()
        routing_decisions = routing_ai.get_routing_decisions(
            current_tool="clean-my-data",
            agent_results=agent_results,
            primary_filename="data.csv",
            baseline_filename=None,
            current_parameters=None
        )
        
        print(f"Generated {len(routing_decisions)} routing recommendations")
    except Exception as e:
        print(f"Warning: Routing AI agent failed: {str(e)}")
        routing_decisions = []
    
    # ==================== GENERATE DOWNLOADS ====================
    # Use dedicated download module for comprehensive Excel and JSON exports
    
    # Collect cleaned files from agents
    cleaned_files = {}
    for agent_id in ["null-handler", "outlier-remover", "type-fixer", "duplicate-resolver", "field-standardization", "quarantine-agent"]:
        agent_output = agent_results.get(agent_id, {})
        if agent_output.get("status") == "success":
            if agent_id == "quarantine-agent":
                # For quarantine agent, collect both cleaned and quarantine files
                if "cleaned_file" in agent_output:
                    cleaned_files[agent_id] = agent_output["cleaned_file"]
                if "quarantine_file" in agent_output:
                    if agent_id not in cleaned_files:
                        cleaned_files[agent_id] = {}
                    cleaned_files[agent_id]["quarantine_file"] = agent_output["quarantine_file"]
            elif "cleaned_file" in agent_output:
                cleaned_files[agent_id] = agent_output["cleaned_file"]
    
    downloader = CleanMyDataDownloads()
    downloads = downloader.generate_downloads(
        agent_results=agent_results,
        analysis_id=analysis_id,
        execution_time_ms=execution_time_ms,
        alerts=all_alerts,
        issues=all_issues,
        recommendations=all_recommendations,
        cleaned_files=cleaned_files
    )
    
    # ==================== BUILD FINAL RESPONSE ====================
    
    return {
        "analysis_id": analysis_id,
        "tool": "clean-my-data",
        "status": "success",
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "execution_time_ms": execution_time_ms,
        "report": {
            "alerts": all_alerts,
            "issues": all_issues,
            "recommendations": all_recommendations,
            "executiveSummary": executive_summary,
            "analysisSummary": analysis_summary,
            "visualizations": [],
            "routing_decisions": routing_decisions,
            # Individual agent outputs (for detailed inspection)
            **{agent_id: output for agent_id, output in agent_results.items() if output.get("status") == "success"},
            # Downloads with Excel and JSON exports
            "downloads": downloads
        }
    }
