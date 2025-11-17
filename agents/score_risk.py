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
            }
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
