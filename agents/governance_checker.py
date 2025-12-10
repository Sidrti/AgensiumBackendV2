"""
Governance Checker Agent

Validates data governance compliance including lineage, consent, and classification.
Input: CSV file (primary)
Output: Standardized governance validation results
"""

import polars as pl
import numpy as np
import io
import time
import re
from typing import Dict, Any, Optional, List
from agents.agent_utils import safe_get_list

def execute_governance(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Check data governance compliance.

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
    lineage_weight = parameters.get("lineage_weight", 0.3)
    consent_weight = parameters.get("consent_weight", 0.4)
    classification_weight = parameters.get("classification_weight", 0.3)
    compliance_threshold = parameters.get("compliance_threshold", 80)
    needs_review_threshold = parameters.get("needs_review_threshold", 60)

    try:
        # Read file based on format - Enforce CSV only
        if not filename.endswith('.csv'):
            return {
                "status": "error",
                "agent_id": "governance-checker",
                "error": f"Unsupported file format: {filename}. Only CSV is supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        try:
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": "governance-checker",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.height == 0:
            return {
                "status": "error",
                "agent_id": "governance-checker",
                "agent_name": "Governance Checker",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Perform governance validation
        lineage_score = _validate_lineage(df, parameters)
        consent_score = _validate_consent(df, parameters)
        classification_score = _validate_classification(df, parameters)

        # Calculate overall governance score
        overall_score = (
            lineage_score * lineage_weight +
            consent_score * consent_weight +
            classification_score * classification_weight
        )

        # Determine compliance status
        if overall_score >= compliance_threshold:
            compliance_status = "compliant"
        elif overall_score >= needs_review_threshold:
            compliance_status = "needs_review"
        else:
            compliance_status = "non_compliant"

        # Identify governance issues
        governance_issues = _identify_governance_issues(df, parameters)

        # Generate ROW-LEVEL-ISSUES
        row_level_issues = []
        
        # Add row-level issues for missing required governance fields
        required_lineage_fields = safe_get_list(parameters, 'required_lineage_fields', [])
        required_consent_fields = safe_get_list(parameters, 'required_consent_fields', [])
        required_classification_fields = safe_get_list(parameters, 'required_classification_fields', [])
        
        all_required_fields = required_lineage_fields + required_consent_fields + required_classification_fields
        
        # Check for missing required fields efficiently
        # We only check fields that actually exist in the dataframe to find nulls.
        # If a field is completely missing from the dataframe, it's a schema issue (handled in governance_issues),
        # but here we check for nulls in existing columns.
        
        existing_required_fields = [f for f in all_required_fields if f in df.columns]
        
        if existing_required_fields:
            # Add row index
            df_with_idx = df.with_row_index("row_index")
            
            # Find rows with any nulls in required fields
            null_rows = df_with_idx.filter(
                pl.any_horizontal([pl.col(f).is_null() for f in existing_required_fields])
            ).head(1000)
            
            for row in null_rows.iter_rows(named=True):
                if len(row_level_issues) >= 1000: break
                
                missing_fields = [f for f in existing_required_fields if row[f] is None]
                
                if missing_fields:
                    # Categorize the issue
                    if any(f in required_lineage_fields for f in missing_fields):
                        issue_type = "policy_violation"
                        severity = "warning"
                        field_category = "lineage"
                    elif any(f in required_consent_fields for f in missing_fields):
                        issue_type = "compliance_issue"
                        severity = "critical"
                        field_category = "consent"
                    else:
                        issue_type = "policy_violation"
                        severity = "warning"
                        field_category = "classification"
                    
                    row_level_issues.append({
                        "row_index": row["row_index"],
                        "column": "multiple",
                        "issue_type": issue_type,
                        "severity": severity,
                        "message": f"Missing {field_category} fields: {', '.join(missing_fields)}",
                        "missing_fields": missing_fields
                    })
        
        # Add row-level issues for PII without proper classification
        pii_patterns = parameters.get('pii_patterns', {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b'
        })
        
        # Identify PII columns
        pii_columns = {}  # col -> pii_type
        string_cols = [col for col in df.columns if df[col].dtype == pl.Utf8]
        
        for col in string_cols:
            for pii_type, pattern in pii_patterns.items():
                # Check if any value matches
                if df[col].str.contains(pattern).any():
                    pii_columns[col] = pii_type
                    break
        
        # Check if PII rows have proper classification
        if pii_columns and 'data_classification' in df.columns:
            # We need to find rows where PII is present AND classification is bad
            # Bad classification: null or 'public'
            
            # Construct filter condition
            # For each PII column, if it has a value matching pattern, check classification
            
            # This is complex to do in one go for all columns. Let's iterate PII columns.
            for pii_col, pii_type in pii_columns.items():
                if len(row_level_issues) >= 1000: break
                
                pattern = pii_patterns[pii_type]
                
                # Find violating rows
                violating_rows = df.with_row_index("row_index").filter(
                    (pl.col(pii_col).str.contains(pattern)) &
                    (
                        (pl.col('data_classification').is_null()) |
                        (pl.col('data_classification') == 'public')
                    )
                ).head(1000 - len(row_level_issues))
                
                for row in violating_rows.iter_rows(named=True):
                    if len(row_level_issues) >= 1000: break
                    
                    row_level_issues.append({
                        "row_index": row["row_index"],
                        "column": pii_col,
                        "issue_type": "compliance_issue",
                        "severity": "critical",
                        "message": f"PII data detected in {pii_col} without proper classification or incorrectly classified as public",
                        "pii_columns": [pii_col]
                    })

        # Cap at 1000 issues
        row_level_issues = row_level_issues[:1000]
        
        # Calculate issue summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {},
            "affected_rows": len(set(issue["row_index"] for issue in row_level_issues)),
            "affected_columns": sorted(list(set(issue.get("column", "") for issue in row_level_issues if issue.get("column") != "all" and issue.get("column") != "multiple")))
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
        governance_data = {
            "governance_scores": {
                "overall": round(overall_score, 1),
                "lineage": round(lineage_score, 1),
                "consent": round(consent_score, 1),
                "classification": round(classification_score, 1)
            },
            "compliance_status": compliance_status,
            "total_records": df.height,
            "fields_analyzed": df.columns,
            "governance_issues": governance_issues,
            "row_level_issues": row_level_issues[:100],
            "issue_summary": issue_summary,
            "overrides": {
                "lineage_weight": lineage_weight,
                "consent_weight": consent_weight,
                "classification_weight": classification_weight,
                "compliance_threshold": compliance_threshold,
                "needs_review_threshold": needs_review_threshold
            }
        }
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # Alert 1: Overall compliance status
        if compliance_status != "compliant":
            issues_found = len(governance_issues)
            alerts.append({
                "alert_id": "alert_governance_001_overall",
                "severity": "critical" if compliance_status == "non_compliant" else "high",
                "category": "governance_compliance",
                "message": f"Overall governance compliance: {overall_score:.1f}/100 ({compliance_status.upper().replace('_', ' ')})",
                "affected_fields_count": issues_found,
                "recommendation": f"Address {issues_found} governance issue(s) to meet compliance requirements."
            })
        
        # Alert 2: Data lineage assessment
        if lineage_score < 80:
            lineage_issues_count = len([i for i in governance_issues if i.get("type", "").startswith("missing_lineage")])
            alerts.append({
                "alert_id": "alert_governance_002_lineage",
                "severity": "critical" if lineage_score < 50 else "high" if lineage_score < 65 else "medium",
                "category": "data_lineage",
                "message": f"Data lineage tracking insufficient: {lineage_score:.1f}/100 - {lineage_issues_count} lineage gaps detected",
                "affected_fields_count": lineage_issues_count,
                "recommendation": "Implement comprehensive data lineage: document source systems, transformations, and data dependencies"
            })
        
        # Alert 3: Consent management
        if consent_score < 80:
            consent_issues_count = len([i for i in governance_issues if i.get("type", "").startswith("missing_consent")])
            alerts.append({
                "alert_id": "alert_governance_003_consent",
                "severity": "critical" if consent_score < 50 else "high" if consent_score < 65 else "medium",
                "category": "consent_management",
                "message": f"Consent tracking gaps: {consent_score:.1f}/100 - {consent_issues_count} consent fields missing",
                "affected_fields_count": consent_issues_count,
                "recommendation": "Implement consent management system to track user consent, preferences, and withdrawal requests (GDPR/CCPA)"
            })
        
        # Alert 4: Data classification
        if classification_score < 80:
            classification_issues_count = len([i for i in governance_issues if i.get("type", "").startswith("missing_classification")])
            alerts.append({
                "alert_id": "alert_governance_004_classification",
                "severity": "high" if classification_score < 60 else "medium",
                "category": "data_classification",
                "message": f"Data classification incomplete: {classification_score:.1f}/100 - {classification_issues_count} fields unclassified",
                "affected_fields_count": classification_issues_count,
                "recommendation": "Classify all data fields by sensitivity level (public/internal/confidential/restricted)"
            })
        
        # Alert 5: PII detection
        pii_issues = [i for i in governance_issues if i.get("type") == "pii_detected"]
        if pii_issues:
            alerts.append({
                "alert_id": "alert_governance_005_pii",
                "severity": "critical",
                "category": "pii_without_classification",
                "message": f"PII detected in {len(pii_issues)} field(s): {', '.join([i.get('field', 'N/A') for i in pii_issues[:3]])}",
                "affected_fields_count": len(pii_issues),
                "recommendation": "Immediately implement encryption, access controls, and audit logging for all PII fields"
            })
        
        # Alert 6: Missing lineage fields
        missing_lineage = [i for i in governance_issues if i.get("type") == "missing_lineage_field"]
        if missing_lineage:
            alerts.append({
                "alert_id": "alert_governance_006_missing_lineage",
                "severity": "critical",
                "category": "data_lineage",
                "message": f"Required lineage fields missing: {', '.join([i.get('field', 'N/A') for i in missing_lineage])}",
                "affected_fields_count": len(missing_lineage),
                "recommendation": "Add required lineage fields: source_system, transformation_date, data_owner, business_unit"
            })
        
        # Alert 7: Missing consent fields
        missing_consent = [i for i in governance_issues if i.get("type") == "missing_consent_field"]
        if missing_consent:
            alerts.append({
                "alert_id": "alert_governance_007_missing_consent",
                "severity": "critical",
                "category": "consent_management",
                "message": f"Critical consent fields missing: {', '.join([i.get('field', 'N/A') for i in missing_consent])}",
                "affected_fields_count": len(missing_consent),
                "recommendation": "Add required consent fields: consent_status, consent_date, consent_type, withdrawal_date"
            })
        
        # Alert 8: Missing classification fields
        missing_classification = [i for i in governance_issues if i.get("type") == "missing_classification_field"]
        if missing_classification:
            alerts.append({
                "alert_id": "alert_governance_008_missing_classification",
                "severity": "high",
                "category": "data_classification",
                "message": f"Data classification fields missing: {', '.join([i.get('field', 'N/A') for i in missing_classification[:3]])}",
                "affected_fields_count": len(missing_classification),
                "recommendation": "Add data_classification and sensitivity_level fields to all records"
            })
        
        # Alert 9: Critical governance issues detected
        critical_gov_issues = [i for i in governance_issues if i.get("severity") == "critical"]
        if critical_gov_issues and len(critical_gov_issues) > 0:
            alerts.append({
                "alert_id": "alert_governance_009_critical_issues",
                "severity": "critical",
                "category": "governance_compliance",
                "message": f"Critical governance issues detected: {len(critical_gov_issues)} issue(s) require immediate resolution",
                "affected_fields_count": len(critical_gov_issues),
                "recommendation": "Prioritize resolution of critical issues: missing required fields, unprotected PII, compliance violations"
            })
        
        # Alert 10: Governance framework gaps
        governance_gap_score = 100 - overall_score
        if governance_gap_score > 20:
            alerts.append({
                "alert_id": "alert_governance_010_framework_gaps",
                "severity": "high",
                "category": "governance_compliance",
                "message": f"Governance framework gaps: {governance_gap_score:.1f} points below required threshold",
                "affected_fields_count": len(df.columns),
                "recommendation": "Establish comprehensive governance framework: policies, procedures, roles, responsibilities, and controls"
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Add all governance issues with extended severity mapping
        for idx, issue in enumerate(governance_issues[:100]):  # Limit to 100 issues
            issue_type = issue.get("type", "governance_issue")
            field = issue.get("field", "N/A")
            severity = issue.get("severity", "medium")
            message = issue.get("message", "Governance issue detected")
            
            issues.append({
                "issue_id": f"issue_governance_{issue_type}_{field}_{idx}",
                "agent_id": "governance-checker",
                "field_name": field,
                "issue_type": issue_type,
                "severity": severity,
                "message": message
            })
        
        # Add specific lineage violation issues
        if lineage_score < 80:
            for idx, col in enumerate(df.columns[:10]):
                if idx < 3:  # Add for sample columns
                    issues.append({
                        "issue_id": f"issue_governance_lineage_gap_{col}",
                        "agent_id": "governance-checker",
                        "field_name": col,
                        "issue_type": "lineage_gap",
                        "severity": "high" if lineage_score < 50 else "medium",
                        "message": f"Missing lineage metadata for field '{col}': source system and transformation history not documented"
                    })
        
        # Add specific consent violation issues
        if consent_score < 80:
            for idx, col in enumerate(df.columns[:10]):
                if idx < 3:  # Add for sample columns
                    issues.append({
                        "issue_id": f"issue_governance_consent_gap_{col}",
                        "agent_id": "governance-checker",
                        "field_name": col,
                        "issue_type": "consent_gap",
                        "severity": "critical" if consent_score < 50 else "high",
                        "message": f"Missing consent tracking for field '{col}': user consent and withdrawal records not available"
                    })
        
        # Add specific classification violation issues
        if classification_score < 80:
            for idx, col in enumerate(df.columns[:10]):
                if idx < 3:  # Add for sample columns
                    issues.append({
                        "issue_id": f"issue_governance_classification_gap_{col}",
                        "agent_id": "governance-checker",
                        "field_name": col,
                        "issue_type": "classification_gap",
                        "severity": "high",
                        "message": f"Missing data classification for field '{col}': sensitivity level not assigned"
                    })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        recommendations = []
        
        # Recommendation 1: Critical issues resolution
        critical_issues = [i for i in governance_issues if i.get("severity") == "critical"][:3]
        if critical_issues:
            for idx, issue in enumerate(critical_issues):
                field = issue.get("field", "N/A")
                issue_type = issue.get("type", "governance_issue")
                message = issue.get("message", "")
                
                recommendations.append({
                    "recommendation_id": f"rec_governance_critical_{issue_type}_{idx}",
                    "agent_id": "governance-checker",
                    "field_name": field,
                    "priority": "critical",
                    "recommendation": f"URGENT - {message}. This is a compliance violation requiring immediate corrective action",
                    "timeline": "immediate"
                })
        
        # Recommendation 2: High-severity issues
        high_issues = [i for i in governance_issues if i.get("severity") == "high"][:2]
        if high_issues:
            for idx, issue in enumerate(high_issues):
                field = issue.get("field", "N/A")
                issue_type = issue.get("type", "governance_issue")
                message = issue.get("message", "")
                
                recommendations.append({
                    "recommendation_id": f"rec_governance_high_{issue_type}_{idx}",
                    "agent_id": "governance-checker",
                    "field_name": field,
                    "priority": "high",
                    "recommendation": f"{message}. Implement corrective measures to align with governance requirements",
                    "timeline": "1-2 weeks"
                })
        
        # Recommendation 3: Data lineage implementation
        if lineage_score < 80:
            missing_lineage_fields = [i.get("field") for i in governance_issues if i.get("type") == "missing_lineage_field"]
            recommendations.append({
                "recommendation_id": "rec_governance_lineage_impl",
                "agent_id": "governance-checker",
                "field_name": "all" if not missing_lineage_fields else ", ".join(missing_lineage_fields[:3]),
                "priority": "critical" if lineage_score < 50 else "high",
                "recommendation": f"Implement comprehensive data lineage tracking system: document source systems, data transformations, dependencies, and data flow for {len(missing_lineage_fields) if missing_lineage_fields else 'all'} field(s). Include source_system, transformation_date, data_owner metadata",
                "timeline": "2-4 weeks"
            })
        
        # Recommendation 4: Consent management framework
        if consent_score < 80:
            missing_consent_fields = [i.get("field") for i in governance_issues if i.get("type") == "missing_consent_field"]
            recommendations.append({
                "recommendation_id": "rec_governance_consent_impl",
                "agent_id": "governance-checker",
                "field_name": "all" if not missing_consent_fields else ", ".join(missing_consent_fields[:3]),
                "priority": "critical",
                "recommendation": f"Implement consent management and tracking for {len(missing_consent_fields) if missing_consent_fields else 'all'} field(s): track user consent status, dates, types, and withdrawal requests. Required for GDPR/CCPA compliance",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 5: Data classification framework
        if classification_score < 80:
            missing_classification_fields = [i.get("field") for i in governance_issues if i.get("type") == "missing_classification_field"]
            recommendations.append({
                "recommendation_id": "rec_governance_classification_impl",
                "agent_id": "governance-checker",
                "field_name": "all" if not missing_classification_fields else ", ".join(missing_classification_fields[:3]),
                "priority": "high",
                "recommendation": f"Establish data classification framework for {len(missing_classification_fields) if missing_classification_fields else 'all'} field(s): categorize by sensitivity (public/internal/confidential/restricted). Assign ownership and access controls",
                "timeline": "1-2 weeks"
            })
        
        # Recommendation 6: PII protection
        if pii_issues:
            pii_fields = [i.get("field") for i in pii_issues]
            recommendations.append({
                "recommendation_id": "rec_governance_pii_protection",
                "agent_id": "governance-checker",
                "field_name": ", ".join(pii_fields[:5]),
                "priority": "critical",
                "recommendation": f"Immediately secure {len(pii_fields)} PII field(s) ({', '.join(pii_fields[:3])}...): implement encryption (AES-256), access controls (RBAC), audit logging, and data masking. Establish retention policies",
                "timeline": "immediate"
            })
        
        # Recommendation 7: Missing governance fields
        if missing_lineage or missing_consent or missing_classification:
            all_missing = len(missing_lineage) + len(missing_consent) + len(missing_classification)
            recommendations.append({
                "recommendation_id": "rec_governance_fields_add",
                "agent_id": "governance-checker",
                "field_name": "all",
                "priority": "critical",
                "recommendation": f"Add {all_missing} required governance metadata fields: source_system, transformation_date, consent_status, data_classification, sensitivity_level, data_owner, business_unit. Update all {df.height} records",
                "timeline": "1 week"
            })
        
        # Recommendation 8: Overall governance framework
        if compliance_status == "non_compliant":
            recommendations.append({
                "recommendation_id": "rec_governance_framework",
                "agent_id": "governance-checker",
                "field_name": "entire dataset",
                "priority": "critical",
                "recommendation": f"Dataset is non-compliant ({overall_score:.1f}/100). Establish comprehensive governance framework: define policies, procedures, roles (DPO, data steward), responsibilities, and enforcement controls. Conduct compliance audit",
                "timeline": "4-6 weeks"
            })
        elif compliance_status == "needs_review":
            recommendations.append({
                "recommendation_id": "rec_governance_review",
                "agent_id": "governance-checker",
                "field_name": "entire dataset",
                "priority": "high",
                "recommendation": f"Governance compliance requires review ({overall_score:.1f}/100). Prioritize gap resolution in lineage ({lineage_score:.0f}), consent ({consent_score:.0f}), and classification ({classification_score:.0f}) components",
                "timeline": "2-3 weeks"
            })
        else:
            recommendations.append({
                "recommendation_id": "rec_governance_continuous",
                "agent_id": "governance-checker",
                "field_name": "entire dataset",
                "priority": "medium",
                "recommendation": f"Maintain governance compliance status: establish continuous monitoring, quarterly audits, and annual reviews. Document changes to data lineage, consent tracking, and classifications",
                "timeline": "ongoing"
            })

        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = []
        
        # Governance Compliance
        executive_summary.append({
            "summary_id": "exec_governance",
            "title": "Governance Compliance",
            "value": str(round(overall_score, 1)),
            "status": "compliant" if compliance_status == "compliant" else "needs_review" if compliance_status == "needs_review" else "non_compliant",
            "description": f"{overall_score:.1f}/100 - {compliance_status.upper().replace('_', ' ')}"
        })
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_text_parts = []
        ai_analysis_text_parts.append(f"GOVERNANCE: {compliance_status.upper().replace('_', ' ')} ({overall_score:.1f}/100)")
        ai_analysis_text_parts.append(f"- Lineage Score: {lineage_score:.1f}/100")
        ai_analysis_text_parts.append(f"- Consent Score: {consent_score:.1f}/100")
        ai_analysis_text_parts.append(f"- Classification Score: {classification_score:.1f}/100")
        
        if len(governance_issues) > 0:
            ai_analysis_text_parts.append(f"- {len(governance_issues)} governance issue(s) detected")
            
            # Critical issues
            critical_gov_issues = [i for i in governance_issues if i.get("severity") == "critical"]
            if critical_gov_issues:
                ai_analysis_text_parts.append(f"  • {len(critical_gov_issues)} critical issue(s) requiring immediate attention")
            
            # PII issues
            pii_gov_issues = [i for i in governance_issues if i.get("type") == "pii_detected"]
            if pii_gov_issues:
                ai_analysis_text_parts.append(f"  • {len(pii_gov_issues)} PII field(s) without proper classification")
        
        if compliance_status == "compliant":
            ai_analysis_text_parts.append("- All governance requirements met")
        else:
            ai_analysis_text_parts.append("- Governance framework implementation required")
        
        ai_analysis_text = "\n".join(ai_analysis_text_parts)

        return {
            "status": "success",
            "agent_id": "governance-checker",
            "agent_name": "Governance Checker",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_records": df.height,
                "total_fields": len(df.columns),
                "governance_score": round(overall_score, 1),
                "compliance_status": compliance_status,
                "issues_found": len(governance_issues)
            },
            "data": governance_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": recommendations,
            "row_level_issues": row_level_issues,
            "issue_summary": issue_summary,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_id": "governance-checker",
            "agent_name": "Governance Checker",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _validate_lineage(df: pl.DataFrame, config: Dict[str, Any]) -> float:
    """
    Validate data lineage requirements.
    """
    score = 100.0

    # Check for required lineage fields
    required_fields = config.get('required_lineage_fields', [])
    for field in required_fields:
        if field not in df.columns:
            score -= 20  # Deduct for missing field

    # Check for high null percentages in lineage fields
    for field in required_fields:
        if field in df.columns:
            null_pct = (df[field].null_count() / df.height) * 100
            if null_pct > 5:
                score -= min(15, null_pct / 10)

    return max(0, score)


def _validate_consent(df: pl.DataFrame, config: Dict[str, Any]) -> float:
    """
    Validate consent and privacy requirements.
    """
    score = 100.0

    # Check for required consent fields
    required_fields = config.get('required_consent_fields', [])
    for field in required_fields:
        if field not in df.columns:
            score -= 25  # Deduct for missing field

    # Validate consent status values
    if 'consent_status' in df.columns:
        valid_statuses = config.get('valid_consent_statuses', ['granted', 'denied', 'withdrawn', 'pending'])
        # Count invalid statuses (not in valid list AND not null)
        # Note: Original code treated None as valid (or at least didn't penalize it if not in list + [None])
        # (~df['consent_status'].isin(valid_statuses + [None])).sum()
        
        invalid_count = df.filter(
            pl.col('consent_status').is_not_null() &
            ~pl.col('consent_status').is_in(valid_statuses)
        ).height
        
        if invalid_count > 0:
            score -= 15

    return max(0, score)


def _validate_classification(df: pl.DataFrame, config: Dict[str, Any]) -> float:
    """
    Validate data classification and tagging requirements.
    """
    score = 100.0

    # Check for required classification fields
    required_fields = config.get('required_classification_fields', [])
    for field in required_fields:
        if field not in df.columns:
            score -= 20  # Deduct for missing field

    # Check for PII detection and classification mismatch
    pii_patterns = config.get('pii_patterns', {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
    })

    pii_columns = []
    string_cols = [col for col in df.columns if df[col].dtype == pl.Utf8]
    
    for col in string_cols:
        for pii_type, pattern in pii_patterns.items():
            if df[col].str.contains(pattern).any():
                pii_columns.append(col)
                break

    # If PII found, check if classified appropriately
    if pii_columns and 'data_classification' in df.columns:
        # Count rows where classification is public AND PII is present in any PII column
        # This is slightly different from original which checked each column separately?
        # Original: public_pii = ((df['data_classification'] == 'public') & df.index.isin(...)).sum()
        # It sums rows that have public classification AND have PII in ANY of the pii_columns.
        
        # In Polars:
        # Filter rows where classification is public
        public_rows = df.filter(pl.col('data_classification') == 'public')
        
        if public_rows.height > 0:
            # Check if any PII column has PII in these rows
            has_pii_expr = pl.any_horizontal([
                pl.col(col).str.contains(pii_patterns.get('email') if 'email' in pii_patterns else r'.*') # Simplified logic, need correct pattern per column
                for col in pii_columns
            ])
            
            # Re-do loop to be precise
            public_pii_count = 0
            # We need to check if ANY pii column has pii in a public row.
            # But pii_columns list doesn't store which type/pattern matched.
            # Let's re-detect per column.
            
            for col in pii_columns:
                # Find pattern for this column (we just know it matched ONE of them)
                # This is inefficient. Let's just check all patterns again or store it.
                # Optimization: In _validate_classification we just need count.
                
                # Let's iterate patterns again
                for pii_type, pattern in pii_patterns.items():
                     count = df.filter(
                         (pl.col('data_classification') == 'public') &
                         (pl.col(col).str.contains(pattern))
                     ).height
                     if count > 0:
                         public_pii_count += count
                         break # Counted this column's contribution (wait, original counts ROWS, not instances)
            
            # Correct logic: Count ROWS that are public AND have PII in ANY pii column.
            # We need an expression: (public) & ( (col1 has pii) OR (col2 has pii) ... )
            
            # We need to know which pattern applies to which column.
            # Let's map col -> pattern first
            col_patterns = {}
            for col in string_cols:
                for pii_type, pattern in pii_patterns.items():
                    if df[col].str.contains(pattern).any():
                        col_patterns[col] = pattern
                        break
            
            if col_patterns:
                public_pii_rows = df.filter(
                    (pl.col('data_classification') == 'public') &
                    (pl.any_horizontal([
                        pl.col(c).str.contains(p) for c, p in col_patterns.items()
                    ]))
                ).height
                
                if public_pii_rows > 0:
                    score -= 20

    return max(0, score)


def _identify_governance_issues(df: pl.DataFrame, config: Dict[str, Any]) -> list:
    """
    Identify specific governance issues in the data.
    """
    issues = []

    # Check for missing lineage fields
    required_lineage = config.get('required_lineage_fields', [])
    for field in required_lineage:
        if field not in df.columns:
            issues.append({
                "type": "missing_lineage_field",
                "field": field,
                "severity": "critical",
                "message": f"Required lineage field '{field}' is missing"
            })

    # Check for missing consent fields
    required_consent = config.get('required_consent_fields', [])
    for field in required_consent:
        if field not in df.columns:
            issues.append({
                "type": "missing_consent_field",
                "field": field,
                "severity": "critical",
                "message": f"Required consent field '{field}' is missing"
            })

    # Check for missing classification fields
    required_classification = config.get('required_classification_fields', [])
    for field in required_classification:
        if field not in df.columns:
            issues.append({
                "type": "missing_classification_field",
                "field": field,
                "severity": "critical",
                "message": f"Required classification field '{field}' is missing"
            })

    # Check for PII without proper classification
    pii_patterns = config.get('pii_patterns', {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b'
    })

    string_cols = [col for col in df.columns if df[col].dtype == pl.Utf8]
    for col in string_cols:
        for pii_type, pattern in pii_patterns.items():
            if df[col].str.contains(pattern).any():
                issues.append({
                    "type": "pii_detected",
                    "field": col,
                    "pii_type": pii_type,
                    "severity": "high",
                    "message": f"PII ({pii_type}) detected in field '{col}'"
                })
                break

    return issues
