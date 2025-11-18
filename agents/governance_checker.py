"""
Governance Checker Agent

Validates data governance compliance including lineage, consent, and classification.
Input: CSV/JSON/XLSX file (primary)
Output: Standardized governance validation results
"""

import pandas as pd
import numpy as np
import io
import time
import re
from typing import Dict, Any, Optional


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
                "agent_id": "governance-checker",
                "error": f"Unsupported file format: {filename}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.empty:
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

        # Build results
        governance_data = {
            "governance_scores": {
                "overall": round(overall_score, 1),
                "lineage": round(lineage_score, 1),
                "consent": round(consent_score, 1),
                "classification": round(classification_score, 1)
            },
            "compliance_status": compliance_status,
            "total_records": len(df),
            "fields_analyzed": list(df.columns),
            "governance_issues": governance_issues
        }
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        if compliance_status != "compliant":
            issues_found = len(governance_issues)
            
            alerts.append({
                "alert_id": "alert_governance_001",
                "severity": "critical" if compliance_status == "non_compliant" else "high",
                "category": "governance_compliance",
                "message": f"Governance compliance: {overall_score:.1f}/100 ({compliance_status.upper().replace('_', ' ')})",
                "affected_fields_count": issues_found,
                "recommendation": f"Address {issues_found} governance issue(s) to meet compliance requirements."
            })
        
        # Component-specific alerts
        if lineage_score < 80:
            alerts.append({
                "alert_id": "alert_governance_lineage",
                "severity": "high" if lineage_score < 60 else "medium",
                "category": "data_lineage",
                "message": f"Data lineage score: {lineage_score:.1f}/100",
                "affected_fields_count": len([i for i in governance_issues if i.get("type", "").startswith("missing_lineage")]),
                "recommendation": "Implement data lineage tracking to document data sources, transformations, and dependencies"
            })
        
        if consent_score < 80:
            alerts.append({
                "alert_id": "alert_governance_consent",
                "severity": "critical" if consent_score < 60 else "high",
                "category": "consent_management",
                "message": f"Consent management score: {consent_score:.1f}/100",
                "affected_fields_count": len([i for i in governance_issues if i.get("type", "").startswith("missing_consent")]),
                "recommendation": "Implement consent tracking and management to comply with privacy regulations (GDPR, CCPA)"
            })
        
        if classification_score < 80:
            alerts.append({
                "alert_id": "alert_governance_classification",
                "severity": "high" if classification_score < 60 else "medium",
                "category": "data_classification",
                "message": f"Data classification score: {classification_score:.1f}/100",
                "affected_fields_count": len([i for i in governance_issues if i.get("type", "").startswith("missing_classification")]),
                "recommendation": "Implement data classification to identify and protect sensitive information"
            })
        
        # PII detection alert
        pii_issues = [i for i in governance_issues if i.get("type") == "pii_detected"]
        if pii_issues:
            alerts.append({
                "alert_id": "alert_governance_pii",
                "severity": "critical",
                "category": "pii_without_classification",
                "message": f"{len(pii_issues)} field(s) with PII detected without proper classification",
                "affected_fields_count": len(pii_issues),
                "recommendation": "Classify and secure PII fields with appropriate access controls and encryption"
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Add governance issues
        for issue in governance_issues:
            issue_type = issue.get("type", "governance_issue")
            field = issue.get("field", "N/A")
            severity = issue.get("severity", "medium")
            message = issue.get("message", "Governance issue detected")
            
            issues.append({
                "issue_id": f"issue_governance_{issue_type}_{field}",
                "agent_id": "governance-checker",
                "field_name": field,
                "issue_type": issue_type,
                "severity": severity,
                "message": message
            })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        recommendations = []
        
        # Governance recommendations based on critical/high severity issues
        critical_issues = [i for i in governance_issues if i.get("severity") == "critical"][:3]
        for issue in critical_issues:
            field = issue.get("field", "N/A")
            issue_type = issue.get("type", "governance_issue")
            message = issue.get("message", "")
            
            recommendations.append({
                "recommendation_id": f"rec_governance_{issue_type}_{field}",
                "agent_id": "governance-checker",
                "field_name": field,
                "priority": "critical",
                "recommendation": f"Address governance issue: {message}",
                "timeline": "immediate"
            })
        
        high_issues = [i for i in governance_issues if i.get("severity") == "high"][:3]
        for issue in high_issues:
            field = issue.get("field", "N/A")
            issue_type = issue.get("type", "governance_issue")
            message = issue.get("message", "")
            
            recommendations.append({
                "recommendation_id": f"rec_governance_{issue_type}_{field}",
                "agent_id": "governance-checker",
                "field_name": field,
                "priority": "high",
                "recommendation": f"Address governance issue: {message}",
                "timeline": "1-2 weeks"
            })
        
        # Component-based recommendations
        if lineage_score < 80:
            missing_lineage_fields = [i.get("field") for i in governance_issues if i.get("type") == "missing_lineage_field"]
            if missing_lineage_fields:
                recommendations.append({
                    "recommendation_id": "rec_governance_lineage",
                    "agent_id": "governance-checker",
                    "field_name": ", ".join(missing_lineage_fields[:3]),
                    "priority": "high",
                    "recommendation": f"Implement data lineage tracking for {len(missing_lineage_fields)} field(s): document source systems, transformations, and data flow",
                    "timeline": "2-3 weeks"
                })
        
        if consent_score < 80:
            missing_consent_fields = [i.get("field") for i in governance_issues if i.get("type") == "missing_consent_field"]
            if missing_consent_fields:
                recommendations.append({
                    "recommendation_id": "rec_governance_consent",
                    "agent_id": "governance-checker",
                    "field_name": ", ".join(missing_consent_fields[:3]),
                    "priority": "critical",
                    "recommendation": f"Implement consent management for {len(missing_consent_fields)} field(s): track user consent, preferences, and withdrawal requests",
                    "timeline": "1-2 weeks"
                })
        
        if classification_score < 80:
            missing_classification_fields = [i.get("field") for i in governance_issues if i.get("type") == "missing_classification_field"]
            if missing_classification_fields:
                recommendations.append({
                    "recommendation_id": "rec_governance_classification",
                    "agent_id": "governance-checker",
                    "field_name": ", ".join(missing_classification_fields[:3]),
                    "priority": "high",
                    "recommendation": f"Implement data classification for {len(missing_classification_fields)} field(s): categorize as public, internal, confidential, or restricted",
                    "timeline": "1-2 weeks"
                })
        
        # PII-specific recommendation
        if pii_issues:
            pii_fields = [i.get("field") for i in pii_issues]
            recommendations.append({
                "recommendation_id": "rec_governance_pii_protection",
                "agent_id": "governance-checker",
                "field_name": ", ".join(pii_fields[:3]),
                "priority": "critical",
                "recommendation": f"Protect {len(pii_fields)} PII field(s): implement encryption, access controls, audit logging, and data masking",
                "timeline": "immediate"
            })
        
        # Overall governance recommendation
        if compliance_status == "non_compliant":
            recommendations.append({
                "recommendation_id": "rec_governance_overall",
                "agent_id": "governance-checker",
                "field_name": "entire dataset",
                "priority": "critical",
                "recommendation": f"Governance compliance is non-compliant ({overall_score:.1f}/100). Implement comprehensive data governance framework with policies, procedures, and controls",
                "timeline": "4-6 weeks"
            })
        elif compliance_status == "needs_review":
            recommendations.append({
                "recommendation_id": "rec_governance_review",
                "agent_id": "governance-checker",
                "field_name": "entire dataset",
                "priority": "high",
                "recommendation": f"Governance compliance needs review ({overall_score:.1f}/100). Address identified gaps to meet regulatory requirements",
                "timeline": "2-4 weeks"
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
                "total_records": len(df),
                "total_fields": len(df.columns),
                "governance_score": round(overall_score, 1),
                "compliance_status": compliance_status,
                "issues_found": len(governance_issues)
            },
            "data": governance_data,
            "alerts": alerts,
            "issues": issues,
            "recommendations": recommendations,
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


def _validate_lineage(df: pd.DataFrame, config: Dict[str, Any]) -> float:
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
            null_pct = (df[field].isnull().sum() / len(df)) * 100
            if null_pct > 5:
                score -= min(15, null_pct / 10)

    return max(0, score)


def _validate_consent(df: pd.DataFrame, config: Dict[str, Any]) -> float:
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
        invalid_count = (~df['consent_status'].isin(valid_statuses + [None])).sum()
        if invalid_count > 0:
            score -= 15

    return max(0, score)


def _validate_classification(df: pd.DataFrame, config: Dict[str, Any]) -> float:
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
    for col in df.select_dtypes(include=['object']).columns:
        col_data = df[col].astype(str)
        for pii_type, pattern in pii_patterns.items():
            if col_data.str.contains(pattern, regex=True, na=False).any():
                pii_columns.append(col)
                break

    # If PII found, check if classified appropriately
    if pii_columns and 'data_classification' in df.columns:
        public_pii = ((df['data_classification'] == 'public') & df.index.isin(
            [idx for col in pii_columns for idx in df.index if df.loc[idx, col]]
        )).sum()
        if public_pii > 0:
            score -= 20

    return max(0, score)


def _identify_governance_issues(df: pd.DataFrame, config: Dict[str, Any]) -> list:
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

    for col in df.select_dtypes(include=['object']).columns:
        col_data = df[col].astype(str)
        for pii_type, pattern in pii_patterns.items():
            if col_data.str.contains(pattern, regex=True, na=False).any():
                issues.append({
                    "type": "pii_detected",
                    "field": col,
                    "pii_type": pii_type,
                    "severity": "high",
                    "message": f"PII ({pii_type}) detected in field '{col}'"
                })
                break

    return issues
