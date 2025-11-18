"""
Risk Scorer Agent

Identifies PII, calculates risk scores, and assesses compliance requirements.
Input: CSV/JSON/XLSX file (primary)
Output: Uniform risk assessment structure matching API specification
"""

import pandas as pd
import io
import time
import re
from typing import Dict, Any, Optional, List


# PII patterns
PII_PATTERNS = {
    "email_address": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    "phone_number": r'^[\d\s\-\(\)\+]{10,}$',
    "ssn": r'^\d{3}-\d{2}-\d{4}$',
    "credit_card": r'^\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}$',
    "zipcode": r'^\d{5}(-\d{4})?$'
}

PII_SENSITIVE_KEYWORDS = [
    'email', 'phone', 'ssn', 'social_security', 'credit_card', 'account_number',
    'password', 'api_key', 'token', 'secret', 'name', 'address', 'dob', 'date_of_birth'
]

COMPLIANCE_FRAMEWORKS = {
    "GDPR": {
        "pii_fields": ["email", "phone", "name", "address", "dob"],
        "requires_consent": True,
        "retention_period": "30 days"
    },
    "CCPA": {
        "pii_fields": ["email", "phone", "name", "address", "ssn"],
        "consumer_rights": ["access", "delete", "opt_out"],
        "retention_period": "12 months"
    },
    "HIPAA": {
        "pii_fields": ["email", "phone", "name", "ssn", "patient_id", "medical_record"],
        "encryption_required": True,
        "retention_period": "6 years"
    }
}


def score_risk(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Score risk based on PII detection, compliance requirements, and governance.
    
    Args:
        file_contents: File bytes
        filename: Original filename
        parameters: Agent parameters matching tool.json
        
    Returns:
        Uniform output structure matching API_SPECIFICATION.js response format
    """
    
    start_time = time.time()
    parameters = parameters or {}
    
    # Get parameters with defaults (matching tool.json)
    pii_sample_size = parameters.get("pii_sample_size", 100)
    high_risk_threshold = parameters.get("high_risk_threshold", 70)
    medium_risk_threshold = parameters.get("medium_risk_threshold", 40)
    pii_detection_enabled = parameters.get("pii_detection_enabled", True)
    sensitive_field_detection_enabled = parameters.get("sensitive_field_detection_enabled", True)
    governance_check_enabled = parameters.get("governance_check_enabled", True)
    
    try:
        # Read file
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_contents))
        elif filename.endswith('.json'):
            df = pd.read_json(io.BytesIO(file_contents))
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(file_contents))
        else:
            return {
                "status": "error",
                "error": f"Unsupported file format: {filename}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }
        
        # Analyze each field
        field_risk_assessments = []
        total_high_risk = 0
        total_medium_risk = 0
        total_low_risk = 0
        pii_fields_detected = 0
        sensitive_fields_detected = 0
        governance_gaps = 0
        
        for col in df.columns:
            col_data = df[col]
            field_risk_score = 0
            risk_factors = []
            compliance_issues = []
            
            # Check field name for sensitivity
            col_lower = col.lower()
            is_sensitive_field = False
            
            for keyword in PII_SENSITIVE_KEYWORDS:
                if keyword in col_lower:
                    is_sensitive_field = True
                    sensitive_fields_detected += 1
                    break
            
            # PII Detection
            detected_pii_type = None
            pii_confidence = 0
            
            if pii_detection_enabled and col_data.dtype == 'object':
                # Sample data for PII detection
                sample = col_data.dropna().astype(str).head(pii_sample_size)
                
                for pii_type, pattern in PII_PATTERNS.items():
                    matches = sample.str.match(pattern).sum()
                    match_percentage = (matches / len(sample) * 100) if len(sample) > 0 else 0
                    
                    if match_percentage > 50:
                        detected_pii_type = pii_type
                        pii_confidence = min(0.99, match_percentage / 100)
                        pii_fields_detected += 1
                        
                        risk_factors.append({
                            "factor": "pii_detected",
                            "confidence": round(pii_confidence, 2),
                            "pii_type": pii_type
                        })
                        
                        field_risk_score += 80
                        break
                
                # Check for email addresses even if pattern doesn't match
                if not detected_pii_type and col_lower in ['email', 'email_address']:
                    email_count = sample.str.contains('@').sum()
                    if email_count / len(sample) > 0.7:
                        detected_pii_type = "email_address"
                        pii_confidence = 0.85
                        pii_fields_detected += 1
                        
                        risk_factors.append({
                            "factor": "pii_detected",
                            "confidence": 0.85,
                            "pii_type": "email_address"
                        })
                        
                        field_risk_score += 75
            
            # Sensitive field detection
            if sensitive_field_detection_enabled and is_sensitive_field and not detected_pii_type:
                risk_factors.append({
                    "factor": "contains_personal_identifier",
                    "confidence": 0.75
                })
                field_risk_score += 60
            
            # Check for governance gaps
            if governance_check_enabled:
                if field_risk_score > 0 and col_lower not in ['encrypted_email', 'masked_phone']:
                    compliance_issues.append("Missing encryption for sensitive data")
                    governance_gaps += 1
            
            # Determine risk level and compliance issues
            risk_level = "low"
            if field_risk_score >= high_risk_threshold:
                risk_level = "high"
                total_high_risk += 1
            elif field_risk_score >= medium_risk_threshold:
                risk_level = "medium"
                total_medium_risk += 1
            else:
                total_low_risk += 1
            
            # Add compliance framework issues
            if detected_pii_type or is_sensitive_field:
                for framework, config in COMPLIANCE_FRAMEWORKS.items():
                    pii_keywords = config.get("pii_fields", [])
                    for keyword in pii_keywords:
                        if keyword in col_lower:
                            if framework == "GDPR":
                                compliance_issues.append(f"{framework}: Requires explicit consent for processing")
                            elif framework == "CCPA":
                                compliance_issues.append(f"{framework}: Considered personal information")
                            elif framework == "HIPAA":
                                if config.get("encryption_required"):
                                    compliance_issues.append(f"{framework}: Requires encryption")
                            break
            
            # Determine remediation priority and effort
            remediation_priority = "high" if risk_level == "high" else "medium" if risk_level == "medium" else "low"
            remediation_effort = "high" if detected_pii_type else "medium" if is_sensitive_field else "low"
            
            field_assessment = {
                "field_id": col,
                "field_name": col,
                "risk_score": min(100, field_risk_score),
                "risk_level": risk_level,
                "risk_factors": risk_factors if risk_factors else [
                    {
                        "factor": "no_risk_detected",
                        "confidence": 1.0
                    }
                ],
                "compliance_issues": compliance_issues,
                "remediation_priority": remediation_priority,
                "remediation_effort": remediation_effort
            }
            
            field_risk_assessments.append(field_assessment)
        
        # Calculate overall risk score
        if field_risk_assessments:
            overall_risk_score = sum(f["risk_score"] for f in field_risk_assessments) / len(field_risk_assessments)
        else:
            overall_risk_score = 0
        
        overall_risk_level = "high" if overall_risk_score >= high_risk_threshold else "medium" if overall_risk_score >= medium_risk_threshold else "low"
        
        # Create risk summary
        risk_summary = {
            "overall_risk_score": round(overall_risk_score, 2),
            "overall_risk_level": overall_risk_level,
            "critical_issues": 0,
            "high_priority_issues": total_high_risk,
            "compliance_frameworks_impacted": _get_impacted_frameworks(field_risk_assessments),
            "estimated_remediation_time_hours": _estimate_remediation_time(total_high_risk, total_medium_risk, governance_gaps)
        }
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # Overall risk alert
        if overall_risk_level in ["high", "medium"]:
            alerts.append({
                "alert_id": "alert_risk_001",
                "severity": "critical" if overall_risk_level == "high" else "high",
                "category": "risk_compliance",
                "message": f"Overall risk level: {overall_risk_level.upper()} ({overall_risk_score:.1f}/100)",
                "affected_fields_count": total_high_risk,
                "recommendation": f"Address {total_high_risk} high-risk field(s). Implement encryption, access controls, audit logging."
            })
        
        # PII detection alerts
        if pii_fields_detected > 0:
            alerts.append({
                "alert_id": "alert_pii_001",
                "severity": "critical",
                "category": "pii_detected",
                "message": f"{pii_fields_detected} PII field(s) detected",
                "affected_fields_count": pii_fields_detected,
                "recommendation": f"Implement encryption at rest/transit, restrict access, audit logging, data retention policies."
            })
        
        # Sensitive fields alert (separate from PII)
        sensitive_non_pii = sensitive_fields_detected - pii_fields_detected
        if sensitive_non_pii > 0:
            alerts.append({
                "alert_id": "alert_sensitive_001",
                "severity": "high",
                "category": "sensitive_data",
                "message": f"{sensitive_non_pii} sensitive field(s) detected",
                "affected_fields_count": sensitive_non_pii,
                "recommendation": f"Review and secure {sensitive_non_pii} sensitive field(s). Consider access controls and monitoring."
            })
        
        # Governance gaps alert
        if governance_gaps > 0:
            alerts.append({
                "alert_id": "alert_governance_gaps_001",
                "severity": "high",
                "category": "governance_gaps",
                "message": f"{governance_gaps} governance gap(s) detected",
                "affected_fields_count": governance_gaps,
                "recommendation": f"Address {governance_gaps} governance gap(s) to ensure compliance and data quality."
            })
        
        # Compliance framework alerts
        impacted_frameworks = risk_summary["compliance_frameworks_impacted"]
        if impacted_frameworks:
            for framework in impacted_frameworks:
                alerts.append({
                    "alert_id": f"alert_compliance_{framework.lower()}",
                    "severity": "critical" if framework == "HIPAA" else "high",
                    "category": "compliance",
                    "message": f"{framework} compliance requirements detected",
                    "affected_fields_count": len([f for f in field_risk_assessments if framework in str(f.get("compliance_issues", []))]),
                    "recommendation": f"Ensure {framework} compliance: encryption, access controls, consent management, audit trails"
                })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Add field risk issues
        for field in field_risk_assessments:
            if field.get("risk_level") in ["high", "medium"]:
                risk_score = field.get("risk_score", 0)
                field_name = field.get("field_name")
                field_id = field.get("field_id")
                risk_level = field.get("risk_level")
                risk_factors = field.get("risk_factors", [])
                
                # Primary risk issue
                issues.append({
                    "issue_id": f"issue_risk_{field_id}",
                    "agent_id": "score-risk",
                    "field_name": field_name,
                    "issue_type": "pii_or_sensitive_data",
                    "severity": "critical" if risk_level == "high" else "warning",
                    "message": f"{field_name} - Risk {risk_score}/100 ({risk_level.upper()})"
                })
                
                # Add specific risk factor issues
                for risk_factor in risk_factors:
                    factor_type = risk_factor.get("factor", "unknown")
                    pii_type = risk_factor.get("pii_type")
                    confidence = risk_factor.get("confidence", 0)
                    
                    if factor_type == "pii_detected" and pii_type:
                        issues.append({
                            "issue_id": f"issue_pii_{field_id}_{pii_type}",
                            "agent_id": "score-risk",
                            "field_name": field_name,
                            "issue_type": f"pii_{pii_type}",
                            "severity": "critical",
                            "message": f"PII detected: {pii_type.replace('_', ' ').title()} (confidence: {confidence:.0%})"
                        })
                    elif factor_type == "contains_personal_identifier":
                        issues.append({
                            "issue_id": f"issue_sensitive_{field_id}",
                            "agent_id": "score-risk",
                            "field_name": field_name,
                            "issue_type": "sensitive_personal_data",
                            "severity": "high",
                            "message": f"Contains personal identifier or sensitive information"
                        })
                
                # Add compliance issues
                compliance_issues = field.get("compliance_issues", [])
                for idx, compliance_issue in enumerate(compliance_issues):
                    issues.append({
                        "issue_id": f"issue_compliance_{field_id}_{idx}",
                        "agent_id": "score-risk",
                        "field_name": field_name,
                        "issue_type": "compliance_violation",
                        "severity": "critical" if "HIPAA" in compliance_issue else "high",
                        "message": compliance_issue
                    })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        recommendations = []
        
        # Risk recommendations for high-risk fields
        high_risk_fields = [f for f in field_risk_assessments if f.get("risk_level") == "high"][:3]
        for field in high_risk_fields:
            field_name = field.get("field_name")
            field_id = field.get("field_id")
            risk_factors = field.get("risk_factors", [])
            
            # Determine specific recommendation based on risk factors
            pii_detected = any(rf.get("factor") == "pii_detected" for rf in risk_factors)
            
            if pii_detected:
                recommendation_text = f"Implement security measures for {field_name}: encryption (AES-256), role-based access control, audit logging"
            else:
                recommendation_text = f"Implement security measures for {field_name} - High risk detected"
            
            recommendations.append({
                "recommendation_id": f"rec_risk_{field_id}",
                "agent_id": "score-risk",
                "field_name": field_name,
                "priority": "critical",
                "recommendation": recommendation_text,
                "timeline": "immediate"
            })
        
        # Medium risk fields
        medium_risk_fields = [f for f in field_risk_assessments if f.get("risk_level") == "medium"][:3]
        for field in medium_risk_fields:
            field_name = field.get("field_name")
            field_id = field.get("field_id")
            
            recommendations.append({
                "recommendation_id": f"rec_risk_medium_{field_id}",
                "agent_id": "score-risk",
                "field_name": field_name,
                "priority": "high",
                "recommendation": f"Review and secure {field_name} - Medium risk level. Consider data masking or tokenization",
                "timeline": "1 week"
            })
        
        # PII handling recommendation
        if pii_fields_detected > 0:
            recommendations.append({
                "recommendation_id": "rec_pii_handling",
                "agent_id": "score-risk",
                "field_name": f"{pii_fields_detected} fields",
                "priority": "critical",
                "recommendation": f"Implement PII protection strategy for {pii_fields_detected} field(s): anonymization, pseudonymization, or encryption",
                "timeline": "immediate"
            })
        
        # Governance gaps recommendation
        if governance_gaps > 0:
            recommendations.append({
                "recommendation_id": "rec_governance_gaps",
                "agent_id": "score-risk",
                "field_name": f"{governance_gaps} fields",
                "priority": "high",
                "recommendation": f"Address {governance_gaps} governance gap(s): implement data classification, lineage tracking, and access policies",
                "timeline": "1-2 weeks"
            })
        
        # Compliance framework recommendations
        for framework in impacted_frameworks:
            if framework == "GDPR":
                recommendations.append({
                    "recommendation_id": "rec_gdpr_compliance",
                    "agent_id": "score-risk",
                    "field_name": "all PII fields",
                    "priority": "critical",
                    "recommendation": "GDPR compliance: implement consent management, data portability, right to erasure, and breach notification procedures",
                    "timeline": "2-4 weeks"
                })
            elif framework == "HIPAA":
                recommendations.append({
                    "recommendation_id": "rec_hipaa_compliance",
                    "agent_id": "score-risk",
                    "field_name": "all PHI fields",
                    "priority": "critical",
                    "recommendation": "HIPAA compliance: implement end-to-end encryption, access controls, audit trails, and Business Associate Agreements (BAAs)",
                    "timeline": "immediate"
                })
            elif framework == "CCPA":
                recommendations.append({
                    "recommendation_id": "rec_ccpa_compliance",
                    "agent_id": "score-risk",
                    "field_name": "all personal information",
                    "priority": "high",
                    "recommendation": "CCPA compliance: implement consumer rights mechanisms (access, delete, opt-out), privacy notices, and data inventory",
                    "timeline": "2-3 weeks"
                })
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = []
        
        # Risk Level
        executive_summary.append({
            "summary_id": "exec_risk",
            "title": "Risk Level",
            "value": str(round(overall_risk_score, 1)),
            "status": "high" if overall_risk_score >= 70 else "medium" if overall_risk_score >= 40 else "low",
            "description": f"{overall_risk_score:.1f}/100 - {overall_risk_level.upper()}"
        })
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_text_parts = []
        ai_analysis_text_parts.append(f"RISK ASSESSMENT: Overall risk level is {overall_risk_level.upper()} ({overall_risk_score:.1f}/100)")
        ai_analysis_text_parts.append(f"- High-risk fields: {total_high_risk}")
        ai_analysis_text_parts.append(f"- Medium-risk fields: {total_medium_risk}")
        ai_analysis_text_parts.append(f"- PII fields detected: {pii_fields_detected}")
        
        if sensitive_fields_detected > 0:
            ai_analysis_text_parts.append(f"- Sensitive fields detected: {sensitive_fields_detected}")
        
        if governance_gaps > 0:
            ai_analysis_text_parts.append(f"- Governance gaps: {governance_gaps}")
        
        if impacted_frameworks:
            ai_analysis_text_parts.append(f"- Compliance frameworks impacted: {', '.join(impacted_frameworks)}")
        
        if overall_risk_level in ["high", "medium"]:
            ai_analysis_text_parts.append("- Immediate security measures required: encryption, access controls, audit logging")
        
        ai_analysis_text = "\n".join(ai_analysis_text_parts)
        
        return {
            "status": "success",
            "agent_id": "score-risk",
            "agent_name": "RiskScorer",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_fields_analyzed": len(df.columns),
                "fields_with_high_risk": total_high_risk,
                "fields_with_medium_risk": total_medium_risk,
                "fields_with_low_risk": total_low_risk,
                "pii_fields_detected": pii_fields_detected,
                "sensitive_fields_detected": sensitive_fields_detected,
                "governance_gaps": governance_gaps
            },
            "data": {
                "fields": field_risk_assessments,
                "risk_summary": risk_summary
            },
            "alerts": alerts,
            "issues": issues,
            "recommendations": recommendations,
            "executive_summary": executive_summary,
            "ai_analysis_text": ai_analysis_text
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _get_impacted_frameworks(field_assessments: List[Dict]) -> List[str]:
    """Determine which compliance frameworks are impacted"""
    frameworks = set()
    
    for field in field_assessments:
        if field.get("compliance_issues"):
            for issue in field.get("compliance_issues", []):
                if "GDPR" in issue:
                    frameworks.add("GDPR")
                elif "CCPA" in issue:
                    frameworks.add("CCPA")
                elif "HIPAA" in issue:
                    frameworks.add("HIPAA")
    
    return sorted(list(frameworks))


def _estimate_remediation_time(high_risk: int, medium_risk: int, governance_gaps: int) -> int:
    """Estimate remediation time in hours"""
    # Rough estimate: 2 hours per high risk field, 1 hour per medium risk, 0.5 hours per governance gap
    return high_risk * 2 + medium_risk * 1 + max(0, governance_gaps - (high_risk + medium_risk))
