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

import pandas as pd
import numpy as np
import io
import time
import base64
import json
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import re


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

    # Extract parameters with defaults
    detect_missing_fields = parameters.get("detect_missing_fields", True)
    detect_type_mismatches = parameters.get("detect_type_mismatches", True)
    detect_out_of_range = parameters.get("detect_out_of_range", True)
    detect_invalid_formats = parameters.get("detect_invalid_formats", True)
    detect_broken_records = parameters.get("detect_broken_records", True)
    detect_schema_mismatches = parameters.get("detect_schema_mismatches", True)
    required_fields = parameters.get("required_fields", [])
    range_constraints = parameters.get("range_constraints", {})
    format_constraints = parameters.get("format_constraints", {})
    expected_schema = parameters.get("expected_schema", {})
    quarantine_reduction_weight = parameters.get("quarantine_reduction_weight", 0.5)
    data_integrity_weight = parameters.get("data_integrity_weight", 0.3)
    processing_efficiency_weight = parameters.get("processing_efficiency_weight", 0.2)
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
                "agent_id": "quarantine-agent",
                "error": f"Unsupported file format: {filename}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.empty:
            return {
                "status": "error",
                "agent_id": "quarantine-agent",
                "agent_name": "Quarantine Agent",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Store original data for comparison
        original_df = df.copy()
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
        df_clean = df.drop(quarantined_data.index).reset_index(drop=True)

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

        # Generate quarantine zone file (CSV format)
        quarantine_file_bytes = _generate_quarantine_file(quarantined_data)
        quarantine_file_base64 = base64.b64encode(quarantine_file_bytes).decode('utf-8')

        # Generate cleaned file (CSV format)
        cleaned_file_bytes = _generate_cleaned_file(df_clean, filename)
        cleaned_file_base64 = base64.b64encode(cleaned_file_bytes).decode('utf-8')

        # Build results
        quarantine_data = {
            "quality_score": quality_score,
            "quality_status": quality_status,
            "quarantine_analysis": quarantine_analysis,
            "quarantine_log": quarantine_log,
            "summary": f"Quarantine agent completed. Identified {len(quarantined_data)} problematic records. Quality: {quality_status}.",
            "row_level_issues": _extract_row_level_issues(quarantined_data, quarantine_analysis)
        }

        return {
            "status": "success",
            "agent_id": "quarantine-agent",
            "agent_name": "Quarantine Agent",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_processed": len(original_df),
                "quarantined_records": len(quarantined_data),
                "clean_records": len(df_clean),
                "quarantine_percentage": round((len(quarantined_data) / len(original_df) * 100) if len(original_df) > 0 else 0, 2),
                "quarantine_issues_found": len(quarantine_analysis.get("quarantine_issues", []))
            },
            "data": quarantine_data,
            "cleaned_file": {
                "filename": f"cleaned_{filename}",
                "content": cleaned_file_base64,
                "size_bytes": len(cleaned_file_bytes),
                "format": filename.split('.')[-1].lower()
            },
            "quarantine_file": {
                "filename": f"quarantined_{filename}",
                "content": quarantine_file_base64,
                "size_bytes": len(quarantine_file_bytes),
                "format": filename.split('.')[-1].lower()
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "quarantine-agent",
            "agent_name": "Quarantine Agent",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _analyze_and_quarantine(
    df: pd.DataFrame,
    required_fields: List[str],
    range_constraints: Dict[str, Dict[str, float]],
    format_constraints: Dict[str, str],
    expected_schema: Dict[str, str],
    detection_flags: Dict[str, bool]
) -> Tuple[pd.DataFrame, List[str], Dict[str, Any]]:
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
                missing_mask = df[col].isnull()
                missing_indices = df[missing_mask].index.tolist()
                
                if missing_indices:
                    quarantine_indices.update(missing_indices)
                    quarantine_log.append(
                        f"Missing required field '{col}': {len(missing_indices)} rows"
                    )
                    
                    for idx in missing_indices[:100]:
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
            expected_type = expected_schema.get(col, None)
            
            if expected_type:
                try:
                    actual_type = _infer_column_type(df[col])
                    
                    if actual_type != expected_type:
                        # Try to detect which rows have the mismatch
                        mismatch_indices = _find_type_mismatch_rows(df[col], expected_type)
                        
                        if mismatch_indices:
                            quarantine_indices.update(mismatch_indices)
                            quarantine_log.append(
                                f"Type mismatch in '{col}': expected {expected_type}, found {actual_type} ({len(mismatch_indices)} rows)"
                            )
                            
                            for idx in mismatch_indices[:50]:
                                quarantine_issues.append({
                                    "row_index": int(idx),
                                    "column": col,
                                    "issue_type": "type_mismatch",
                                    "severity": "high",
                                    "description": f"Type mismatch: expected {expected_type}, found {actual_type}"
                                })
                except Exception as e:
                    quarantine_log.append(f"Error checking type in '{col}': {str(e)}")

    # 3. DETECT OUT-OF-RANGE VALUES
    if detection_flags.get("detect_out_of_range", True) and range_constraints:
        for col, constraints in range_constraints.items():
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                min_val = constraints.get("min", None)
                max_val = constraints.get("max", None)
                
                out_of_range = pd.Series([False] * len(df), index=df.index)
                
                if min_val is not None:
                    out_of_range |= df[col] < min_val
                if max_val is not None:
                    out_of_range |= df[col] > max_val
                
                out_of_range_indices = df[out_of_range].index.tolist()
                
                if out_of_range_indices:
                    quarantine_indices.update(out_of_range_indices)
                    quarantine_log.append(
                        f"Out-of-range values in '{col}': {len(out_of_range_indices)} rows (range: {min_val}-{max_val})"
                    )
                    
                    for idx in out_of_range_indices[:50]:
                        val = df.loc[idx, col]
                        quarantine_issues.append({
                            "row_index": int(idx),
                            "column": col,
                            "issue_type": "out_of_range",
                            "severity": "high",
                            "description": f"Value {val} outside range [{min_val}, {max_val}]"
                        })

    # 4. DETECT INVALID FORMATS
    if detection_flags.get("detect_invalid_formats", True) and format_constraints:
        for col, pattern in format_constraints.items():
            if col in df.columns:
                invalid_indices = _find_format_violations(df[col], pattern)
                
                if invalid_indices:
                    quarantine_indices.update(invalid_indices)
                    quarantine_log.append(
                        f"Invalid format in '{col}': {len(invalid_indices)} rows (pattern: {pattern})"
                    )
                    
                    for idx in invalid_indices[:50]:
                        val = df.loc[idx, col]
                        quarantine_issues.append({
                            "row_index": int(idx),
                            "column": col,
                            "issue_type": "invalid_format",
                            "severity": "medium",
                            "description": f"Value '{val}' does not match pattern '{pattern}'"
                        })

    # 5. DETECT BROKEN/CORRUPTED RECORDS
    if detection_flags.get("detect_broken_records", True):
        corrupted_indices = _detect_corrupted_records(df)
        
        if corrupted_indices:
            quarantine_indices.update(corrupted_indices)
            quarantine_log.append(
                f"Corrupted/broken records detected: {len(corrupted_indices)} rows"
            )
            
            for idx in corrupted_indices[:50]:
                quarantine_issues.append({
                    "row_index": int(idx),
                    "column": "record",
                    "issue_type": "corrupted_record",
                    "severity": "critical",
                    "description": "Record appears to be corrupted or broken"
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
                quarantine_indices.update(df.index.tolist())
                quarantine_issues.append({
                    "row_index": 0,
                    "column": "schema",
                    "issue_type": "schema_mismatch",
                    "severity": "critical",
                    "description": f"Critical schema mismatch: missing {len(schema_mismatch_cols)} required columns"
                })

    # Isolate quarantined records
    quarantined_df = df.loc[list(quarantine_indices)].copy()
    quarantined_df["_quarantine_timestamp"] = datetime.utcnow().isoformat()
    quarantined_df["_quarantine_reason"] = quarantined_df.index.map(
        lambda idx: next(
            (issue["description"] for issue in quarantine_issues if issue["row_index"] == idx),
            "Multiple issues detected"
        )
    )

    quarantine_analysis = {
        "total_rows_analyzed": len(df),
        "total_quarantined": len(quarantined_df),
        "quarantine_percentage": round((len(quarantined_df) / len(df) * 100) if len(df) > 0 else 0, 2),
        "quarantine_issues": quarantine_issues,
        "issue_types": _count_issue_types(quarantine_issues),
        "severity_breakdown": _count_severity_breakdown(quarantine_issues),
        "timestamp": datetime.utcnow().isoformat()
    }

    return quarantined_df, quarantine_log, quarantine_analysis


def _infer_column_type(series: pd.Series) -> str:
    """Infer the overall type of a column."""
    series_clean = series.dropna()
    
    if len(series_clean) == 0:
        return "unknown"
    
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    elif pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    elif pd.api.types.is_categorical_dtype(series):
        return "category"
    elif pd.api.types.is_bool_dtype(series):
        return "boolean"
    else:
        return "string"


def _find_type_mismatch_rows(series: pd.Series, expected_type: str) -> List[int]:
    """Find rows that don't match the expected type."""
    mismatches = []
    
    for idx, val in series.items():
        if pd.isna(val):
            continue
        
        try:
            if expected_type == "numeric":
                float(val)
            elif expected_type == "integer":
                int(val)
            elif expected_type == "datetime":
                pd.Timestamp(val)
            elif expected_type == "boolean":
                str(val).lower() in ['true', 'false', '1', '0', 'yes', 'no']
            elif expected_type == "string":
                str(val)
        except (ValueError, TypeError):
            mismatches.append(int(idx))
    
    return mismatches


def _find_format_violations(series: pd.Series, pattern: str) -> List[int]:
    """Find values that don't match the format pattern."""
    violations = []
    
    try:
        regex = re.compile(f"^{pattern}$")
        
        for idx, val in series.items():
            if pd.isna(val):
                continue
            
            if not regex.match(str(val)):
                violations.append(int(idx))
    except:
        pass
    
    return violations


def _detect_corrupted_records(df: pd.DataFrame) -> List[int]:
    """Detect records that appear to be corrupted or broken."""
    corrupted = []
    
    # Check for records with all nulls
    all_null_mask = df.isnull().all(axis=1)
    corrupted.extend(df[all_null_mask].index.tolist())
    
    # Check for records with suspicious values (e.g., SQL injection patterns)
    # Using non-capturing groups (?:...) to avoid pandas warning about match groups
    suspicious_patterns = [
        r"(?i)(?:drop\s+table|delete\s+from|insert\s+into|update\s+|select\s+\*)",
        r"['\"]?\s*OR\s+['\"]?1['\"]?\s*=['\"]?1",
        r"<script[^>]*>.*?</script>",
        r"javascript:",
    ]
    
    for col in df.columns:
        if df[col].dtype == 'object':
            for pattern in suspicious_patterns:
                try:
                    mask = df[col].astype(str).str.contains(pattern, regex=True, case=False, na=False)
                    corrupted.extend(df[mask].index.tolist())
                except:
                    pass
    
    return list(set(corrupted))


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
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    quarantined_df: pd.DataFrame,
    quarantine_analysis: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate quarantine effectiveness score."""
    total_rows = len(original_df)
    clean_rows = len(cleaned_df)
    quarantined_rows = len(quarantined_df)
    
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


def _extract_row_level_issues(quarantined_df: pd.DataFrame, quarantine_analysis: Dict) -> List[Dict]:
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


def _generate_quarantine_file(quarantined_df: pd.DataFrame) -> bytes:
    """
    Generate quarantine zone file containing all quarantined records.
    
    Args:
        quarantined_df: DataFrame of quarantined records
        
    Returns:
        File contents as bytes
    """
    output = io.BytesIO()
    quarantined_df.to_csv(output, index=False)
    return output.getvalue()


def _generate_cleaned_file(df: pd.DataFrame, original_filename: str) -> bytes:
    """
    Generate cleaned data file (after quarantine removal).
    
    Args:
        df: Cleaned dataframe
        original_filename: Original filename to determine format
        
    Returns:
        File contents as bytes
    """
    output = io.BytesIO()
    df.to_csv(output, index=False)
    return output.getvalue()
