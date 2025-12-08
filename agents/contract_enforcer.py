"""
Contract Enforcer Agent

Enforces predefined data contracts to ensure data is strictly compliant with 
external system requirements. Acts as a quality control gateway for data integration.

Enforcement Categories:
I. Structural (Schema) Contract Enforcement:
   - Missing required columns
   - Extra unspecified columns
   - Incorrect data types
   - Incorrect column naming

II. Value (Content) Contract Enforcement:
   - Invalid value sets
   - Out-of-bounds ranges
   - Incorrect format/regex
   - Uniqueness violations

Input: CSV file (primary) + Contract Definition (JSON)
Output: Enforcement results with violations, transformations applied, and compliance status
"""

import polars as pl
import numpy as np
import io
import time
import re
import base64
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime


def execute_contract_enforcer(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Enforce data contract on dataset.

    Args:
        file_contents: File bytes (read as binary)
        filename: Original filename (used to detect format)
        parameters: Agent parameters including contract definition

    Returns:
        Standardized output dictionary with enforcement results
    """

    start_time = time.time()
    
    # Handle parameters being a string (JSON)
    if isinstance(parameters, str):
        try:
            parameters = json.loads(parameters)
        except Exception as e:
             return {
                "status": "error",
                "agent_id": "contract-enforcer",
                "error": f"Parameters is a string but failed to parse as JSON: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

    parameters = parameters or {}

    # Extract contract and parameters
    contract = parameters.get("contract", {})
    
    # Handle contract being a string (JSON)
    if isinstance(contract, str):
        try:
            contract = json.loads(contract)
        except Exception as e:
             return {
                "status": "error",
                "agent_id": "contract-enforcer",
                "error": f"Contract parameter is a string but failed to parse as JSON: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

    auto_transform = parameters.get("auto_transform", True)
    strict_mode = parameters.get("strict_mode", False)  # If True, fail on first violation
    drop_extra_columns = parameters.get("drop_extra_columns", True)
    rename_columns = parameters.get("rename_columns", True)
    cast_types = parameters.get("cast_types", True)
    enforce_values = parameters.get("enforce_values", True)
    default_value_strategy = parameters.get("default_value_strategy", "null")  # null, default, drop
    
    # Scoring weights
    structural_compliance_weight = parameters.get("structural_compliance_weight", 0.4)
    value_compliance_weight = parameters.get("value_compliance_weight", 0.4)
    transformation_success_weight = parameters.get("transformation_success_weight", 0.2)
    excellent_threshold = parameters.get("excellent_threshold", 95)
    good_threshold = parameters.get("good_threshold", 80)

    try:
        # Read file - CSV only
        if not filename.endswith('.csv'):
            return {
                "status": "error",
                "agent_id": "contract-enforcer",
                "error": f"Unsupported file format: {filename}. Only CSV files are supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        try:
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000, truncate_ragged_lines=True)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": "contract-enforcer",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.height == 0:
            return {
                "status": "error",
                "agent_id": "contract-enforcer",
                "agent_name": "Contract Enforcer",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate contract
        if not contract:
            return {
                "status": "error",
                "agent_id": "contract-enforcer",
                "agent_name": "Contract Enforcer",
                "error": "No contract definition provided. Please specify a contract in parameters.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        original_df = df.clone()
        total_rows = df.height
        total_columns = len(df.columns)
        
        # Initialize tracking
        violations = []
        transformations = []
        critical_violations = []
        warnings = []
        
        # Extract contract specifications
        required_columns = contract.get("required_columns", [])
        optional_columns = contract.get("optional_columns", [])
        column_types = contract.get("column_types", {})
        column_mappings = contract.get("column_mappings", {})  # old_name -> new_name
        value_constraints = contract.get("value_constraints", {})
        uniqueness_constraints = contract.get("uniqueness_constraints", [])
        
        # ==================== STRUCTURAL ENFORCEMENT ====================
        
        # 1. Check for missing required columns
        input_columns = set(df.columns)
        required_set = set(required_columns)
        missing_required = required_set - input_columns
        
        # Check if missing columns can be mapped
        mappable_missing = set()
        for missing_col in missing_required:
            # Check if there's a column that maps to this required column
            for old_name, new_name in column_mappings.items():
                if new_name == missing_col and old_name in input_columns:
                    mappable_missing.add(missing_col)
                    break
        
        truly_missing = missing_required - mappable_missing
        
        for col in truly_missing:
            violation = {
                "violation_id": f"violation_missing_{col}",
                "category": "structural",
                "type": "missing_required_column",
                "severity": "critical",
                "column": col,
                "message": f"Required column '{col}' is missing from input dataset",
                "action_taken": "flagged" if strict_mode else "none",
                "contract_requirement": f"Column '{col}' is mandatory"
            }
            violations.append(violation)
            critical_violations.append(violation)
        
        if strict_mode and truly_missing:
            return _generate_failure_response(
                start_time, 
                f"CRITICAL: Missing required columns: {', '.join(truly_missing)}",
                violations
            )
        
        # 2. Check for extra unspecified columns
        allowed_columns = set(required_columns) | set(optional_columns)
        # Also include source columns from mappings
        for old_name in column_mappings.keys():
            allowed_columns.add(old_name)
        
        extra_columns = input_columns - allowed_columns
        
        for col in extra_columns:
            violation = {
                "violation_id": f"violation_extra_{col}",
                "category": "structural",
                "type": "extra_unspecified_column",
                "severity": "warning",
                "column": col,
                "message": f"Column '{col}' is not specified in contract",
                "action_taken": "dropped" if (auto_transform and drop_extra_columns) else "flagged",
                "contract_requirement": "Only specified columns allowed"
            }
            violations.append(violation)
            warnings.append(violation)
            
            if auto_transform and drop_extra_columns:
                df = df.drop(col)
                transformations.append({
                    "transformation_id": f"transform_drop_{col}",
                    "type": "drop_column",
                    "column": col,
                    "description": f"Dropped extra column '{col}' not in contract"
                })
        
        # 3. Apply column name mappings
        for old_name, new_name in column_mappings.items():
            if old_name in df.columns:
                if auto_transform and rename_columns:
                    df = df.rename({old_name: new_name})
                    transformations.append({
                        "transformation_id": f"transform_rename_{old_name}",
                        "type": "rename_column",
                        "old_name": old_name,
                        "new_name": new_name,
                        "description": f"Renamed column '{old_name}' to '{new_name}'"
                    })
                else:
                    violation = {
                        "violation_id": f"violation_naming_{old_name}",
                        "category": "structural",
                        "type": "incorrect_column_naming",
                        "severity": "warning",
                        "column": old_name,
                        "message": f"Column '{old_name}' should be named '{new_name}' per contract",
                        "action_taken": "flagged",
                        "expected_name": new_name,
                        "contract_requirement": f"Column must be named '{new_name}'"
                    }
                    violations.append(violation)
                    warnings.append(violation)
        
        # 4. Check and enforce data types
        for col, expected_type in column_types.items():
            if col not in df.columns:
                continue
            
            actual_type = str(df[col].dtype)
            type_match, type_category = _check_type_compatibility(actual_type, expected_type)
            
            if not type_match:
                if auto_transform and cast_types:
                    # Attempt type conversion
                    df, success, error_msg = _cast_column_type(df, col, expected_type)
                    
                    if success:
                        transformations.append({
                            "transformation_id": f"transform_cast_{col}",
                            "type": "cast_type",
                            "column": col,
                            "from_type": actual_type,
                            "to_type": expected_type,
                            "description": f"Cast column '{col}' from {actual_type} to {expected_type}"
                        })
                    else:
                        violation = {
                            "violation_id": f"violation_type_{col}",
                            "category": "structural",
                            "type": "incorrect_data_type",
                            "severity": "high",
                            "column": col,
                            "message": f"Column '{col}' has type '{actual_type}' but contract requires '{expected_type}'. Cast failed: {error_msg}",
                            "action_taken": "cast_attempted_failed",
                            "expected_type": expected_type,
                            "actual_type": actual_type,
                            "contract_requirement": f"Column must be of type '{expected_type}'"
                        }
                        violations.append(violation)
                        warnings.append(violation)
                else:
                    violation = {
                        "violation_id": f"violation_type_{col}",
                        "category": "structural",
                        "type": "incorrect_data_type",
                        "severity": "high",
                        "column": col,
                        "message": f"Column '{col}' has type '{actual_type}' but contract requires '{expected_type}'",
                        "action_taken": "flagged",
                        "expected_type": expected_type,
                        "actual_type": actual_type,
                        "contract_requirement": f"Column must be of type '{expected_type}'"
                    }
                    violations.append(violation)
                    warnings.append(violation)
        
        # ==================== VALUE ENFORCEMENT ====================
        row_level_issues = []
        
        if enforce_values:
            for col, constraints in value_constraints.items():
                if col not in df.columns:
                    continue
                
                col_data = df[col]
                
                # 5. Check allowed values (enum/set constraint)
                allowed_values = constraints.get("allowed_values")
                if allowed_values:
                    invalid_mask = ~col_data.is_in(allowed_values) & col_data.is_not_null()
                    invalid_rows = df.with_row_index("row_index").filter(invalid_mask)
                    
                    if invalid_rows.height > 0:
                        default_value = constraints.get("default_value", None)
                        
                        violation = {
                            "violation_id": f"violation_values_{col}",
                            "category": "value",
                            "type": "invalid_value_set",
                            "severity": "warning",
                            "column": col,
                            "message": f"Column '{col}' contains {invalid_rows.height} values not in allowed set: {allowed_values}",
                            "action_taken": "replaced" if auto_transform else "flagged",
                            "invalid_count": invalid_rows.height,
                            "allowed_values": allowed_values,
                            "contract_requirement": f"Values must be one of: {allowed_values}"
                        }
                        violations.append(violation)
                        warnings.append(violation)
                        
                        # Add row-level issues
                        for row in invalid_rows.head(100).iter_rows(named=True):
                            if len(row_level_issues) < 1000:
                                row_level_issues.append({
                                    "row_index": int(row["row_index"]),
                                    "column": col,
                                    "issue_type": "invalid_value",
                                    "severity": "warning",
                                    "message": f"Value '{row[col]}' not in allowed set {allowed_values}",
                                    "value": str(row[col]),
                                    "allowed_values": allowed_values
                                })
                        
                        if auto_transform:
                            df = df.with_columns(
                                pl.when(invalid_mask)
                                .then(pl.lit(default_value))
                                .otherwise(pl.col(col))
                                .alias(col)
                            )
                            transformations.append({
                                "transformation_id": f"transform_values_{col}",
                                "type": "replace_invalid_values",
                                "column": col,
                                "replacement": default_value,
                                "count": invalid_rows.height,
                                "description": f"Replaced {invalid_rows.height} invalid values with '{default_value}'"
                            })
                
                # 6. Check range constraints (min/max)
                min_value = constraints.get("min_value")
                max_value = constraints.get("max_value")
                
                if min_value is not None or max_value is not None:
                    # Only for numeric columns
                    if col_data.dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, 
                                          pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
                                          pl.Float32, pl.Float64]:
                        
                        out_of_range_mask = pl.lit(False)
                        if min_value is not None:
                            out_of_range_mask = out_of_range_mask | (pl.col(col) < min_value)
                        if max_value is not None:
                            out_of_range_mask = out_of_range_mask | (pl.col(col) > max_value)
                        
                        out_of_range_rows = df.with_row_index("row_index").filter(
                            out_of_range_mask & pl.col(col).is_not_null()
                        )
                        
                        if out_of_range_rows.height > 0:
                            cap_strategy = constraints.get("cap_strategy", "cap")  # cap, null, drop
                            
                            violation = {
                                "violation_id": f"violation_range_{col}",
                                "category": "value",
                                "type": "out_of_bounds_range",
                                "severity": "warning",
                                "column": col,
                                "message": f"Column '{col}' has {out_of_range_rows.height} values outside range [{min_value}, {max_value}]",
                                "action_taken": "capped" if auto_transform else "flagged",
                                "out_of_range_count": out_of_range_rows.height,
                                "min_value": min_value,
                                "max_value": max_value,
                                "contract_requirement": f"Values must be between {min_value} and {max_value}"
                            }
                            violations.append(violation)
                            warnings.append(violation)
                            
                            # Add row-level issues
                            for row in out_of_range_rows.head(100).iter_rows(named=True):
                                if len(row_level_issues) < 1000:
                                    row_level_issues.append({
                                        "row_index": int(row["row_index"]),
                                        "column": col,
                                        "issue_type": "out_of_range",
                                        "severity": "warning",
                                        "message": f"Value {row[col]} outside range [{min_value}, {max_value}]",
                                        "value": str(row[col]),
                                        "min_value": min_value,
                                        "max_value": max_value
                                    })
                            
                            if auto_transform and cap_strategy == "cap":
                                expr = pl.col(col)
                                if min_value is not None:
                                    expr = pl.when(pl.col(col) < min_value).then(pl.lit(min_value)).otherwise(expr)
                                if max_value is not None:
                                    expr = pl.when(expr > max_value).then(pl.lit(max_value)).otherwise(expr)
                                
                                df = df.with_columns(expr.alias(col))
                                transformations.append({
                                    "transformation_id": f"transform_range_{col}",
                                    "type": "cap_values",
                                    "column": col,
                                    "min_value": min_value,
                                    "max_value": max_value,
                                    "count": out_of_range_rows.height,
                                    "description": f"Capped {out_of_range_rows.height} out-of-range values"
                                })
                
                # 7. Check regex/format constraints
                pattern = constraints.get("pattern")
                if pattern and col_data.dtype == pl.Utf8:
                    pattern_name = constraints.get("pattern_name", "custom pattern")
                    
                    try:
                        invalid_pattern_mask = ~col_data.str.contains(pattern) & col_data.is_not_null()
                        invalid_pattern_rows = df.with_row_index("row_index").filter(invalid_pattern_mask)
                        
                        if invalid_pattern_rows.height > 0:
                            violation = {
                                "violation_id": f"violation_format_{col}",
                                "category": "value",
                                "type": "incorrect_format",
                                "severity": "warning",
                                "column": col,
                                "message": f"Column '{col}' has {invalid_pattern_rows.height} values not matching {pattern_name}",
                                "action_taken": "flagged",
                                "invalid_count": invalid_pattern_rows.height,
                                "pattern": pattern,
                                "pattern_name": pattern_name,
                                "contract_requirement": f"Values must match pattern: {pattern}"
                            }
                            violations.append(violation)
                            warnings.append(violation)
                            
                            # Add row-level issues
                            for row in invalid_pattern_rows.head(100).iter_rows(named=True):
                                if len(row_level_issues) < 1000:
                                    row_level_issues.append({
                                        "row_index": int(row["row_index"]),
                                        "column": col,
                                        "issue_type": "format_violation",
                                        "severity": "warning",
                                        "message": f"Value '{row[col]}' does not match {pattern_name}",
                                        "value": str(row[col]),
                                        "expected_pattern": pattern
                                    })
                    except Exception as e:
                        # Invalid regex pattern
                        pass
        
        # 8. Check uniqueness constraints
        for unique_col in uniqueness_constraints:
            if unique_col not in df.columns:
                continue
            
            value_counts = df[unique_col].value_counts(sort=True)
            duplicates = value_counts.filter(pl.col("count") > 1)
            
            if duplicates.height > 0:
                total_duplicates = duplicates["count"].sum() - duplicates.height
                
                violation = {
                    "violation_id": f"violation_unique_{unique_col}",
                    "category": "value",
                    "type": "uniqueness_violation",
                    "severity": "critical",
                    "column": unique_col,
                    "message": f"Column '{unique_col}' has {total_duplicates} duplicate values (uniqueness required)",
                    "action_taken": "flagged",
                    "duplicate_count": int(total_duplicates),
                    "unique_values_with_duplicates": duplicates.height,
                    "contract_requirement": f"Column '{unique_col}' must have unique values"
                }
                violations.append(violation)
                critical_violations.append(violation)
                
                # Add row-level issues for duplicates
                dup_values = duplicates[unique_col].to_list()[:10]
                for dup_val in dup_values:
                    dup_rows = df.with_row_index("row_index").filter(pl.col(unique_col) == dup_val)
                    for row in dup_rows.iter_rows(named=True):
                        if len(row_level_issues) < 1000:
                            row_level_issues.append({
                                "row_index": int(row["row_index"]),
                                "column": unique_col,
                                "issue_type": "duplicate_value",
                                "severity": "critical",
                                "message": f"Duplicate value '{dup_val}' in column requiring uniqueness",
                                "value": str(dup_val)
                            })
        
        # Cap row-level issues
        row_level_issues = row_level_issues[:1000]
        
        # Calculate compliance scores
        structural_violations = len([v for v in violations if v["category"] == "structural"])
        value_violations = len([v for v in violations if v["category"] == "value"])
        total_checks = len(required_columns) + len(column_types) + len(value_constraints) + len(uniqueness_constraints)
        
        structural_compliance = ((total_checks - structural_violations) / max(total_checks, 1)) * 100
        value_compliance = ((total_rows * len(value_constraints) - value_violations) / max(total_rows * len(value_constraints), 1)) * 100 if value_constraints else 100
        transformation_success = (len(transformations) / max(len(violations), 1)) * 100 if violations else 100
        
        overall_score = (
            structural_compliance * structural_compliance_weight +
            value_compliance * value_compliance_weight +
            transformation_success * transformation_success_weight
        )
        
        # Determine quality status
        if overall_score >= excellent_threshold:
            quality_status = "compliant"
        elif overall_score >= good_threshold:
            quality_status = "partially_compliant"
        else:
            quality_status = "non_compliant"
        
        # Calculate issue summary
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
        
        # Build enforcement data
        enforcement_data = {
            "compliance_score": round(overall_score, 1),
            "quality_status": quality_status,
            "structural_compliance": round(structural_compliance, 1),
            "value_compliance": round(value_compliance, 1),
            "transformation_success": round(transformation_success, 1),
            "violations": violations,
            "transformations": transformations,
            "critical_violations_count": len(critical_violations),
            "warnings_count": len(warnings),
            "contract_summary": {
                "required_columns": required_columns,
                "optional_columns": optional_columns,
                "column_types": column_types,
                "value_constraints_count": len(value_constraints),
                "uniqueness_constraints": uniqueness_constraints
            },
            "summary": f"Contract enforcement completed. Status: {quality_status}. "
                      f"{len(violations)} violations found, {len(transformations)} transformations applied.",
            "row_level_issues": row_level_issues[:100],
            "issue_summary": issue_summary,
            "overrides": {
                "auto_transform": auto_transform,
                "strict_mode": strict_mode,
                "drop_extra_columns": drop_extra_columns,
                "rename_columns": rename_columns,
                "cast_types": cast_types,
                "enforce_values": enforce_values,
                "default_value_strategy": default_value_strategy
            }
        }
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = [{
            "summary_id": "exec_contract_enforcer",
            "title": "Contract Compliance Status",
            "value": f"{overall_score:.1f}",
            "status": "excellent" if quality_status == "compliant" else "good" if quality_status == "partially_compliant" else "needs_improvement",
            "description": f"Status: {quality_status.upper()}, Violations: {len(violations)}, "
                          f"Transformations: {len(transformations)}, Critical: {len(critical_violations)}"
        }]
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_parts = []
        ai_analysis_parts.append(f"CONTRACT ENFORCER ANALYSIS:")
        ai_analysis_parts.append(f"- Compliance Score: {overall_score:.1f}/100 ({quality_status})")
        ai_analysis_parts.append(f"- Structural Compliance: {structural_compliance:.1f}% ({structural_violations} violations)")
        ai_analysis_parts.append(f"- Value Compliance: {value_compliance:.1f}% ({value_violations} violations)")
        ai_analysis_parts.append(f"- Transformations Applied: {len(transformations)}")
        
        if critical_violations:
            ai_analysis_parts.append(f"- CRITICAL: {len(critical_violations)} critical violations require immediate attention")
            critical_types = set(v["type"] for v in critical_violations)
            ai_analysis_parts.append(f"  Types: {', '.join(critical_types)}")
        
        if truly_missing:
            ai_analysis_parts.append(f"- Missing Required Columns: {', '.join(truly_missing)}")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # Critical: Missing required columns
        if truly_missing:
            alerts.append({
                "alert_id": "alert_contract_missing_required",
                "severity": "critical",
                "category": "structural_compliance",
                "message": f"CRITICAL: {len(truly_missing)} required column(s) missing: {', '.join(truly_missing)}",
                "affected_fields_count": len(truly_missing),
                "recommendation": "Add missing columns to input data or update contract requirements."
            })
        
        # Critical: Uniqueness violations
        if any(v["type"] == "uniqueness_violation" for v in violations):
            unique_violations = [v for v in violations if v["type"] == "uniqueness_violation"]
            alerts.append({
                "alert_id": "alert_contract_uniqueness",
                "severity": "critical",
                "category": "data_integrity",
                "message": f"Uniqueness constraint violated in {len(unique_violations)} column(s)",
                "affected_fields_count": len(unique_violations),
                "recommendation": "Deduplicate records or send to Mastering Tool for merging."
            })
        
        # High: Type mismatches
        type_violations = [v for v in violations if v["type"] == "incorrect_data_type"]
        if type_violations:
            alerts.append({
                "alert_id": "alert_contract_types",
                "severity": "high",
                "category": "type_compliance",
                "message": f"{len(type_violations)} column(s) have incorrect data types",
                "affected_fields_count": len(type_violations),
                "recommendation": "Review type definitions and apply type conversions."
            })
        
        # Warning: Extra columns dropped
        extra_dropped = [t for t in transformations if t["type"] == "drop_column"]
        if extra_dropped:
            alerts.append({
                "alert_id": "alert_contract_extra_dropped",
                "severity": "medium",
                "category": "structural_compliance",
                "message": f"{len(extra_dropped)} extra column(s) dropped as per contract",
                "affected_fields_count": len(extra_dropped),
                "recommendation": "Verify dropped columns are not needed or update contract."
            })
        
        # Warning: Value violations
        value_violation_count = len([v for v in violations if v["category"] == "value"])
        if value_violation_count > 0:
            alerts.append({
                "alert_id": "alert_contract_values",
                "severity": "medium",
                "category": "value_compliance",
                "message": f"{value_violation_count} value constraint violation(s) detected",
                "affected_fields_count": len(set(v["column"] for v in violations if v["category"] == "value")),
                "recommendation": "Review value constraints and apply data cleansing."
            })
        
        # Overall compliance alert
        if quality_status != "compliant":
            alerts.append({
                "alert_id": "alert_contract_compliance",
                "severity": "high" if quality_status == "non_compliant" else "medium",
                "category": "overall_compliance",
                "message": f"Contract compliance: {quality_status.upper()} ({overall_score:.1f}%)",
                "affected_fields_count": len(violations),
                "recommendation": "Address violations before integration with downstream systems."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        for v in violations[:100]:
            issues.append({
                "issue_id": v["violation_id"],
                "agent_id": "contract-enforcer",
                "field_name": v.get("column", "dataset"),
                "issue_type": v["type"],
                "severity": v["severity"],
                "message": v["message"]
            })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        agent_recommendations = []
        
        # Recommendation 1: Address critical violations
        if critical_violations:
            agent_recommendations.append({
                "recommendation_id": "rec_contract_critical",
                "agent_id": "contract-enforcer",
                "field_name": ", ".join(set(v.get("column", "N/A") for v in critical_violations[:3])),
                "priority": "critical",
                "recommendation": f"IMMEDIATE: Address {len(critical_violations)} critical violation(s) blocking data integration",
                "timeline": "immediate"
            })
        
        # Recommendation 2: Handle missing columns
        if truly_missing:
            agent_recommendations.append({
                "recommendation_id": "rec_contract_missing",
                "agent_id": "contract-enforcer",
                "field_name": ", ".join(list(truly_missing)[:3]),
                "priority": "critical",
                "recommendation": f"Add {len(truly_missing)} missing required column(s) to source data",
                "timeline": "immediate"
            })
        
        # Recommendation 3: Type alignment
        if type_violations:
            agent_recommendations.append({
                "recommendation_id": "rec_contract_types",
                "agent_id": "contract-enforcer",
                "field_name": ", ".join([v["column"] for v in type_violations[:3]]),
                "priority": "high",
                "recommendation": f"Run Type Fixer agent on {len(type_violations)} column(s) with type mismatches",
                "timeline": "1 week"
            })
        
        # Recommendation 4: Value standardization
        value_violations_list = [v for v in violations if v["category"] == "value"]
        if value_violations_list:
            agent_recommendations.append({
                "recommendation_id": "rec_contract_values",
                "agent_id": "contract-enforcer",
                "field_name": ", ".join(set(v["column"] for v in value_violations_list[:3])),
                "priority": "high",
                "recommendation": f"Apply Field Standardization to {len(value_violations_list)} value constraint violation(s)",
                "timeline": "1 week"
            })
        
        # Recommendation 5: Deduplication
        uniqueness_issues = [v for v in violations if v["type"] == "uniqueness_violation"]
        if uniqueness_issues:
            agent_recommendations.append({
                "recommendation_id": "rec_contract_dedup",
                "agent_id": "contract-enforcer",
                "field_name": ", ".join([v["column"] for v in uniqueness_issues]),
                "priority": "critical",
                "recommendation": "Run DuplicateResolver or send to Mastering Tool for deduplication",
                "timeline": "immediate"
            })
        
        # Recommendation 6: Update contract (if many warnings)
        if len(warnings) > 10:
            agent_recommendations.append({
                "recommendation_id": "rec_contract_update",
                "agent_id": "contract-enforcer",
                "field_name": "contract",
                "priority": "medium",
                "recommendation": f"Review and potentially update contract - {len(warnings)} warnings suggest contract may be too strict",
                "timeline": "2 weeks"
            })
        
        # Recommendation 7: Implement validation at source
        agent_recommendations.append({
            "recommendation_id": "rec_contract_source_validation",
            "agent_id": "contract-enforcer",
            "field_name": "all",
            "priority": "medium",
            "recommendation": "Implement contract validation at data source to prevent violations at ingestion",
            "timeline": "2-3 weeks"
        })
        
        # Recommendation 8: Contract documentation
        agent_recommendations.append({
            "recommendation_id": "rec_contract_documentation",
            "agent_id": "contract-enforcer",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Document contract requirements and share with data providers",
            "timeline": "3 weeks"
        })

        # Generate cleaned file (CSV format)
        cleaned_file_bytes = _generate_cleaned_file(df, filename)
        cleaned_file_base64 = base64.b64encode(cleaned_file_bytes).decode('utf-8')

        return {
            "status": "success",
            "agent_id": "contract-enforcer",
            "agent_name": "Contract Enforcer",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_processed": total_rows,
                "original_columns": total_columns,
                "final_columns": len(df.columns),
                "violations_count": len(violations),
                "critical_violations": len(critical_violations),
                "warnings_count": len(warnings),
                "transformations_applied": len(transformations),
                "total_issues": len(row_level_issues)
            },
            "data": enforcement_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary,
            "cleaned_file": {
                "filename": f"mastered_{filename}",
                "content": cleaned_file_base64,
                "size_bytes": len(cleaned_file_bytes),
                "format": filename.split('.')[-1].lower()
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "contract-enforcer",
            "agent_name": "Contract Enforcer",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _check_type_compatibility(actual_type: str, expected_type: str) -> Tuple[bool, str]:
    """Check if actual type is compatible with expected type."""
    type_mappings = {
        "string": ["Utf8", "String", "str"],
        "text": ["Utf8", "String", "str"],
        "integer": ["Int8", "Int16", "Int32", "Int64", "UInt8", "UInt16", "UInt32", "UInt64"],
        "int": ["Int8", "Int16", "Int32", "Int64", "UInt8", "UInt16", "UInt32", "UInt64"],
        "float": ["Float32", "Float64"],
        "double": ["Float64"],
        "numeric": ["Int8", "Int16", "Int32", "Int64", "UInt8", "UInt16", "UInt32", "UInt64", "Float32", "Float64"],
        "boolean": ["Boolean", "Bool"],
        "bool": ["Boolean", "Bool"],
        "date": ["Date"],
        "datetime": ["Datetime", "Date"],
        "timestamp": ["Datetime"]
    }
    
    expected_lower = expected_type.lower()
    
    if expected_lower in type_mappings:
        compatible_types = type_mappings[expected_lower]
        for ct in compatible_types:
            if ct.lower() in actual_type.lower():
                return True, expected_lower
    
    # Direct match check
    if expected_lower in actual_type.lower():
        return True, expected_lower
    
    return False, expected_lower


def _cast_column_type(df: pl.DataFrame, col: str, target_type: str) -> Tuple[pl.DataFrame, bool, str]:
    """Attempt to cast column to target type."""
    try:
        target_lower = target_type.lower()
        
        if target_lower in ["string", "text", "str"]:
            df = df.with_columns(pl.col(col).cast(pl.Utf8))
        elif target_lower in ["integer", "int"]:
            df = df.with_columns(pl.col(col).cast(pl.Int64, strict=False))
        elif target_lower in ["float", "double", "numeric"]:
            df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False))
        elif target_lower in ["boolean", "bool"]:
            df = df.with_columns(pl.col(col).cast(pl.Boolean, strict=False))
        elif target_lower in ["date"]:
            df = df.with_columns(pl.col(col).str.to_date(strict=False))
        elif target_lower in ["datetime", "timestamp"]:
            df = df.with_columns(pl.col(col).str.to_datetime(strict=False))
        else:
            return df, False, f"Unknown target type: {target_type}"
        
        return df, True, ""
    
    except Exception as e:
        return df, False, str(e)


def _generate_failure_response(
    start_time: float, 
    message: str, 
    violations: List[Dict]
) -> Dict[str, Any]:
    """Generate a failure response for strict mode violations."""
    return {
        "status": "failed",
        "agent_id": "contract-enforcer",
        "agent_name": "Contract Enforcer",
        "error": message,
        "violations": violations,
        "execution_time_ms": int((time.time() - start_time) * 1000),
        "summary_metrics": {
            "violations_count": len(violations)
        },
        "data": {
            "quality_status": "failed",
            "compliance_score": 0,
            "violations": violations
        },
        "alerts": [{
            "alert_id": "alert_contract_failed",
            "severity": "critical",
            "category": "workflow_stopped",
            "message": message,
            "affected_fields_count": len(violations),
            "recommendation": "Address critical violations before continuing workflow."
        }],
        "issues": [{
            "issue_id": "issue_contract_workflow_stopped",
            "agent_id": "contract-enforcer",
            "field_name": "workflow",
            "issue_type": "workflow_failed",
            "severity": "critical",
            "message": message
        }],
        "recommendations": [{
            "recommendation_id": "rec_contract_fix_critical",
            "agent_id": "contract-enforcer",
            "field_name": "all",
            "priority": "critical",
            "recommendation": "Fix critical contract violations to proceed with data processing",
            "timeline": "immediate"
        }],
        "executive_summary": [{
            "summary_id": "exec_contract_failed",
            "title": "Contract Enforcement Failed",
            "value": "0",
            "status": "failed",
            "description": message
        }],
        "ai_analysis_text": f"CONTRACT ENFORCEMENT FAILED:\n- {message}\n- Workflow stopped in strict mode\n- {len(violations)} violation(s) must be addressed",
        "row_level_issues": [],
        "issue_summary": {
            "total_issues": len(violations),
            "by_type": {},
            "by_severity": {"critical": len(violations)},
            "affected_rows": 0,
            "affected_columns": []
        }
    }


def _generate_cleaned_file(df: pl.DataFrame, original_filename: str) -> bytes:
    """
    Generate cleaned data file in CSV format.
    
    Args:
        df: Cleaned dataframe
        original_filename: Original filename to determine format
        
    Returns:
        File contents as bytes
    """
    output = io.BytesIO()
    df.write_csv(output)
    return output.getvalue()
