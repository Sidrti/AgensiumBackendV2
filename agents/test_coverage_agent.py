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
        
        # ==================== GENERATE ROW-LEVEL-ISSUES ====================
        row_level_issues = []
        
        # Check uniqueness constraints at row level
        unique_columns = parameters.get('unique_columns', [])
        for col in unique_columns:
            if col in df.columns:
                # Find rows with duplicate values
                dup_mask = df[col].duplicated(keep=False)
                for idx in df[dup_mask].index:
                    if len(row_level_issues) >= 1000:
                        break
                    row_level_issues.append({
                        "row_index": int(idx),
                        "column": str(col),
                        "issue_type": "test_coverage_gap",
                        "severity": "critical",
                        "message": f"Row {idx}, column '{col}': Duplicate value {df.loc[idx, col]} violates uniqueness constraint",
                        "value": str(df.loc[idx, col]),
                        "validation_type": "uniqueness"
                    })
        
        # Check range constraints at row level
        range_tests = parameters.get('range_tests', {})
        for col, constraints in range_tests.items():
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                min_val = constraints.get('min')
                max_val = constraints.get('max')
                
                for idx, val in df[col].items():
                    if len(row_level_issues) >= 1000:
                        break
                    if pd.isna(val):
                        continue
                    
                    out_of_range = False
                    if min_val is not None and val < min_val:
                        out_of_range = True
                    elif max_val is not None and val > max_val:
                        out_of_range = True
                    
                    if out_of_range:
                        row_level_issues.append({
                            "row_index": int(idx),
                            "column": str(col),
                            "issue_type": "validation_missing",
                            "severity": "warning",
                            "message": f"Row {idx}, column '{col}': Value {val} outside range [{min_val}, {max_val}]",
                            "value": float(val),
                            "bounds": {"lower": min_val, "upper": max_val},
                            "validation_type": "range"
                        })
        
        # Check format constraints at row level
        format_tests = parameters.get('format_tests', {})
        for col, pattern_info in format_tests.items():
            if col in df.columns:
                pattern = pattern_info.get('pattern') if isinstance(pattern_info, dict) else pattern_info
                description = pattern_info.get('description', 'format') if isinstance(pattern_info, dict) else 'format'
                
                try:
                    for idx, val in df[col].items():
                        if len(row_level_issues) >= 1000:
                            break
                        if pd.isna(val):
                            continue
                        
                        val_str = str(val)
                        matches = re.match(pattern, val_str)
                        
                        if not matches:
                            row_level_issues.append({
                                "row_index": int(idx),
                                "column": str(col),
                                "issue_type": "edge_case_uncovered",
                                "severity": "warning",
                                "message": f"Row {idx}, column '{col}': Value '{val_str}' does not match {description} pattern",
                                "value": val_str,
                                "expected_format": description,
                                "validation_type": "format"
                            })
                except re.error:
                    pass  # Skip invalid regex patterns
        
        # Check for edge cases (null, empty, boundary values)
        for idx, row in df.iterrows():
            if len(row_level_issues) >= 1000:
                break
            
            # Check for rows with many null values (edge case coverage gap)
            null_count = row.isna().sum()
            null_ratio = null_count / len(df.columns) if len(df.columns) > 0 else 0
            
            if null_ratio > 0.2:  # >20% nulls indicates potential edge case issue
                row_level_issues.append({
                    "row_index": int(idx),
                    "column": "N/A",
                    "issue_type": "edge_case_uncovered",
                    "severity": "info",
                    "message": f"Row {idx} has {null_ratio*100:.1f}% null values - edge case coverage may be insufficient",
                    "null_count": int(null_count),
                    "validation_type": "edge_case"
                })
        
        # Cap row-level-issues at 1000
        row_level_issues = row_level_issues[:1000]
        
        # Calculate issue summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {},
            "affected_rows": len(set(issue["row_index"] for issue in row_level_issues)),
            "affected_columns": list(set(issue["column"] for issue in row_level_issues if issue["column"] != "N/A"))
        }
        
        # Aggregate by type
        for issue in row_level_issues:
            issue_type = issue["issue_type"]
            issue_summary["by_type"][issue_type] = issue_summary["by_type"].get(issue_type, 0) + 1
        
        # Aggregate by severity
        for issue in row_level_issues:
            severity = issue["severity"]
            issue_summary["by_severity"][severity] = issue_summary["by_severity"].get(severity, 0) + 1
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # Alert 1: Overall test coverage status
        if coverage_status != "excellent":
            issues_found = len(test_issues)
            
            alerts.append({
                "alert_id": "alert_test_coverage_001_overall",
                "severity": "critical" if coverage_status == "needs_improvement" and overall_score < 60 else "high" if coverage_status == "needs_improvement" else "medium",
                "category": "test_coverage",
                "message": f"Test coverage status: {overall_score:.1f}/100 ({coverage_status.upper().replace('_', ' ')}). {issues_found} test(s) failing or needs attention.",
                "affected_fields_count": issues_found,
                "recommendation": f"Implement comprehensive data validation. {issues_found} test(s) require immediate attention."
            })
        
        # Alert 2: Uniqueness constraint coverage
        if uniqueness_score < 80:
            uniqueness_issues = len([i for i in test_issues if i.get("type") in ["uniqueness_violation", "missing_unique_column"]])
            alerts.append({
                "alert_id": "alert_test_uniqueness_coverage",
                "severity": "critical" if uniqueness_score < 60 else "high",
                "category": "uniqueness_tests",
                "message": f"Uniqueness test coverage: {uniqueness_score:.1f}/100. {uniqueness_issues} field(s) with duplicate/missing unique constraints.",
                "affected_fields_count": uniqueness_issues,
                "recommendation": "Define and enforce unique constraints on primary/candidate key fields to ensure data integrity"
            })
        elif uniqueness_score >= 90:
            alerts.append({
                "alert_id": "alert_test_uniqueness_excellent",
                "severity": "low",
                "category": "uniqueness_tests",
                "message": f"Uniqueness test coverage EXCELLENT: {uniqueness_score:.1f}/100. Primary keys properly validated.",
                "affected_fields_count": 0,
                "recommendation": "Maintain current uniqueness validation standards in production"
            })
        
        # Alert 3: Range constraint coverage
        if range_score < 80:
            range_issues = len([i for i in test_issues if i.get("type") in ["range_violation", "missing_range_column"]])
            alerts.append({
                "alert_id": "alert_test_range_coverage",
                "severity": "high" if range_score < 60 else "medium",
                "category": "range_tests",
                "message": f"Range test coverage: {range_score:.1f}/100. {range_issues} numeric field(s) with out-of-range values.",
                "affected_fields_count": range_issues,
                "recommendation": "Define acceptable value ranges (min/max) for numeric fields and implement validation"
            })
        elif range_score >= 90:
            alerts.append({
                "alert_id": "alert_test_range_excellent",
                "severity": "low",
                "category": "range_tests",
                "message": f"Range test coverage EXCELLENT: {range_score:.1f}/100. All numeric values within acceptable ranges.",
                "affected_fields_count": 0,
                "recommendation": "Continue monitoring numeric field value ranges in production"
            })
        
        # Alert 4: Format constraint coverage
        if format_score < 80:
            format_issues = len([i for i in test_issues if i.get("type") in ["format_violation", "missing_format_column"]])
            alerts.append({
                "alert_id": "alert_test_format_coverage",
                "severity": "high" if format_score < 60 else "medium",
                "category": "format_tests",
                "message": f"Format test coverage: {format_score:.1f}/100. {format_issues} field(s) with format violations.",
                "affected_fields_count": format_issues,
                "recommendation": "Establish format standards (email, phone, date, etc.) and implement pattern validation"
            })
        elif format_score >= 90:
            alerts.append({
                "alert_id": "alert_test_format_excellent",
                "severity": "low",
                "category": "format_tests",
                "message": f"Format test coverage EXCELLENT: {format_score:.1f}/100. All data formats properly standardized.",
                "affected_fields_count": 0,
                "recommendation": "Maintain current format validation standards"
            })
        
        # Alert 5: Flaky test detection
        flaky_tests = len([i for i in test_issues if i.get("type") == "flaky_test"])
        if flaky_tests > 0:
            alerts.append({
                "alert_id": "alert_test_flaky_tests",
                "severity": "high",
                "category": "test_reliability",
                "message": f"Flaky test patterns detected: {flaky_tests} test(s) inconsistent in results",
                "affected_fields_count": flaky_tests,
                "recommendation": "Review and stabilize inconsistent tests; implement deterministic validation logic"
            })
        
        # Alert 6: Test coverage by dimension analysis
        score_breakdown = {
            "uniqueness": uniqueness_score,
            "range": range_score,
            "format": format_score
        }
        lowest_coverage = min(score_breakdown, key=score_breakdown.get)
        lowest_score = score_breakdown[lowest_coverage]
        
        if max(score_breakdown.values()) - min(score_breakdown.values()) > 20:
            alerts.append({
                "alert_id": "alert_test_dimension_imbalance",
                "severity": "medium",
                "category": "test_completeness",
                "message": f"Test coverage imbalance detected: {lowest_coverage} ({lowest_score:.1f}/100) significantly lower than others",
                "affected_fields_count": 1,
                "recommendation": f"Balance test coverage across dimensions. Focus on improving {lowest_coverage} testing (currently {lowest_score:.1f}/100)"
            })
        
        # Alert 7: Edge-case coverage gaps
        edge_case_gaps = len([i for i in test_issues if "edge_case" in str(i.get("type", "")).lower()])
        if edge_case_gaps > 0 or overall_score < 75:
            alerts.append({
                "alert_id": "alert_test_edge_case_gaps",
                "severity": "medium",
                "category": "test_completeness",
                "message": f"Edge-case coverage gaps identified: {edge_case_gaps} gaps in boundary/special value testing",
                "affected_fields_count": edge_case_gaps,
                "recommendation": "Add comprehensive edge-case tests: null values, empty strings, min/max boundaries, special characters"
            })
        
        # Alert 8: Test coverage trend
        if overall_score >= 85:
            alerts.append({
                "alert_id": "alert_test_coverage_good",
                "severity": "low",
                "category": "test_quality",
                "message": f"Test coverage is good: {overall_score:.1f}/100. Data validation framework effective.",
                "affected_fields_count": 0,
                "recommendation": "Maintain current testing standards and continue incremental improvements"
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Add all test coverage issues with comprehensive categorization
        for idx, issue in enumerate(test_issues[:100]):  # Limit to 100 issues
            issue_type = issue.get("type", "test_coverage_issue")
            field = issue.get("field", "N/A")
            severity = issue.get("severity", "warning")
            message = issue.get("message", "Test coverage issue detected")
            
            # Add detailed severity mapping based on test type
            if issue_type == "uniqueness_violation":
                severity = "critical"
                test_category = "uniqueness"
            elif issue_type == "range_violation":
                severity = "high" if abs(issue.get("value", 0)) > issue.get("range_max", 999999) else "medium"
                test_category = "range"
            elif issue_type == "format_violation":
                severity = "high"
                test_category = "format"
            elif issue_type == "missing_unique_column":
                severity = "high"
                test_category = "uniqueness"
            elif issue_type == "missing_range_column":
                severity = "medium"
                test_category = "range"
            elif issue_type == "missing_format_column":
                severity = "medium"
                test_category = "format"
            elif issue_type == "flaky_test":
                severity = "high"
                test_category = "reliability"
            elif issue_type == "edge_case_gap":
                severity = "medium"
                test_category = "coverage"
            else:
                test_category = "other"
            
            # Enhanced issue details
            issue_detail_map = {
                "uniqueness_violation": f"Duplicate value(s) found in field '{field}' that should contain unique values",
                "range_violation": f"Value {issue.get('value', 'N/A')} in '{field}' outside acceptable range [{issue.get('range_min', 0)}, {issue.get('range_max', 100)}]",
                "format_violation": f"Value format mismatch in '{field}': expected {issue.get('expected_format', 'unknown')}, got {issue.get('actual_format', 'unknown')}",
                "missing_unique_column": f"Column '{field}' lacks unique constraint test definition",
                "missing_range_column": f"Column '{field}' lacks range validation test definition",
                "missing_format_column": f"Column '{field}' lacks format validation test definition",
                "flaky_test": f"Test for '{field}' shows inconsistent pass/fail patterns across runs",
                "edge_case_gap": f"Edge-case testing gap in '{field}': null/empty/min/max values not validated"
            }
            
            issue_message = issue_detail_map.get(issue_type, message)
            
            issues.append({
                "issue_id": f"issue_test_{test_category}_{field}_{idx}",
                "agent_id": "test-coverage-agent",
                "field_name": field,
                "issue_type": issue_type,
                "severity": severity,
                "message": issue_message,
                "test_category": test_category,
                "remediation_priority": "immediate" if severity == "critical" else "high" if severity == "high" else "medium"
            })
        
        # Add summary issues for missing test coverage dimensions
        if uniqueness_score < 70:
            issues.append({
                "issue_id": f"issue_test_uniqueness_coverage_gap",
                "agent_id": "test-coverage-agent",
                "field_name": "primary_key_fields",
                "issue_type": "test_coverage_gap",
                "severity": "critical",
                "message": f"Insufficient uniqueness test coverage ({uniqueness_score:.1f}%). Primary keys not properly validated.",
                "test_category": "uniqueness",
                "remediation_priority": "immediate"
            })
        
        if range_score < 70:
            issues.append({
                "issue_id": f"issue_test_range_coverage_gap",
                "agent_id": "test-coverage-agent",
                "field_name": "numeric_fields",
                "issue_type": "test_coverage_gap",
                "severity": "high",
                "message": f"Insufficient range test coverage ({range_score:.1f}%). Numeric value boundaries not validated.",
                "test_category": "range",
                "remediation_priority": "high"
            })
        
        if format_score < 70:
            issues.append({
                "issue_id": f"issue_test_format_coverage_gap",
                "agent_id": "test-coverage-agent",
                "field_name": "text_fields",
                "issue_type": "test_coverage_gap",
                "severity": "high",
                "message": f"Insufficient format test coverage ({format_score:.1f}%). Data format standards not enforced.",
                "test_category": "format",
                "remediation_priority": "high"
            })
        
        # Add cross-field validation gap issue
        if overall_score < 75:
            issues.append({
                "issue_id": f"issue_test_cross_field_validation",
                "agent_id": "test-coverage-agent",
                "field_name": "all_fields",
                "issue_type": "cross_field_validation_gap",
                "severity": "medium",
                "message": f"Cross-field validation coverage not tested. Related fields may have inconsistent states. Overall coverage: {overall_score:.1f}/100",
                "test_category": "coverage",
                "remediation_priority": "medium"
            })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        recommendations = []
        
        # Recommendation 1: Critical - Uniqueness constraint test coverage
        uniqueness_violations = [i for i in test_issues if i.get("type") == "uniqueness_violation"]
        if uniqueness_score < 80 or uniqueness_violations:
            fields_affected = [i.get("field") for i in uniqueness_violations[:3]]
            duplicate_counts = [i.get("duplicate_count", 0) for i in uniqueness_violations]
            total_duplicates = sum(duplicate_counts)
            
            recommendations.append({
                "recommendation_id": "rec_test_uniqueness_priority",
                "agent_id": "test-coverage-agent",
                "field_name": ", ".join(fields_affected) if fields_affected else "primary_key_fields",
                "priority": "critical" if uniqueness_score < 60 else "high",
                "recommendation": f"Implement comprehensive uniqueness testing: 1) Define unique constraint tests for all candidate key fields, 2) Remove/resolve {total_duplicates} duplicate value(s) detected, 3) Add automated uniqueness validation to data pipeline, 4) Document uniqueness requirements for each field",
                "timeline": "immediate" if uniqueness_score < 60 else "1 week",
                "estimated_effort_hours": 12 if uniqueness_score < 60 else 8,
                "owner": "Data Quality Team"
            })
        
        # Recommendation 2: High - Range constraint test coverage
        range_violations = [i for i in test_issues if i.get("type") == "range_violation"]
        if range_score < 80 or range_violations:
            fields_affected = [i.get("field") for i in range_violations[:3]]
            violation_counts = [i.get("violations", 0) for i in range_violations]
            total_violations = sum(violation_counts)
            
            recommendations.append({
                "recommendation_id": "rec_test_range_priority",
                "agent_id": "test-coverage-agent",
                "field_name": ", ".join(fields_affected) if fields_affected else "numeric_fields",
                "priority": "high" if range_score < 70 else "medium",
                "recommendation": f"Establish range validation testing: 1) Define min/max acceptable values for all numeric fields, 2) Correct {total_violations} out-of-range value(s) in {len(range_violations)} field(s), 3) Implement range boundary testing (min, max, boundary values), 4) Add automated range validation to data ingestion pipeline",
                "timeline": "1-2 weeks" if range_score < 70 else "2-3 weeks",
                "estimated_effort_hours": 10 if range_score < 70 else 6,
                "owner": "Data Engineering Team"
            })
        
        # Recommendation 3: High - Format constraint test coverage
        format_violations = [i for i in test_issues if i.get("type") == "format_violation"]
        if format_score < 80 or format_violations:
            fields_affected = [i.get("field") for i in format_violations[:3]]
            violation_counts = [i.get("violations", 0) for i in format_violations]
            total_violations = sum(violation_counts)
            
            recommendations.append({
                "recommendation_id": "rec_test_format_priority",
                "agent_id": "test-coverage-agent",
                "field_name": ", ".join(fields_affected) if fields_affected else "text_fields",
                "priority": "high" if format_score < 70 else "medium",
                "recommendation": f"Standardize format validation testing: 1) Define format patterns for all text/string fields (email, phone, date, etc.), 2) Standardize {total_violations} values not matching required formats, 3) Implement regex-based format validation tests, 4) Add format validation to data transformation pipeline",
                "timeline": "1-2 weeks" if format_score < 70 else "2-3 weeks",
                "estimated_effort_hours": 8 if format_score < 70 else 5,
                "owner": "Data Quality Team"
            })
        
        # Recommendation 4: High - Overall test coverage improvement strategy
        if coverage_status == "needs_improvement":
            recommendations.append({
                "recommendation_id": "rec_test_coverage_strategy",
                "agent_id": "test-coverage-agent",
                "field_name": "all_fields",
                "priority": "high" if overall_score < 75 else "medium",
                "recommendation": f"Implement comprehensive data validation framework (current coverage: {overall_score:.1f}/100): 1) Create test specification document for all critical fields, 2) Establish testing policies (uniqueness, range, format, cross-field), 3) Automate test execution in CI/CD pipeline, 4) Set coverage targets: uniqueness >90%, range >85%, format >80%, 5) Establish monitoring and alerting for test failures",
                "timeline": "2-3 weeks" if overall_score < 75 else "4 weeks",
                "estimated_effort_hours": 16 if overall_score < 75 else 12,
                "owner": "Data Quality Lead"
            })
        
        # Recommendation 5: Medium - Edge-case test coverage
        edge_case_gaps = len([i for i in test_issues if "edge_case" in str(i.get("type", "")).lower()])
        recommendations.append({
            "recommendation_id": "rec_test_edge_cases",
            "agent_id": "test-coverage-agent",
            "field_name": "all_fields",
            "priority": "high" if overall_score < 75 else "medium",
            "recommendation": f"Add comprehensive edge-case testing: 1) Test null/empty/NA values in all fields, 2) Test boundary values (min, max, limits) for numeric fields, 3) Test special characters and unicode in text fields, 4) Test date/time edge cases (leap years, DST), 5) Test zero values and negative numbers where applicable, 6) Document edge-case expectations per field",
            "timeline": "1-2 weeks",
            "estimated_effort_hours": 10,
            "owner": "QA/Test Automation Team"
        })
        
        # Recommendation 6: Medium - Test reliability and flaky test investigation
        flaky_tests = len([i for i in test_issues if i.get("type") == "flaky_test"])
        if flaky_tests > 0:
            recommendations.append({
                "recommendation_id": "rec_test_reliability",
                "agent_id": "test-coverage-agent",
                "field_name": "test_suite",
                "priority": "high",
                "recommendation": f"Stabilize test suite ({flaky_tests} flaky test(s) detected): 1) Investigate root causes of inconsistent test results, 2) Fix order dependencies and timing issues, 3) Use deterministic test data and mock external dependencies, 4) Add test isolation and setup/teardown, 5) Implement test result logging and debugging",
                "timeline": "1 week",
                "estimated_effort_hours": 12,
                "owner": "QA Automation Engineer"
            })
        
        # Recommendation 7: Medium - Cross-field validation testing
        if overall_score < 80:
            recommendations.append({
                "recommendation_id": "rec_test_cross_field",
                "agent_id": "test-coverage-agent",
                "field_name": "multiple_fields",
                "priority": "medium",
                "recommendation": "Implement cross-field validation testing: 1) Identify field relationships and dependencies (e.g., if status='active', then date_deactivated must be null), 2) Define cross-field validation rules, 3) Add automated tests for field combinations, 4) Test constraint violations and cascading updates, 5) Document inter-field dependencies",
                "timeline": "2-3 weeks",
                "estimated_effort_hours": 10,
                "owner": "Data Quality Team"
            })
        
        # Recommendation 8: Medium - Test coverage monitoring and continuous improvement
        recommendations.append({
            "recommendation_id": "rec_test_monitoring",
            "agent_id": "test-coverage-agent",
            "field_name": "all_fields",
            "priority": "medium",
            "recommendation": f"Establish test coverage monitoring (current: {overall_score:.1f}/100): 1) Create test coverage dashboard with uniqueness/range/format/edge-case metrics, 2) Set coverage targets by test dimension, 3) Implement weekly test coverage reviews, 4) Track coverage trends over time, 5) Alert on coverage regressions, 6) Document best practices and lessons learned",
            "timeline": "ongoing",
            "estimated_effort_hours": 6,
            "owner": "Data Quality Lead"
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
            "data": {
                "test_coverage_scores": {
                    "overall": round(overall_score, 1),
                    "uniqueness": round(uniqueness_score, 1),
                    "range": round(range_score, 1),
                    "format": round(format_score, 1)
                },
                "coverage_status": coverage_status,
                "total_records": len(df),
                "fields_analyzed": list(df.columns),
                "test_coverage_issues": test_issues,
                "row_level_issues": row_level_issues[:100],
                "issue_summary": issue_summary,
                "overrides": {
                    "uniqueness_weight": uniqueness_weight,
                    "range_weight": range_weight,
                    "format_weight": format_weight,
                    "excellent_threshold": excellent_threshold,
                    "good_threshold": good_threshold
                }
            },
            "alerts": alerts,
            "issues": issues,
            "recommendations": recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary
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
