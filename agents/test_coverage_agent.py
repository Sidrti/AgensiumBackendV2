"""
Test Coverage Agent

Validates data test coverage including uniqueness, range, and format constraints.
Input: CSV/JSON/XLSX file (primary)
Output: Standardized test coverage validation results
"""

import pandas as pd
import numpy as np
import io
import time
import re
from typing import Dict, Any, Optional


def execute_test_coverage(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Check data test coverage compliance.

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
    uniqueness_weight = parameters.get("uniqueness_weight", 0.4)
    range_weight = parameters.get("range_weight", 0.3)
    format_weight = parameters.get("format_weight", 0.3)
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
                "agent_id": "test-coverage-agent",
                "error": f"Unsupported file format: {filename}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.empty:
            return {
                "status": "error",
                "agent_id": "test-coverage-agent",
                "agent_name": "Test Coverage Agent",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Perform test coverage validation
        uniqueness_score = _test_uniqueness(df, parameters)
        range_score = _test_ranges(df, parameters)
        format_score = _test_formats(df, parameters)

        # Calculate overall test coverage score
        overall_score = (
            uniqueness_score * uniqueness_weight +
            range_score * range_weight +
            format_score * format_weight
        )

        # Determine test coverage status
        if overall_score >= excellent_threshold:
            coverage_status = "excellent"
        elif overall_score >= good_threshold:
            coverage_status = "good"
        else:
            coverage_status = "needs_improvement"

        # Identify test coverage issues
        test_issues = _identify_test_coverage_issues(df, parameters)

        # Build results
        test_coverage_data = {
            "test_coverage_scores": {
                "overall": round(overall_score, 1),
                "uniqueness": round(uniqueness_score, 1),
                "range": round(range_score, 1),
                "format": round(format_score, 1)
            },
            "coverage_status": coverage_status,
            "total_records": len(df),
            "fields_analyzed": list(df.columns),
            "test_coverage_issues": test_issues
        }
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        if coverage_status != "excellent":
            issues_found = len(test_issues)
            
            alerts.append({
                "alert_id": "alert_test_coverage_001",
                "severity": "high" if coverage_status == "needs_improvement" else "medium",
                "category": "test_coverage",
                "message": f"Test coverage: {overall_score:.1f}/100 ({coverage_status.upper().replace('_', ' ')})",
                "affected_fields_count": issues_found,
                "recommendation": f"Improve test coverage. {issues_found} test(s) failing or missing."
            })
        
        # Component-specific alerts
        if uniqueness_score < 80:
            uniqueness_issues = len([i for i in test_issues if i.get("type") in ["uniqueness_violation", "missing_unique_column"]])
            alerts.append({
                "alert_id": "alert_test_uniqueness",
                "severity": "critical" if uniqueness_score < 60 else "high",
                "category": "uniqueness_tests",
                "message": f"Uniqueness test score: {uniqueness_score:.1f}/100",
                "affected_fields_count": uniqueness_issues,
                "recommendation": "Address uniqueness constraint violations to ensure data integrity"
            })
        
        if range_score < 80:
            range_issues = len([i for i in test_issues if i.get("type") in ["range_violation", "missing_range_column"]])
            alerts.append({
                "alert_id": "alert_test_range",
                "severity": "high" if range_score < 60 else "medium",
                "category": "range_tests",
                "message": f"Range test score: {range_score:.1f}/100",
                "affected_fields_count": range_issues,
                "recommendation": "Review and correct values outside expected ranges"
            })
        
        if format_score < 80:
            format_issues = len([i for i in test_issues if i.get("type") in ["format_violation", "missing_format_column"]])
            alerts.append({
                "alert_id": "alert_test_format",
                "severity": "high" if format_score < 60 else "medium",
                "category": "format_tests",
                "message": f"Format test score: {format_score:.1f}/100",
                "affected_fields_count": format_issues,
                "recommendation": "Standardize data formats to match expected patterns"
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Add test coverage issues
        for issue in test_issues:
            issue_type = issue.get("type", "test_coverage_issue")
            field = issue.get("field", "N/A")
            severity = issue.get("severity", "warning")
            message = issue.get("message", "Test coverage issue detected")
            
            issues.append({
                "issue_id": f"issue_test_coverage_{issue_type}_{field}",
                "agent_id": "test-coverage-agent",
                "field_name": field,
                "issue_type": issue_type,
                "severity": severity,
                "message": message
            })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        recommendations = []
        
        # Test coverage recommendations based on critical/high severity issues
        critical_issues = [i for i in test_issues if i.get("severity") == "critical"][:5]
        for issue in critical_issues:
            field = issue.get("field", "N/A")
            issue_type = issue.get("type", "test_coverage_issue")
            message = issue.get("message", "")
            
            recommendations.append({
                "recommendation_id": f"rec_test_{issue_type}_{field}",
                "agent_id": "test-coverage-agent",
                "field_name": field,
                "priority": "high",
                "recommendation": f"Fix test coverage issue: {message}",
                "timeline": "1 week"
            })
        
        # Component-based recommendations
        if uniqueness_score < 80:
            uniqueness_violations = [i for i in test_issues if i.get("type") == "uniqueness_violation"]
            if uniqueness_violations:
                fields_affected = [i.get("field") for i in uniqueness_violations]
                duplicate_counts = [i.get("duplicate_count", 0) for i in uniqueness_violations]
                total_duplicates = sum(duplicate_counts)
                
                recommendations.append({
                    "recommendation_id": "rec_test_uniqueness",
                    "agent_id": "test-coverage-agent",
                    "field_name": ", ".join(fields_affected[:3]),
                    "priority": "critical",
                    "recommendation": f"Remove {total_duplicates} duplicate value(s) from {len(uniqueness_violations)} field(s) that should be unique",
                    "timeline": "1 week"
                })
        
        if range_score < 80:
            range_violations = [i for i in test_issues if i.get("type") == "range_violation"]
            if range_violations:
                fields_affected = [i.get("field") for i in range_violations]
                violation_counts = [i.get("violations", 0) for i in range_violations]
                total_violations = sum(violation_counts)
                
                recommendations.append({
                    "recommendation_id": "rec_test_range",
                    "agent_id": "test-coverage-agent",
                    "field_name": ", ".join(fields_affected[:3]),
                    "priority": "high",
                    "recommendation": f"Correct {total_violations} value(s) in {len(range_violations)} field(s) that are outside expected ranges",
                    "timeline": "1-2 weeks"
                })
        
        if format_score < 80:
            format_violations = [i for i in test_issues if i.get("type") == "format_violation"]
            if format_violations:
                fields_affected = [i.get("field") for i in format_violations]
                violation_counts = [i.get("violations", 0) for i in format_violations]
                total_violations = sum(violation_counts)
                
                recommendations.append({
                    "recommendation_id": "rec_test_format",
                    "agent_id": "test-coverage-agent",
                    "field_name": ", ".join(fields_affected[:3]),
                    "priority": "high",
                    "recommendation": f"Standardize {total_violations} value(s) in {len(format_violations)} field(s) to match expected formats",
                    "timeline": "1-2 weeks"
                })
        
        # Overall test coverage recommendation
        if coverage_status == "needs_improvement":
            recommendations.append({
                "recommendation_id": "rec_test_coverage_overall",
                "agent_id": "test-coverage-agent",
                "field_name": "entire dataset",
                "priority": "high",
                "recommendation": f"Test coverage needs improvement ({overall_score:.1f}/100). Implement data validation rules and quality checks to ensure data integrity",
                "timeline": "2-3 weeks"
            })
        
        # Missing column recommendations
        missing_unique_cols = [i for i in test_issues if i.get("type") == "missing_unique_column"]
        if missing_unique_cols:
            recommendations.append({
                "recommendation_id": "rec_test_missing_unique",
                "agent_id": "test-coverage-agent",
                "field_name": ", ".join([i.get("field") for i in missing_unique_cols]),
                "priority": "high",
                "recommendation": f"{len(missing_unique_cols)} expected unique column(s) not found. Verify schema and add missing fields",
                "timeline": "1 week"
            })
        
        missing_range_cols = [i for i in test_issues if i.get("type") == "missing_range_column"]
        if missing_range_cols:
            recommendations.append({
                "recommendation_id": "rec_test_missing_range",
                "agent_id": "test-coverage-agent",
                "field_name": ", ".join([i.get("field") for i in missing_range_cols]),
                "priority": "medium",
                "recommendation": f"{len(missing_range_cols)} expected range test column(s) not found. Verify schema and add missing fields",
                "timeline": "1-2 weeks"
            })
        
        missing_format_cols = [i for i in test_issues if i.get("type") == "missing_format_column"]
        if missing_format_cols:
            recommendations.append({
                "recommendation_id": "rec_test_missing_format",
                "agent_id": "test-coverage-agent",
                "field_name": ", ".join([i.get("field") for i in missing_format_cols]),
                "priority": "medium",
                "recommendation": f"{len(missing_format_cols)} expected format test column(s) not found. Verify schema and add missing fields",
                "timeline": "1-2 weeks"
            })

        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = []
        
        # Test Coverage
        executive_summary.append({
            "summary_id": "exec_test_coverage",
            "title": "Test Coverage",
            "value": str(round(overall_score, 1)),
            "status": "excellent" if coverage_status == "excellent" else "good" if coverage_status == "good" else "needs_improvement",
            "description": f"{overall_score:.1f}/100 - {coverage_status.upper().replace('_', ' ')}"
        })
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_text_parts = []
        ai_analysis_text_parts.append(f"TEST COVERAGE: {coverage_status.upper().replace('_', ' ')} ({overall_score:.1f}/100)")
        ai_analysis_text_parts.append(f"- Uniqueness Tests: {uniqueness_score:.1f}/100")
        ai_analysis_text_parts.append(f"- Range Tests: {range_score:.1f}/100")
        ai_analysis_text_parts.append(f"- Format Tests: {format_score:.1f}/100")
        
        if len(test_issues) > 0:
            ai_analysis_text_parts.append(f"- {len(test_issues)} test issue(s) detected")
            
            # Critical issues
            critical_test_issues = [i for i in test_issues if i.get("severity") == "critical"]
            if critical_test_issues:
                ai_analysis_text_parts.append(f"  • {len(critical_test_issues)} critical test failure(s)")
            
            # Uniqueness violations
            uniqueness_issues = [i for i in test_issues if i.get("type") == "uniqueness_violation"]
            if uniqueness_issues:
                ai_analysis_text_parts.append(f"  • {len(uniqueness_issues)} uniqueness constraint violation(s)")
            
            # Range violations
            range_issues = [i for i in test_issues if i.get("type") == "range_violation"]
            if range_issues:
                ai_analysis_text_parts.append(f"  • {len(range_issues)} range constraint violation(s)")
            
            # Format violations
            format_issues = [i for i in test_issues if i.get("type") == "format_violation"]
            if format_issues:
                ai_analysis_text_parts.append(f"  • {len(format_issues)} format constraint violation(s)")
        
        if coverage_status == "excellent":
            ai_analysis_text_parts.append("- All test validations passed")
        else:
            ai_analysis_text_parts.append("- Data validation improvements required")
        
        ai_analysis_text = "\n".join(ai_analysis_text_parts)

        return {
            "status": "success",
            "agent_id": "test-coverage-agent",
            "agent_name": "Test Coverage Agent",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_records": len(df),
                "total_fields": len(df.columns),
                "test_coverage_score": round(overall_score, 1),
                "coverage_status": coverage_status,
                "issues_found": len(test_issues)
            },
            "data": test_coverage_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "test-coverage-agent",
            "agent_name": "Test Coverage Agent",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _test_uniqueness(df: pd.DataFrame, config: Dict[str, Any]) -> float:
    """
    Test uniqueness constraints on specified columns.
    """
    score = 100.0
    unique_columns = config.get('unique_columns', [])

    if not unique_columns:
        return score

    for col in unique_columns:
        if col not in df.columns:
            score -= 20  # Deduct for missing column
            continue

        duplicate_count = df[col].duplicated().sum()
        if duplicate_count > 0:
            duplicate_pct = (duplicate_count / len(df)) * 100
            deduction = min(25, duplicate_pct)
            score -= deduction

    return max(0, score)


def _test_ranges(df: pd.DataFrame, config: Dict[str, Any]) -> float:
    """
    Test range constraints on numeric columns.
    """
    score = 100.0
    range_tests = config.get('range_tests', {})

    if not range_tests:
        return score

    for col, constraints in range_tests.items():
        if col not in df.columns:
            score -= 15  # Deduct for missing column
            continue

        if not pd.api.types.is_numeric_dtype(df[col]):
            score -= 10  # Deduct for non-numeric column
            continue

        min_val = constraints.get('min')
        max_val = constraints.get('max')

        col_data = df[col].dropna()
        violations = 0

        if min_val is not None:
            violations += (col_data < min_val).sum()

        if max_val is not None:
            violations += (col_data > max_val).sum()

        if violations > 0:
            total_valid = len(col_data)
            violation_pct = (violations / total_valid * 100) if total_valid > 0 else 0
            deduction = min(20, violation_pct)
            score -= deduction

    return max(0, score)


def _test_formats(df: pd.DataFrame, config: Dict[str, Any]) -> float:
    """
    Test format constraints using regex patterns.
    """
    score = 100.0
    format_tests = config.get('format_tests', {})

    if not format_tests:
        return score

    for col, pattern_info in format_tests.items():
        if col not in df.columns:
            score -= 15  # Deduct for missing column
            continue

        pattern = pattern_info.get('pattern') if isinstance(pattern_info, dict) else pattern_info

        try:
            col_data = df[col].dropna().astype(str)
            matches = col_data.str.match(pattern, na=False)
            violations = (~matches).sum()

            if violations > 0:
                total_valid = len(col_data)
                violation_pct = (violations / total_valid * 100) if total_valid > 0 else 0
                deduction = min(15, violation_pct)
                score -= deduction

        except re.error:
            score -= 5  # Deduct for invalid regex

    return max(0, score)


def _identify_test_coverage_issues(df: pd.DataFrame, config: Dict[str, Any]) -> list:
    """
    Identify specific test coverage issues in the data.
    """
    issues = []

    # Check uniqueness constraints
    unique_columns = config.get('unique_columns', [])
    for col in unique_columns:
        if col not in df.columns:
            issues.append({
                "type": "missing_unique_column",
                "field": col,
                "severity": "critical",
                "message": f"Required unique column '{col}' not found"
            })
        else:
            duplicate_count = df[col].duplicated().sum()
            if duplicate_count > 0:
                issues.append({
                    "type": "uniqueness_violation",
                    "field": col,
                    "severity": "critical",
                    "message": f"Column '{col}' has {duplicate_count} duplicate values",
                    "duplicate_count": int(duplicate_count)
                })

    # Check range constraints
    range_tests = config.get('range_tests', {})
    for col, constraints in range_tests.items():
        if col not in df.columns:
            issues.append({
                "type": "missing_range_column",
                "field": col,
                "severity": "warning",
                "message": f"Range test column '{col}' not found"
            })
        elif pd.api.types.is_numeric_dtype(df[col]):
            min_val = constraints.get('min')
            max_val = constraints.get('max')

            col_data = df[col].dropna()
            violations = 0

            if min_val is not None:
                violations += (col_data < min_val).sum()

            if max_val is not None:
                violations += (col_data > max_val).sum()

            if violations > 0:
                issues.append({
                    "type": "range_violation",
                    "field": col,
                    "severity": "warning",
                    "message": f"Column '{col}' has {violations} values outside range [{min_val}, {max_val}]",
                    "violations": int(violations)
                })

    # Check format constraints
    format_tests = config.get('format_tests', {})
    for col, pattern_info in format_tests.items():
        if col not in df.columns:
            issues.append({
                "type": "missing_format_column",
                "field": col,
                "severity": "warning",
                "message": f"Format test column '{col}' not found"
            })
        else:
            pattern = pattern_info.get('pattern') if isinstance(pattern_info, dict) else pattern_info
            description = pattern_info.get('description', 'format') if isinstance(pattern_info, dict) else 'format'

            try:
                col_data = df[col].dropna().astype(str)
                matches = col_data.str.match(pattern, na=False)
                violations = (~matches).sum()

                if violations > 0:
                    issues.append({
                        "type": "format_violation",
                        "field": col,
                        "severity": "warning",
                        "message": f"Column '{col}' has {violations} values not matching {description} pattern",
                        "violations": int(violations)
                    })

            except re.error as e:
                issues.append({
                    "type": "invalid_regex_pattern",
                    "field": col,
                    "severity": "warning",
                    "message": f"Invalid regex pattern for column '{col}': {str(e)}"
                })

    return issues
