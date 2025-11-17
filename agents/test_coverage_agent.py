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
            "data": test_coverage_data
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
