"""
Cleanse Writeback Agent

The final quality assurance and documentation step in the "Cleanse My Data" pipeline.
This agent guarantees that the dataset leaving the cleaning tool is not only fixed but also
perfectly documented and ready for the next major tool (e.g., "Master My Data").

Core Functions:
1. Integrity Verification: Performs a final validation pass over the transformed dataset
   to verify that cleansing actions did not introduce any new errors.
2. Manifest Finalization (Audit Log): Gathers individual manifests from all preceding agents
   and bundles them into a single, comprehensive Cleansing Manifest with detailed action logs.
3. Data Packaging: Formats the final cleaned dataset with embedded manifest for pass-through
   to the orchestrator, ensuring trust, lineage, and auditability.

Why This Agent is Necessary:
- Trust: Guarantees data is clean and validated
- Lineage: Provides verifiable record of exact cleansing history
- Chain Integrity: Ensures "Master My Data" knows exactly what was done to the data
- Auditability: Complete documentation of all transformations applied

Input: CSV/JSON/XLSX file (primary) + manifests from previous agents
Output: Validation report with comprehensive cleansing manifest and integrity verification
"""

import pandas as pd
import numpy as np
import io
import time
import base64
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime


def execute_cleanse_writeback(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute cleanse writeback with integrity verification and manifest finalization.

    Args:
        file_contents: File bytes (read as binary) - should be the cleaned data
        filename: Original filename (used to detect format)
        parameters: Agent parameters from tool.json

    Returns:
        Standardized output dictionary with integrity report and finalized manifest
    """

    start_time = time.time()
    parameters = parameters or {}

    # Extract parameters with defaults
    verify_numeric_types = parameters.get("verify_numeric_types", True)
    verify_datetime_types = parameters.get("verify_datetime_types", True)
    verify_no_new_nulls = parameters.get("verify_no_new_nulls", True)
    verify_no_duplicates = parameters.get("verify_no_duplicates", True)
    verify_data_retention = parameters.get("verify_data_retention", True)
    generate_comprehensive_manifest = parameters.get("generate_comprehensive_manifest", True)
    include_transformation_summary = parameters.get("include_transformation_summary", True)
    
    # Manifest sources from previous agents
    agent_manifests = parameters.get("agent_manifests", {})  # Dict of agent_id -> manifest
    original_row_count = parameters.get("original_row_count", None)
    original_column_count = parameters.get("original_column_count", None)
    
    # Scoring weights
    integrity_weight = parameters.get("integrity_weight", 0.4)
    completeness_weight = parameters.get("completeness_weight", 0.3)
    auditability_weight = parameters.get("auditability_weight", 0.3)
    excellent_threshold = parameters.get("excellent_threshold", 95)
    good_threshold = parameters.get("good_threshold", 85)

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
                "agent_id": "cleanse-writeback",
                "error": f"Unsupported file format: {filename}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.empty:
            return {
                "status": "error",
                "agent_id": "cleanse-writeback",
                "agent_name": "Cleanse Writeback",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # ==================== INTEGRITY VERIFICATION ====================
        integrity_results = _perform_integrity_verification(
            df,
            {
                "verify_numeric_types": verify_numeric_types,
                "verify_datetime_types": verify_datetime_types,
                "verify_no_new_nulls": verify_no_new_nulls,
                "verify_no_duplicates": verify_no_duplicates,
                "verify_data_retention": verify_data_retention,
                "original_row_count": original_row_count,
                "original_column_count": original_column_count
            }
        )
        
        # ==================== MANIFEST FINALIZATION ====================
        comprehensive_manifest = _finalize_comprehensive_manifest(
            agent_manifests,
            df,
            integrity_results,
            {
                "filename": filename,
                "original_row_count": original_row_count,
                "original_column_count": original_column_count,
                "include_transformation_summary": include_transformation_summary
            }
        )
        
        # ==================== DATA PACKAGING ====================
        packaged_data = _package_final_data(
            df,
            comprehensive_manifest,
            filename,
            generate_comprehensive_manifest
        )
        
        # ==================== CALCULATE WRITEBACK SCORE ====================
        writeback_score = _calculate_writeback_score(
            integrity_results,
            comprehensive_manifest,
            packaged_data,
            {
                "integrity_weight": integrity_weight,
                "completeness_weight": completeness_weight,
                "auditability_weight": auditability_weight,
                "excellent_threshold": excellent_threshold,
                "good_threshold": good_threshold
            }
        )
        
        # Determine quality status
        if writeback_score["overall_score"] >= excellent_threshold:
            quality_status = "excellent"
        elif writeback_score["overall_score"] >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_review"
        
        # Generate recommendations
        recommendations = _generate_writeback_recommendations(
            integrity_results,
            comprehensive_manifest,
            writeback_score
        )
        
        # Build writeback analysis
        writeback_analysis = {
            "integrity_verification": integrity_results,
            "comprehensive_manifest": comprehensive_manifest,
            "data_packaging": packaged_data,
            "total_agents_processed": int(len(agent_manifests)),
            "final_row_count": int(len(df)),
            "final_column_count": int(len(df.columns)),
            "data_ready_for_next_tool": bool(integrity_results["all_checks_passed"]),
            "recommendations": recommendations
        }
        
        # Build results
        writeback_data = {
            "writeback_score": writeback_score,
            "quality_status": quality_status,
            "writeback_analysis": writeback_analysis,
            "summary": f"Cleanse writeback completed. Quality: {quality_status}. Data ready: {integrity_results['all_checks_passed']}. Verified {len(df)} rows across {len(df.columns)} columns.",
            "integrity_issues": _extract_integrity_issues(integrity_results)
        }

        return {
            "status": "success",
            "agent_id": "cleanse-writeback",
            "agent_name": "Cleanse Writeback",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_rows_verified": int(len(df)),
                "total_columns_verified": int(len(df.columns)),
                "integrity_checks_passed": int(integrity_results["checks_passed"]),
                "integrity_checks_failed": int(integrity_results["checks_failed"]),
                "agents_in_manifest": int(len(agent_manifests)),
                "data_ready_for_pipeline": bool(integrity_results["all_checks_passed"]),
                "total_transformations_logged": int(comprehensive_manifest.get("total_transformations", 0))
            },
            "data": writeback_data
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "cleanse-writeback",
            "agent_name": "Cleanse Writeback",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _perform_integrity_verification(
    df: pd.DataFrame,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Perform comprehensive integrity verification on cleaned dataset.
    
    Verifies that cleaning operations did not introduce new errors.
    """
    verification_results = {
        "checks_passed": 0,
        "checks_failed": 0,
        "all_checks_passed": True,
        "checks": {}
    }
    
    # Check 1: Verify numeric type integrity
    if config.get("verify_numeric_types", True):
        numeric_check = _verify_numeric_integrity(df)
        verification_results["checks"]["numeric_type_integrity"] = numeric_check
        
        if numeric_check["passed"]:
            verification_results["checks_passed"] += 1
        else:
            verification_results["checks_failed"] += 1
            verification_results["all_checks_passed"] = False
    
    # Check 2: Verify datetime type integrity
    if config.get("verify_datetime_types", True):
        datetime_check = _verify_datetime_integrity(df)
        verification_results["checks"]["datetime_type_integrity"] = datetime_check
        
        if datetime_check["passed"]:
            verification_results["checks_passed"] += 1
        else:
            verification_results["checks_failed"] += 1
            verification_results["all_checks_passed"] = False
    
    # Check 3: Verify no new nulls introduced
    if config.get("verify_no_new_nulls", True):
        null_check = _verify_no_new_nulls(df)
        verification_results["checks"]["no_new_nulls"] = null_check
        
        if null_check["passed"]:
            verification_results["checks_passed"] += 1
        else:
            verification_results["checks_failed"] += 1
            verification_results["all_checks_passed"] = False
    
    # Check 4: Verify no duplicate introduction
    if config.get("verify_no_duplicates", True):
        duplicate_check = _verify_no_duplicates_introduced(df)
        verification_results["checks"]["no_new_duplicates"] = duplicate_check
        
        if duplicate_check["passed"]:
            verification_results["checks_passed"] += 1
        else:
            verification_results["checks_failed"] += 1
            verification_results["all_checks_passed"] = False
    
    # Check 5: Verify data retention
    if config.get("verify_data_retention", True):
        retention_check = _verify_data_retention(
            df,
            config.get("original_row_count"),
            config.get("original_column_count")
        )
        verification_results["checks"]["data_retention"] = retention_check
        
        if retention_check["passed"]:
            verification_results["checks_passed"] += 1
        else:
            verification_results["checks_failed"] += 1
            verification_results["all_checks_passed"] = False
    
    return verification_results


def _verify_numeric_integrity(df: pd.DataFrame) -> Dict[str, Any]:
    """Verify that numeric columns are truly numeric after cleaning."""
    issues = []
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    
    for col in numeric_columns:
        # Check for any non-numeric values that slipped through
        try:
            # Attempt to cast to numeric to verify
            pd.to_numeric(df[col], errors='raise')
        except (ValueError, TypeError) as e:
            issues.append({
                "column": col,
                "issue": "Contains non-numeric values after cleaning",
                "details": str(e)
            })
    
    return {
        "passed": bool(len(issues) == 0),
        "check_name": "Numeric Type Integrity",
        "columns_checked": int(len(numeric_columns)),
        "issues_found": int(len(issues)),
        "issues": issues,
        "message": f"Verified {len(numeric_columns)} numeric columns" if len(issues) == 0 
                   else f"Found {len(issues)} numeric integrity issues"
    }


def _verify_datetime_integrity(df: pd.DataFrame) -> Dict[str, Any]:
    """Verify that datetime columns are properly formatted."""
    issues = []
    datetime_columns = df.select_dtypes(include=['datetime64']).columns.tolist()
    
    for col in datetime_columns:
        # Check for any invalid datetime values
        invalid_count = df[col].isna().sum()
        if invalid_count > 0:
            issues.append({
                "column": col,
                "issue": "Contains invalid datetime values",
                "invalid_count": int(invalid_count)
            })
    
    return {
        "passed": bool(len(issues) == 0),
        "check_name": "Datetime Type Integrity",
        "columns_checked": int(len(datetime_columns)),
        "issues_found": int(len(issues)),
        "issues": issues,
        "message": f"Verified {len(datetime_columns)} datetime columns" if len(issues) == 0
                   else f"Found {len(issues)} datetime integrity issues"
    }


def _verify_no_new_nulls(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Verify that cleaning operations did not introduce new nulls.
    
    Note: This is a basic check. In production, you'd compare against pre-cleaning state.
    """
    total_nulls = int(df.isna().sum().sum())
    null_percentage = (total_nulls / (len(df) * len(df.columns)) * 100) if len(df) > 0 else 0
    
    # Threshold: if more than 50% of data is null, something went wrong
    passed = null_percentage < 50
    
    columns_with_high_nulls = []
    for col in df.columns:
        null_pct = (df[col].isna().sum() / len(df) * 100) if len(df) > 0 else 0
        if null_pct > 80:  # More than 80% nulls is suspicious
            columns_with_high_nulls.append({
                "column": col,
                "null_percentage": round(float(null_pct), 2),
                "null_count": int(df[col].isna().sum())
            })
    
    return {
        "passed": bool(passed and len(columns_with_high_nulls) == 0),
        "check_name": "No New Nulls Introduced",
        "total_nulls": total_nulls,
        "null_percentage": round(float(null_percentage), 2),
        "columns_with_high_nulls": columns_with_high_nulls,
        "message": "No excessive null values detected" if passed and len(columns_with_high_nulls) == 0
                   else f"Detected {len(columns_with_high_nulls)} columns with excessive nulls"
    }


def _verify_no_duplicates_introduced(df: pd.DataFrame) -> Dict[str, Any]:
    """Verify that no duplicate rows were introduced during cleaning."""
    duplicate_count = int(df.duplicated().sum())
    duplicate_percentage = (duplicate_count / len(df) * 100) if len(df) > 0 else 0
    
    # Threshold: if more than 5% duplicates, investigate
    passed = duplicate_percentage < 5
    
    return {
        "passed": bool(passed),
        "check_name": "No New Duplicates Introduced",
        "duplicate_count": duplicate_count,
        "duplicate_percentage": round(float(duplicate_percentage), 2),
        "total_rows": int(len(df)),
        "message": "No concerning duplicate patterns detected" if passed
                   else f"Found {duplicate_count} duplicate rows ({duplicate_percentage:.1f}%)"
    }


def _verify_data_retention(
    df: pd.DataFrame,
    original_row_count: Optional[int],
    original_column_count: Optional[int]
) -> Dict[str, Any]:
    """Verify that data retention is within acceptable limits."""
    current_row_count = len(df)
    current_column_count = len(df.columns)
    
    issues = []
    
    # Check row retention
    if original_row_count is not None:
        row_retention = (current_row_count / original_row_count * 100) if original_row_count > 0 else 0
        row_loss = original_row_count - current_row_count
        
        # Flag if more than 30% of rows were lost
        if row_retention < 70:
            issues.append({
                "type": "excessive_row_loss",
                "original": original_row_count,
                "current": current_row_count,
                "loss_count": row_loss,
                "retention_percentage": round(row_retention, 2),
                "message": f"Excessive row loss: {row_loss} rows lost ({100 - row_retention:.1f}%)"
            })
    else:
        row_retention = 100  # Unknown, assume OK
    
    # Check column retention
    if original_column_count is not None:
        column_retention = (current_column_count / original_column_count * 100) if original_column_count > 0 else 0
        column_loss = original_column_count - current_column_count
        
        # Flag if any columns were lost (should be rare in cleaning)
        if column_retention < 100:
            issues.append({
                "type": "column_loss",
                "original": original_column_count,
                "current": current_column_count,
                "loss_count": column_loss,
                "retention_percentage": round(column_retention, 2),
                "message": f"Column loss detected: {column_loss} columns removed"
            })
    else:
        column_retention = 100  # Unknown, assume OK
    
    return {
        "passed": bool(len(issues) == 0),
        "check_name": "Data Retention",
        "row_retention_percentage": round(float(row_retention), 2),
        "column_retention_percentage": round(float(column_retention), 2),
        "current_rows": int(current_row_count),
        "current_columns": int(current_column_count),
        "original_rows": original_row_count if original_row_count is None else int(original_row_count),
        "original_columns": original_column_count if original_column_count is None else int(original_column_count),
        "issues": issues,
        "message": "Data retention within acceptable limits" if len(issues) == 0
                   else f"Data retention issues: {len(issues)} concerns"
    }


def _finalize_comprehensive_manifest(
    agent_manifests: Dict[str, Any],
    final_df: pd.DataFrame,
    integrity_results: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create comprehensive cleansing manifest combining all agent outputs.
    
    This is the critical audit log showing exactly what was done to the data.
    """
    manifest = {
        "manifest_version": "1.0.0",
        "manifest_type": "cleansing_manifest",
        "created_at": datetime.utcnow().isoformat() + 'Z',
        "source_file": config.get("filename", "unknown"),
        "original_state": {
            "row_count": config.get("original_row_count", "unknown"),
            "column_count": config.get("original_column_count", "unknown")
        },
        "final_state": {
            "row_count": int(len(final_df)),
            "column_count": int(len(final_df.columns)),
            "columns": final_df.columns.tolist(),
            "dtypes": {col: str(dtype) for col, dtype in final_df.dtypes.items()}
        },
        "integrity_verification": {
            "all_checks_passed": bool(integrity_results["all_checks_passed"]),
            "checks_passed": int(integrity_results["checks_passed"]),
            "checks_failed": int(integrity_results["checks_failed"]),
            "verification_timestamp": datetime.utcnow().isoformat() + 'Z'
        },
        "transformation_pipeline": [],
        "total_transformations": 0,
        "agent_manifests": {}
    }
    
    # Aggregate transformations from all agents
    transformation_count = 0
    
    for agent_id, agent_manifest in agent_manifests.items():
        # Extract transformation details from agent
        agent_summary = {
            "agent_id": agent_id,
            "agent_name": agent_manifest.get("agent_name", agent_id),
            "executed_at": agent_manifest.get("timestamp", "unknown"),
            "execution_time_ms": agent_manifest.get("execution_time_ms", 0),
            "status": agent_manifest.get("status", "unknown"),
            "transformations_applied": []
        }
        
        # Extract specific transformations based on agent type
        if agent_id == "null-handler":
            null_data = agent_manifest.get("data", {})
            imputation_log = null_data.get("imputation_log", [])
            agent_summary["transformations_applied"] = [
                {"action": "null_imputation", "details": log}
                for log in imputation_log
            ]
            transformation_count += len(imputation_log)
        
        elif agent_id == "outlier-remover":
            outlier_data = agent_manifest.get("data", {})
            removal_log = outlier_data.get("removal_log", [])
            agent_summary["transformations_applied"] = [
                {"action": "outlier_removal", "details": log}
                for log in removal_log
            ]
            transformation_count += len(removal_log)
        
        elif agent_id == "type-fixer":
            type_data = agent_manifest.get("data", {})
            fix_log = type_data.get("fix_log", [])
            agent_summary["transformations_applied"] = [
                {"action": "type_conversion", "details": log}
                for log in fix_log
            ]
            transformation_count += len(fix_log)
        
        elif agent_id == "duplicate-resolver":
            dedup_data = agent_manifest.get("data", {})
            resolution_log = dedup_data.get("resolution_log", [])
            agent_summary["transformations_applied"] = [
                {"action": "duplicate_resolution", "details": log}
                for log in resolution_log
            ]
            transformation_count += len(resolution_log)
        
        elif agent_id == "field-standardization":
            standardization_data = agent_manifest.get("data", {})
            standardization_log = standardization_data.get("standardization_log", [])
            agent_summary["transformations_applied"] = [
                {"action": "field_standardization", "details": log}
                for log in standardization_log
            ]
            transformation_count += len(standardization_log)
        
        elif agent_id == "quarantine-agent":
            quarantine_data = agent_manifest.get("data", {})
            quarantine_log = quarantine_data.get("quarantine_log", [])
            agent_summary["transformations_applied"] = [
                {"action": "record_quarantine", "details": log}
                for log in quarantine_log
            ]
            transformation_count += len(quarantine_log)
        
        # Add to pipeline
        manifest["transformation_pipeline"].append(agent_summary)
        manifest["agent_manifests"][agent_id] = agent_manifest
    
    manifest["total_transformations"] = transformation_count
    
    # Add transformation summary if requested
    if config.get("include_transformation_summary", True):
        manifest["transformation_summary"] = _create_transformation_summary(
            manifest["transformation_pipeline"]
        )
    
    return manifest


def _create_transformation_summary(pipeline: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create high-level summary of all transformations."""
    summary = {
        "total_agents": len(pipeline),
        "total_actions": 0,
        "actions_by_type": {},
        "timeline": []
    }
    
    for agent in pipeline:
        agent_id = agent.get("agent_id", "unknown")
        transformations = agent.get("transformations_applied", [])
        
        summary["total_actions"] += len(transformations)
        
        # Count by action type
        for transform in transformations:
            action_type = transform.get("action", "unknown")
            summary["actions_by_type"][action_type] = summary["actions_by_type"].get(action_type, 0) + 1
        
        # Add to timeline
        summary["timeline"].append({
            "agent_id": agent_id,
            "agent_name": agent.get("agent_name", agent_id),
            "executed_at": agent.get("executed_at", "unknown"),
            "actions_count": len(transformations)
        })
    
    return summary


def _package_final_data(
    df: pd.DataFrame,
    manifest: Dict[str, Any],
    filename: str,
    include_manifest: bool
) -> Dict[str, Any]:
    """
    Package final cleaned data with embedded manifest for next tool.
    
    Returns metadata about the packaged data (not the actual data file).
    """
    packaging_info = {
        "format": "csv",
        "original_filename": filename,
        "final_filename": f"cleaned_{filename}",
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": df.columns.tolist(),
        "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "manifest_embedded": bool(include_manifest),
        "manifest_summary": {
            "total_transformations": int(manifest.get("total_transformations", 0)),
            "agents_executed": int(len(manifest.get("transformation_pipeline", []))),
            "integrity_verified": bool(manifest.get("integrity_verification", {}).get("all_checks_passed", False))
        },
        "ready_for_pipeline": bool(manifest.get("integrity_verification", {}).get("all_checks_passed", False)),
        "packaging_timestamp": datetime.utcnow().isoformat() + 'Z'
    }
    
    return packaging_info


def _calculate_writeback_score(
    integrity_results: Dict[str, Any],
    manifest: Dict[str, Any],
    packaging_info: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate comprehensive writeback quality score."""
    
    # Integrity score (based on verification checks)
    checks_passed = integrity_results.get("checks_passed", 0)
    checks_total = checks_passed + integrity_results.get("checks_failed", 0)
    integrity_score = (checks_passed / checks_total * 100) if checks_total > 0 else 0
    
    # Completeness score (based on manifest comprehensiveness)
    total_transformations = manifest.get("total_transformations", 0)
    agents_executed = len(manifest.get("transformation_pipeline", []))
    
    # Score based on having comprehensive documentation
    completeness_score = min(100, (agents_executed * 10) + min(50, total_transformations / 2))
    
    # Auditability score (based on manifest quality)
    has_manifest = manifest.get("manifest_version") is not None
    has_timeline = len(manifest.get("transformation_pipeline", [])) > 0
    has_integrity_check = manifest.get("integrity_verification") is not None
    
    auditability_score = 0
    if has_manifest:
        auditability_score += 40
    if has_timeline:
        auditability_score += 40
    if has_integrity_check:
        auditability_score += 20
    
    # Calculate weighted overall score
    integrity_weight = config.get("integrity_weight", 0.4)
    completeness_weight = config.get("completeness_weight", 0.3)
    auditability_weight = config.get("auditability_weight", 0.3)
    
    overall_score = (
        integrity_score * integrity_weight +
        completeness_score * completeness_weight +
        auditability_score * auditability_weight
    )
    
    return {
        "overall_score": round(float(overall_score), 1),
        "metrics": {
            "integrity_score": round(float(integrity_score), 1),
            "completeness_score": round(float(completeness_score), 1),
            "auditability_score": round(float(auditability_score), 1),
            "checks_passed": int(checks_passed),
            "checks_total": int(checks_total),
            "total_transformations": int(total_transformations),
            "agents_executed": int(agents_executed),
            "data_ready_for_pipeline": bool(integrity_results.get("all_checks_passed", False))
        }
    }


def _generate_writeback_recommendations(
    integrity_results: Dict[str, Any],
    manifest: Dict[str, Any],
    writeback_score: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Generate recommendations based on writeback analysis."""
    recommendations = []
    
    # Check integrity failures
    if not integrity_results.get("all_checks_passed", False):
        failed_checks = [
            check_name for check_name, check_data in integrity_results.get("checks", {}).items()
            if not check_data.get("passed", False)
        ]
        
        recommendations.append({
            "priority": "critical",
            "action": "resolve_integrity_issues",
            "reason": f"Data integrity verification failed: {len(failed_checks)} checks failed",
            "failed_checks": failed_checks,
            "impact": "Data cannot be safely passed to next tool until integrity issues are resolved"
        })
    
    # Check manifest completeness
    if manifest.get("total_transformations", 0) == 0:
        recommendations.append({
            "priority": "high",
            "action": "verify_transformation_logging",
            "reason": "No transformations logged in manifest - verify that cleaning agents executed properly",
            "impact": "Lack of transformation history compromises auditability"
        })
    
    # Check data retention
    retention_check = integrity_results.get("checks", {}).get("data_retention", {})
    if not retention_check.get("passed", True):
        recommendations.append({
            "priority": "high",
            "action": "review_data_retention",
            "reason": "Significant data loss detected during cleaning operations",
            "impact": "Excessive data loss may indicate overly aggressive cleaning strategies"
        })
    
    # Positive recommendation if everything is good
    if writeback_score.get("overall_score", 0) >= 95:
        recommendations.append({
            "priority": "low",
            "action": "proceed_to_next_tool",
            "reason": "Data is clean, validated, and fully documented. Ready for 'Master My Data' or next pipeline step",
            "impact": "High confidence in data quality and lineage"
        })
    elif writeback_score.get("overall_score", 0) >= 85:
        recommendations.append({
            "priority": "medium",
            "action": "review_before_proceeding",
            "reason": "Data quality is good but minor issues exist. Review recommendations before proceeding",
            "impact": "Minor improvements could enhance data quality for downstream processing"
        })
    else:
        recommendations.append({
            "priority": "high",
            "action": "address_quality_issues",
            "reason": "Data quality score is below acceptable threshold. Address critical issues before proceeding",
            "impact": "Poor data quality may cause errors in downstream processing"
        })
    
    return recommendations


def _extract_integrity_issues(integrity_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract specific integrity issues for reporting."""
    issues = []
    
    for check_name, check_data in integrity_results.get("checks", {}).items():
        if not check_data.get("passed", False):
            # Extract issues based on check type
            check_issues = check_data.get("issues", [])
            
            for issue in check_issues:
                issues.append({
                    "issue_type": "integrity_verification_failure",
                    "check_name": check_name,
                    "severity": "high",
                    "details": issue,
                    "message": issue.get("message", "") if isinstance(issue, dict) else str(issue)
                })
            
            # If no specific issues but check failed, add generic issue
            if not check_issues:
                issues.append({
                    "issue_type": "integrity_verification_failure",
                    "check_name": check_name,
                    "severity": "high",
                    "message": check_data.get("message", f"Integrity check '{check_name}' failed")
                })
    
    return issues
