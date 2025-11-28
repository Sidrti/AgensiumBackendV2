"""
Stewardship Flagger Agent

Identifies data issues that require human review or intervention. This agent
automatically flags suspicious, incomplete, inconsistent, or low-confidence data
so that Data Stewards can take action.

It is the "quality gatekeeper" of the entire data pipeline.

Key Responsibilities:
1. Detect data quality issues (missing required, invalid formats, conflicts, etc.)
2. Assign stewardship flags with consistent categories
3. Generate stewardship log entries
4. Determine required human actions
5. Integrate with other agents (uses confidence scores, lineage, etc.)

Issue Categories:
- MISSING_REQUIRED: Required field missing
- INVALID_FORMAT: Field format failed validation
- CONFLICT_UNRESOLVED: SurvivorshipResolver couldn't find confident winner
- DUPLICATE_SUSPECTED: Possible duplicate record group detected
- LOW_CONFIDENCE: Confidence score low
- OUTLIER_VALUE: Value outside expected range
- STANDARDIZATION_FAILED: FieldStandardizer couldn't normalize value

Input: CSV file with optional agent metadata
Output: Stewardship tasks and flagged records for human review
"""

import io
import re
import time
import base64
import polars as pl
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from collections import defaultdict


# ==================== ISSUE CATEGORIES ====================
ISSUE_CATEGORIES = {
    "MISSING_REQUIRED": "Required field missing",
    "INVALID_FORMAT": "Field format failed validation",
    "CONFLICT_UNRESOLVED": "SurvivorshipResolver couldn't find a confident winner",
    "DUPLICATE_SUSPECTED": "Possible duplicate record group detected",
    "LOW_CONFIDENCE": "Confidence score low",
    "OUTLIER_VALUE": "Value outside expected range",
    "STANDARDIZATION_FAILED": "FieldStandardizer couldn't normalize value",
    "DATA_TYPE_MISMATCH": "Data type doesn't match expected type",
    "REFERENTIAL_INTEGRITY": "Referenced entity not found",
    "BUSINESS_RULE_VIOLATION": "Custom business rule violated"
}

# ==================== VALIDATION PATTERNS ====================
VALIDATION_PATTERNS = {
    "email": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    "phone_e164": r'^\+[1-9]\d{6,14}$',
    "phone_general": r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]{6,}$',
    "date_iso": r'^\d{4}-\d{2}-\d{2}$',
    "date_general": r'^\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}$',
    "uuid": r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
    "zip_us": r'^\d{5}(-\d{4})?$',
    "url": r'^https?://[^\s/$.?#].[^\s]*$',
    "ssn": r'^\d{3}-\d{2}-\d{4}$',
    "currency": r'^[\$€£¥]?\s*[\d,]+\.?\d*$',
    "percentage": r'^\d+\.?\d*\s*%?$'
}

# ==================== FIELD TYPE PATTERNS ====================
FIELD_TYPE_PATTERNS = {
    "email": [r'email', r'e[-_]?mail', r'mail_addr'],
    "phone": [r'phone', r'mobile', r'cell', r'tel', r'fax', r'contact_number'],
    "date": [r'date', r'_at$', r'_on$', r'timestamp', r'created', r'updated', r'modified', r'dob', r'birth'],
    "name": [r'name', r'first[-_]?name', r'last[-_]?name', r'full[-_]?name', r'fname', r'lname'],
    "address": [r'address', r'street', r'city', r'state', r'zip', r'postal', r'country', r'addr'],
    "id": [r'_id$', r'^id$', r'identifier', r'key', r'code'],
    "currency": [r'price', r'cost', r'amount', r'total', r'revenue', r'salary', r'income'],
    "percentage": [r'percent', r'rate', r'ratio', r'pct'],
    "age": [r'^age$', r'_age$'],
    "gender": [r'gender', r'sex']
}

# ==================== OUTLIER THRESHOLDS ====================
DEFAULT_OUTLIER_THRESHOLDS = {
    "age": {"min": 0, "max": 120},
    "percentage": {"min": 0, "max": 100},
    "year": {"min": 1900, "max": 2100}
}


def execute_stewardship_flagger(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Flag data issues requiring human review or intervention.

    Args:
        file_contents: File bytes (read as binary)
        filename: Original filename
        parameters: Agent parameters including validation rules

    Returns:
        Standardized output dictionary with stewardship tasks
    """

    start_time = time.time()
    parameters = parameters or {}

    # Extract parameters with defaults
    required_columns = parameters.get("required_columns", [])
    confidence_threshold = parameters.get("confidence_threshold", 0.7)
    confidence_columns = parameters.get("confidence_columns", [])  # Columns containing confidence scores
    
    # Validation rules
    field_validation_rules = parameters.get("field_validation_rules", {})
    outlier_thresholds = parameters.get("outlier_thresholds", DEFAULT_OUTLIER_THRESHOLDS)
    
    # Duplicate detection
    duplicate_key_columns = parameters.get("duplicate_key_columns", [])
    
    # Business rules
    business_rules = parameters.get("business_rules", [])
    
    # Priority configuration
    severity_weights = parameters.get("severity_weights", {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1
    })
    
    # Scoring thresholds
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file - CSV only
        if not filename.endswith('.csv'):
            return {
                "status": "error",
                "agent_id": "stewardship-flagger",
                "error": f"Unsupported file format: {filename}. Only CSV files are supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        try:
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": "stewardship-flagger",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.height == 0:
            return {
                "status": "error",
                "agent_id": "stewardship-flagger",
                "agent_name": "Stewardship Flagger",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        total_rows = df.height
        total_columns = len(df.columns)
        
        # Auto-detect field types
        field_types = _detect_field_types(df)
        
        # Auto-detect confidence columns
        if not confidence_columns:
            confidence_columns = [
                col for col in df.columns
                if any(kw in col.lower() for kw in ['confidence', 'score', 'trust', 'quality'])
            ]
        
        # ==================== DETECT ISSUES ====================
        
        stewardship_tasks = []
        flagged_records = []
        issue_counts = defaultdict(int)
        issues_by_column = defaultdict(list)
        issues_by_severity = defaultdict(int)
        row_level_issues = []
        
        # 1. Check Missing Required Fields
        for col in required_columns:
            if col not in df.columns:
                stewardship_tasks.append({
                    "task_id": f"task_missing_col_{col}",
                    "entity_id": "schema",
                    "field": col,
                    "issue_type": "MISSING_REQUIRED",
                    "value": None,
                    "priority": "critical",
                    "confidence": 0.0,
                    "recommended_action": f"Add required column '{col}' to the dataset",
                    "detected_at": datetime.utcnow().isoformat() + "Z"
                })
                issue_counts["MISSING_REQUIRED"] += 1
                issues_by_severity["critical"] += 1
            else:
                # Check for null values in required columns
                null_count = df[col].null_count()
                if null_count > 0:
                    # Get row indices with nulls
                    null_mask = df[col].is_null()
                    null_indices = [i for i, is_null in enumerate(null_mask.to_list()) if is_null]
                    
                    for idx in null_indices[:50]:  # Limit to 50
                        row = df.row(idx)
                        entity_id = _get_entity_id(df, idx)
                        
                        task = {
                            "task_id": f"task_null_{col}_{idx}",
                            "entity_id": entity_id,
                            "field": col,
                            "issue_type": "MISSING_REQUIRED",
                            "value": None,
                            "priority": "high",
                            "confidence": 0.0,
                            "row_index": idx,
                            "recommended_action": f"Fill missing required field '{col}'",
                            "detected_at": datetime.utcnow().isoformat() + "Z"
                        }
                        stewardship_tasks.append(task)
                        
                        row_level_issues.append({
                            "row_index": idx,
                            "column": col,
                            "issue_type": "MISSING_REQUIRED",
                            "severity": "high",
                            "original_value": None,
                            "message": f"Required field '{col}' is missing"
                        })
                    
                    issue_counts["MISSING_REQUIRED"] += null_count
                    issues_by_severity["high"] += null_count
                    issues_by_column[col].append({"type": "MISSING_REQUIRED", "count": null_count})
        
        # 2. Check Format Validation
        for col in df.columns:
            field_type = field_types.get(col, "unknown")
            
            # Get validation pattern
            pattern = None
            if field_type == "email":
                pattern = VALIDATION_PATTERNS["email"]
            elif field_type == "phone":
                pattern = VALIDATION_PATTERNS["phone_general"]
            elif field_type == "date":
                pattern = VALIDATION_PATTERNS["date_general"]
            
            # Check custom validation rules
            if col in field_validation_rules:
                custom_rule = field_validation_rules[col]
                if "pattern" in custom_rule:
                    pattern = custom_rule["pattern"]
            
            if pattern:
                invalid_count = 0
                for idx in range(min(df.height, 1000)):  # Sample first 1000 rows
                    val = df[col][idx]
                    if val is not None and str(val).strip() != '':
                        if not re.match(pattern, str(val)):
                            entity_id = _get_entity_id(df, idx)
                            
                            task = {
                                "task_id": f"task_format_{col}_{idx}",
                                "entity_id": entity_id,
                                "field": col,
                                "issue_type": "INVALID_FORMAT",
                                "value": str(val)[:100],
                                "priority": "medium",
                                "confidence": 0.2,
                                "row_index": idx,
                                "recommended_action": f"Correct {field_type} format for '{col}'",
                                "detected_at": datetime.utcnow().isoformat() + "Z"
                            }
                            
                            if invalid_count < 20:  # Limit tasks per column
                                stewardship_tasks.append(task)
                            
                            row_level_issues.append({
                                "row_index": idx,
                                "column": col,
                                "issue_type": "INVALID_FORMAT",
                                "severity": "medium",
                                "original_value": str(val)[:50],
                                "message": f"Invalid {field_type} format: '{str(val)[:30]}...'"
                            })
                            
                            invalid_count += 1
                
                if invalid_count > 0:
                    issue_counts["INVALID_FORMAT"] += invalid_count
                    issues_by_severity["medium"] += invalid_count
                    issues_by_column[col].append({"type": "INVALID_FORMAT", "count": invalid_count})
        
        # 3. Check Low Confidence Fields
        for conf_col in confidence_columns:
            if conf_col not in df.columns:
                continue
            
            try:
                low_conf_count = 0
                for idx in range(df.height):
                    conf_val = df[conf_col][idx]
                    if conf_val is not None:
                        try:
                            conf_float = float(conf_val)
                            if conf_float < confidence_threshold:
                                entity_id = _get_entity_id(df, idx)
                                
                                task = {
                                    "task_id": f"task_lowconf_{conf_col}_{idx}",
                                    "entity_id": entity_id,
                                    "field": conf_col,
                                    "issue_type": "LOW_CONFIDENCE",
                                    "value": conf_float,
                                    "priority": "high" if conf_float < 0.3 else "medium",
                                    "confidence": conf_float,
                                    "row_index": idx,
                                    "recommended_action": "Manual verification required",
                                    "detected_at": datetime.utcnow().isoformat() + "Z"
                                }
                                
                                if low_conf_count < 30:
                                    stewardship_tasks.append(task)
                                
                                row_level_issues.append({
                                    "row_index": idx,
                                    "column": conf_col,
                                    "issue_type": "LOW_CONFIDENCE",
                                    "severity": "high" if conf_float < 0.3 else "medium",
                                    "original_value": conf_float,
                                    "message": f"Low confidence score: {conf_float:.2f}"
                                })
                                
                                low_conf_count += 1
                        except (ValueError, TypeError):
                            pass
                
                if low_conf_count > 0:
                    issue_counts["LOW_CONFIDENCE"] += low_conf_count
                    issues_by_severity["medium"] += low_conf_count
                    issues_by_column[conf_col].append({"type": "LOW_CONFIDENCE", "count": low_conf_count})
            except Exception:
                pass
        
        # 4. Check Outlier Values
        for col in df.columns:
            field_type = field_types.get(col, "unknown")
            
            thresholds = outlier_thresholds.get(field_type, {})
            if not thresholds and col in outlier_thresholds:
                thresholds = outlier_thresholds[col]
            
            if thresholds and df[col].dtype in [pl.Int64, pl.Int32, pl.Float64, pl.Float32]:
                min_val = thresholds.get("min")
                max_val = thresholds.get("max")
                
                outlier_count = 0
                for idx in range(df.height):
                    val = df[col][idx]
                    if val is not None:
                        try:
                            num_val = float(val)
                            is_outlier = False
                            
                            if min_val is not None and num_val < min_val:
                                is_outlier = True
                            if max_val is not None and num_val > max_val:
                                is_outlier = True
                            
                            if is_outlier:
                                entity_id = _get_entity_id(df, idx)
                                
                                task = {
                                    "task_id": f"task_outlier_{col}_{idx}",
                                    "entity_id": entity_id,
                                    "field": col,
                                    "issue_type": "OUTLIER_VALUE",
                                    "value": num_val,
                                    "priority": "medium",
                                    "confidence": 0.3,
                                    "row_index": idx,
                                    "expected_range": f"{min_val} - {max_val}",
                                    "recommended_action": f"Verify value {num_val} is correct (expected {min_val}-{max_val})",
                                    "detected_at": datetime.utcnow().isoformat() + "Z"
                                }
                                
                                if outlier_count < 20:
                                    stewardship_tasks.append(task)
                                
                                row_level_issues.append({
                                    "row_index": idx,
                                    "column": col,
                                    "issue_type": "OUTLIER_VALUE",
                                    "severity": "medium",
                                    "original_value": num_val,
                                    "message": f"Outlier value {num_val} outside range {min_val}-{max_val}"
                                })
                                
                                outlier_count += 1
                        except (ValueError, TypeError):
                            pass
                
                if outlier_count > 0:
                    issue_counts["OUTLIER_VALUE"] += outlier_count
                    issues_by_severity["medium"] += outlier_count
                    issues_by_column[col].append({"type": "OUTLIER_VALUE", "count": outlier_count})
        
        # 5. Check for Suspected Duplicates
        if duplicate_key_columns:
            valid_dup_cols = [col for col in duplicate_key_columns if col in df.columns]
            if valid_dup_cols:
                # Group by key columns
                dup_groups = df.group_by(valid_dup_cols).agg(pl.count().alias("__dup_count__"))
                duplicates = dup_groups.filter(pl.col("__dup_count__") > 1)
                
                dup_count = 0
                for i in range(duplicates.height):
                    key_values = {col: duplicates[col][i] for col in valid_dup_cols}
                    count = duplicates["__dup_count__"][i]
                    
                    task = {
                        "task_id": f"task_duplicate_{i}",
                        "entity_id": str(key_values),
                        "field": ", ".join(valid_dup_cols),
                        "issue_type": "DUPLICATE_SUSPECTED",
                        "value": key_values,
                        "priority": "high",
                        "confidence": 0.4,
                        "duplicate_count": count,
                        "recommended_action": f"Merge {count} duplicate records",
                        "detected_at": datetime.utcnow().isoformat() + "Z"
                    }
                    
                    if dup_count < 30:
                        stewardship_tasks.append(task)
                    
                    dup_count += count
                
                if dup_count > 0:
                    issue_counts["DUPLICATE_SUSPECTED"] += dup_count
                    issues_by_severity["high"] += dup_count
        
        # 6. Apply Business Rules
        for rule in business_rules:
            rule_name = rule.get("name", "custom_rule")
            condition = rule.get("condition", {})
            severity = rule.get("severity", "medium")
            action = rule.get("action", "Review required")
            
            # Simple condition matching
            if "column" in condition and "operator" in condition and "value" in condition:
                col = condition["column"]
                op = condition["operator"]
                val = condition["value"]
                
                if col in df.columns:
                    violations = 0
                    for idx in range(df.height):
                        cell_val = df[col][idx]
                        is_violation = False
                        
                        try:
                            if op == "eq" and str(cell_val) == str(val):
                                is_violation = True
                            elif op == "ne" and str(cell_val) != str(val):
                                is_violation = True
                            elif op == "gt" and float(cell_val) > float(val):
                                is_violation = True
                            elif op == "lt" and float(cell_val) < float(val):
                                is_violation = True
                            elif op == "contains" and val in str(cell_val):
                                is_violation = True
                        except:
                            pass
                        
                        if is_violation:
                            entity_id = _get_entity_id(df, idx)
                            
                            task = {
                                "task_id": f"task_rule_{rule_name}_{idx}",
                                "entity_id": entity_id,
                                "field": col,
                                "issue_type": "BUSINESS_RULE_VIOLATION",
                                "value": str(cell_val)[:100],
                                "priority": severity,
                                "rule_name": rule_name,
                                "row_index": idx,
                                "recommended_action": action,
                                "detected_at": datetime.utcnow().isoformat() + "Z"
                            }
                            
                            if violations < 20:
                                stewardship_tasks.append(task)
                            
                            row_level_issues.append({
                                "row_index": idx,
                                "column": col,
                                "issue_type": "BUSINESS_RULE_VIOLATION",
                                "severity": severity,
                                "original_value": str(cell_val)[:50],
                                "message": f"Business rule '{rule_name}' violated"
                            })
                            
                            violations += 1
                    
                    if violations > 0:
                        issue_counts["BUSINESS_RULE_VIOLATION"] += violations
                        issues_by_severity[severity] += violations
        
        # ==================== CALCULATE SCORES ====================
        
        total_issues = sum(issue_counts.values())
        total_potential_issues = total_rows * total_columns
        issue_rate = (total_issues / max(total_potential_issues, 1)) * 100
        
        # Clean data percentage
        clean_rate = 100 - min(100, issue_rate * 10)  # Scale issue rate
        
        # Priority distribution
        critical_count = issues_by_severity.get("critical", 0)
        high_count = issues_by_severity.get("high", 0)
        medium_count = issues_by_severity.get("medium", 0)
        low_count = issues_by_severity.get("low", 0)
        
        # Weighted score
        weighted_issues = (
            critical_count * severity_weights["critical"] +
            high_count * severity_weights["high"] +
            medium_count * severity_weights["medium"] +
            low_count * severity_weights["low"]
        )
        
        max_weighted = total_rows * severity_weights["critical"]  # Worst case
        weighted_score = max(0, 100 - (weighted_issues / max(max_weighted, 1) * 100))
        
        overall_score = (clean_rate * 0.6) + (weighted_score * 0.4)
        
        if overall_score >= excellent_threshold:
            quality_status = "excellent"
        elif overall_score >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"
        
        # Cap row-level issues
        row_level_issues = row_level_issues[:1000]
        
        # Issue summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": dict(issue_counts),
            "by_severity": dict(issues_by_severity),
            "affected_rows": len(set(issue["row_index"] for issue in row_level_issues if "row_index" in issue)),
            "affected_columns": sorted(list(issues_by_column.keys()))
        }
        
        # ==================== BUILD RESPONSE DATA ====================
        
        # Sort tasks by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        stewardship_tasks.sort(key=lambda x: priority_order.get(x.get("priority", "medium"), 2))
        
        stewardship_data = {
            "stewardship_score": round(overall_score, 1),
            "quality_status": quality_status,
            "task_list": stewardship_tasks[:200],
            "issue_distribution": dict(issue_counts),
            "issues_by_column": dict(issues_by_column),
            "issues_by_severity": dict(issues_by_severity),
            "statistics": {
                "total_records": total_rows,
                "total_columns": total_columns,
                "total_issues": total_issues,
                "tasks_created": len(stewardship_tasks),
                "critical_issues": critical_count,
                "high_priority_issues": high_count,
                "medium_priority_issues": medium_count,
                "low_priority_issues": low_count,
                "clean_data_rate": round(clean_rate, 1),
                "records_flagged": len(set(t.get("row_index", -1) for t in stewardship_tasks if t.get("row_index") is not None))
            },
            "field_types_detected": field_types,
            "reason_distribution": dict(issue_counts),
            "summary": f"Stewardship flagging completed. Identified {total_issues} issue(s) across {total_rows} records. "
                      f"Created {len(stewardship_tasks)} stewardship task(s). "
                      f"Critical: {critical_count}, High: {high_count}, Medium: {medium_count}.",
            "row_level_issues": row_level_issues[:100],
            "issue_summary": issue_summary,
            "overrides": {
                "required_columns": required_columns,
                "confidence_threshold": confidence_threshold,
                "duplicate_key_columns": duplicate_key_columns,
                "business_rules_count": len(business_rules)
            }
        }
        
        # ==================== EXECUTIVE SUMMARY ====================
        
        executive_summary = [{
            "summary_id": "exec_stewardship_flagger",
            "title": "Stewardship Status",
            "value": f"{len(stewardship_tasks)}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"{len(stewardship_tasks)} tasks created, {critical_count} critical, "
                          f"{high_count} high priority. Clean rate: {clean_rate:.1f}%"
        }]
        
        # ==================== AI ANALYSIS TEXT ====================
        
        ai_analysis_parts = [
            "STEWARDSHIP FLAGGER ANALYSIS:",
            f"- Stewardship Score: {overall_score:.1f}/100 ({quality_status})",
            f"- Total Issues Detected: {total_issues}",
            f"- Tasks Created: {len(stewardship_tasks)}",
            f"- Critical Issues: {critical_count}",
            f"- High Priority Issues: {high_count}",
            f"- Clean Data Rate: {clean_rate:.1f}%"
        ]
        
        if issue_counts:
            top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            ai_analysis_parts.append(f"- Top Issue Types: {', '.join(f'{t}({c})' for t, c in top_issues)}")
        
        if issues_by_column:
            problem_cols = list(issues_by_column.keys())[:5]
            ai_analysis_parts.append(f"- Problem Columns: {', '.join(problem_cols)}")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # ==================== ALERTS ====================
        
        alerts = []
        
        if critical_count > 0:
            alerts.append({
                "alert_id": "alert_stewardship_critical",
                "severity": "critical",
                "category": "data_quality",
                "message": f"{critical_count} critical issue(s) require immediate attention",
                "affected_fields_count": critical_count,
                "recommendation": "Address critical issues before proceeding with data processing."
            })
        
        if high_count > total_rows * 0.1:
            alerts.append({
                "alert_id": "alert_stewardship_high_volume",
                "severity": "high",
                "category": "data_quality",
                "message": f"High volume of issues detected ({high_count} high priority)",
                "affected_fields_count": high_count,
                "recommendation": "Review data collection process for systematic issues."
            })
        
        if issue_counts.get("MISSING_REQUIRED", 0) > 0:
            alerts.append({
                "alert_id": "alert_stewardship_missing",
                "severity": "high",
                "category": "completeness",
                "message": f"{issue_counts['MISSING_REQUIRED']} missing required field(s)",
                "affected_fields_count": issue_counts["MISSING_REQUIRED"],
                "recommendation": "Fill in missing required data or review data collection."
            })
        
        if issue_counts.get("DUPLICATE_SUSPECTED", 0) > 0:
            alerts.append({
                "alert_id": "alert_stewardship_duplicates",
                "severity": "medium",
                "category": "integrity",
                "message": f"{issue_counts['DUPLICATE_SUSPECTED']} suspected duplicate record(s)",
                "affected_fields_count": issue_counts["DUPLICATE_SUSPECTED"],
                "recommendation": "Review and merge duplicate records using GoldenRecordBuilder."
            })
        
        if overall_score < good_threshold:
            alerts.append({
                "alert_id": "alert_stewardship_quality",
                "severity": "high",
                "category": "overall_quality",
                "message": f"Stewardship score ({overall_score:.1f}%) below threshold",
                "affected_fields_count": total_issues,
                "recommendation": "Comprehensive data quality review recommended."
            })
        
        # ==================== ISSUES ====================
        
        issues = []
        
        for task in stewardship_tasks[:30]:
            issues.append({
                "issue_id": task["task_id"],
                "agent_id": "stewardship-flagger",
                "field_name": task.get("field", "unknown"),
                "issue_type": task.get("issue_type", "unknown"),
                "severity": "high" if task.get("priority") in ["critical", "high"] else "medium",
                "message": f"{task.get('issue_type')}: {task.get('recommended_action', 'Review required')}"
            })
        
        # ==================== RECOMMENDATIONS ====================
        
        agent_recommendations = []
        
        if critical_count > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_stewardship_critical",
                "agent_id": "stewardship-flagger",
                "field_name": "all",
                "priority": "critical",
                "recommendation": f"Immediately address {critical_count} critical issue(s)",
                "timeline": "immediate"
            })
        
        if issue_counts.get("MISSING_REQUIRED", 0) > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_stewardship_missing",
                "agent_id": "stewardship-flagger",
                "field_name": ", ".join(required_columns[:3]),
                "priority": "high",
                "recommendation": "Implement data collection improvements to prevent missing required fields",
                "timeline": "1 week"
            })
        
        if issue_counts.get("INVALID_FORMAT", 0) > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_stewardship_format",
                "agent_id": "stewardship-flagger",
                "field_name": "validation",
                "priority": "medium",
                "recommendation": "Add input validation at data collection point to prevent format issues",
                "timeline": "2 weeks"
            })
        
        if issue_counts.get("DUPLICATE_SUSPECTED", 0) > 0:
            agent_recommendations.append({
                "recommendation_id": "rec_stewardship_duplicates",
                "agent_id": "stewardship-flagger",
                "field_name": ", ".join(duplicate_key_columns[:3]) if duplicate_key_columns else "all",
                "priority": "medium",
                "recommendation": "Run GoldenRecordBuilder to merge suspected duplicates",
                "timeline": "1 week"
            })
        
        agent_recommendations.append({
            "recommendation_id": "rec_stewardship_workflow",
            "agent_id": "stewardship-flagger",
            "field_name": "all",
            "priority": "medium",
            "recommendation": "Establish stewardship workflow for reviewing and resolving flagged issues",
            "timeline": "2 weeks"
        })
        
        agent_recommendations.append({
            "recommendation_id": "rec_stewardship_monitoring",
            "agent_id": "stewardship-flagger",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Set up automated monitoring for recurring data quality issues",
            "timeline": "1 month"
        })

        # Generate flagged records file
        flagged_df = _generate_flagged_records_df(df, stewardship_tasks, row_level_issues)
        flagged_file_bytes = _generate_flagged_file(flagged_df, filename)
        flagged_file_base64 = base64.b64encode(flagged_file_bytes).decode('utf-8')

        return {
            "status": "success",
            "agent_id": "stewardship-flagger",
            "agent_name": "Stewardship Flagger",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_records": total_rows,
                "total_issues": total_issues,
                "tasks_created": len(stewardship_tasks),
                "critical_issues": critical_count,
                "high_priority_tasks": high_count,
                "records_flagged": len(set(t.get("row_index", -1) for t in stewardship_tasks if t.get("row_index") is not None)),
                "clean_data_rate": round(clean_rate, 1),
                "total_issues_count": len(row_level_issues)
            },
            "data": stewardship_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": agent_recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary,
            "cleaned_file": {
                "filename": f"mastered_{filename}",
                "content": flagged_file_base64,
                "size_bytes": len(flagged_file_bytes),
                "format": filename.split('.')[-1].lower()
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "stewardship-flagger",
            "agent_name": "Stewardship Flagger",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _detect_field_types(df: pl.DataFrame) -> Dict[str, str]:
    """Detect semantic field types for each column."""
    field_types = {}
    
    for col in df.columns:
        col_lower = col.lower()
        detected_type = "unknown"
        
        for field_type, patterns in FIELD_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, col_lower):
                    detected_type = field_type
                    break
            if detected_type != "unknown":
                break
        
        field_types[col] = detected_type
    
    return field_types


def _get_entity_id(df: pl.DataFrame, row_index: int) -> str:
    """Get entity ID for a row."""
    # Look for ID-like columns
    id_columns = [col for col in df.columns if 'id' in col.lower()]
    
    for id_col in id_columns:
        val = df[id_col][row_index]
        if val is not None:
            return str(val)
    
    # Fallback to row index
    return f"row_{row_index}"


def _generate_flagged_records_df(
    df: pl.DataFrame,
    tasks: List[Dict],
    row_level_issues: List[Dict]
) -> pl.DataFrame:
    """Generate the full DataFrame with stewardship flag columns added.
    
    Returns all records with additional columns indicating stewardship status:
    - __stewardship_issues__: Summary of issues for flagged rows (empty for clean rows)
    - __flagged_at__: Timestamp when flagging was performed
    - __needs_review__: Boolean indicating if the row requires stewardship review
    """
    # Collect all flagged row indices
    flagged_rows = set()
    for task in tasks:
        if task.get("row_index") is not None:
            flagged_rows.add(task["row_index"])
    for issue in row_level_issues:
        if issue.get("row_index") is not None:
            flagged_rows.add(issue["row_index"])
    
    # Build issue summary per row
    row_issues = defaultdict(list)
    for issue in row_level_issues:
        idx = issue.get("row_index")
        if idx is not None:
            row_issues[idx].append(f"{issue['issue_type']}:{issue['column']}")
    
    # Add row index for processing
    result_df = df.with_row_index("__row_idx__")
    
    # Build issue summaries and review flags for ALL rows
    issue_summaries = []
    needs_review = []
    for idx in range(df.height):
        issues = row_issues.get(idx, [])
        issue_summaries.append("; ".join(issues[:5]) if issues else "")
        needs_review.append(idx in flagged_rows)
    
    # Add stewardship columns to the full DataFrame
    result_df = result_df.with_columns([
        pl.Series("__stewardship_issues__", issue_summaries),
        pl.lit(datetime.utcnow().isoformat() + "Z").alias("__flagged_at__"),
        pl.Series("__needs_review__", needs_review)
    ])
    
    return result_df.drop("__row_idx__")


def _generate_flagged_file(df: pl.DataFrame, original_filename: str) -> bytes:
    """Generate flagged records file in CSV format."""
    output = io.BytesIO()
    df.write_csv(output)
    return output.getvalue()
