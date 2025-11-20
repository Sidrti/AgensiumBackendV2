"""
Risk Scorer Agent

Identifies PII, calculates risk scores, and assesses compliance requirements.
Input: CSV file (primary)
Output: Uniform risk assessment structure matching API specification
"""

import polars as pl
import numpy as np
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
        # Read file - CSV only
        if not filename.endswith('.csv'):
            return {
                "status": "error",
                "error": f"Unsupported file format: {filename}. Only CSV files are supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }
        
        try:
            # Read CSV with Polars
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to parse CSV: {str(e)}",
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
        
        # Pre-compile regex patterns
        compiled_patterns = {k: re.compile(v) for k, v in PII_PATTERNS.items()}
        
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
            
            if pii_detection_enabled:
                # Sample data for PII detection
                non_null_data = col_data.drop_nulls()
                sample_size = min(len(non_null_data), pii_sample_size)
                
                if sample_size > 0:
                    # Take a sample and convert to python list of strings for regex matching
                    sample = non_null_data.sample(n=sample_size, with_replacement=False, seed=42).cast(pl.Utf8).to_list()
                    
                    for pii_type, pattern in compiled_patterns.items():
                        matches = sum(1 for x in sample if pattern.match(x))
                        match_percentage = (matches / len(sample) * 100)
                        
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
                        email_count = sum(1 for x in sample if '@' in x)
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
        
        # Generate ROW-LEVEL-ISSUES
        row_level_issues = []
        
        # Identify columns of interest
        high_risk_pii_columns = [f["field_name"] for f in field_risk_assessments if f.get("risk_level") == "high" and any(rf.get("pii_type") for rf in f.get("risk_factors", []))]
        compliance_columns = [f["field_name"] for f in field_risk_assessments if f.get("compliance_issues")]
        medium_high_risk_cols = [f["field_name"] for f in field_risk_assessments if f.get("risk_level") in ["high", "medium"]]
        
        relevant_cols = list(set(high_risk_pii_columns + compliance_columns + medium_high_risk_cols))
        
        if relevant_cols:
            # Add row index to track original indices
            df_with_idx = df.with_row_index("row_index")
            
            # Iterate over rows to find issues (limit to 1000 issues)
            for row in df_with_idx.select(["row_index"] + relevant_cols).iter_rows(named=True):
                if len(row_level_issues) >= 1000:
                    break
                
                row_idx = row["row_index"]
                
                # 1. High Risk PII Check
                has_pii = False
                pii_types_found = []
                
                for col in high_risk_pii_columns:
                    if row[col] is not None and row[col] != "":
                        has_pii = True
                        for field_assess in field_risk_assessments:
                            if field_assess["field_name"] == col:
                                for risk_factor in field_assess.get("risk_factors", []):
                                    if risk_factor.get("pii_type"):
                                        pii_types_found.append(risk_factor.get("pii_type"))
                                break
                
                if has_pii:
                    severity = "critical"
                    if "ssn" in pii_types_found or "credit_card" in pii_types_found:
                        severity = "critical"
                    elif "email" in pii_types_found or "phone" in pii_types_found:
                        severity = "warning"
                    else:
                        severity = "info"
                    
                    row_level_issues.append({
                        "row_index": int(row_idx),
                        "column": ", ".join(high_risk_pii_columns),
                        "issue_type": "risk_high",
                        "severity": severity,
                        "message": f"Row contains {', '.join(set(pii_types_found))} data with high risk score",
                        "pii_types": list(set(pii_types_found))
                    })
                
                if len(row_level_issues) >= 1000: break
                
                # 2. Compliance Check
                if compliance_columns:
                    has_compliance_data = False
                    affected_frameworks = set()
                    
                    for col in compliance_columns:
                        if row[col] is not None and row[col] != "":
                            has_compliance_data = True
                            for field_assess in field_risk_assessments:
                                if field_assess["field_name"] == col:
                                    for issue in field_assess.get("compliance_issues", []):
                                        if "GDPR" in issue: affected_frameworks.add("GDPR")
                                        if "HIPAA" in issue: affected_frameworks.add("HIPAA")
                                        if "CCPA" in issue: affected_frameworks.add("CCPA")
                                    break
                    
                    if has_compliance_data and affected_frameworks:
                        severity = "critical" if any(f in ["GDPR", "HIPAA"] for f in affected_frameworks) else "warning"
                        
                        row_level_issues.append({
                            "row_index": int(row_idx),
                            "column": ", ".join(compliance_columns),
                            "issue_type": "compliance_violation",
                            "severity": severity,
                            "message": f"Row subject to {', '.join(affected_frameworks)} compliance requirements",
                            "frameworks": list(affected_frameworks)
                        })
                
                if len(row_level_issues) >= 1000: break
                
                # 3. Remediation Check
                if medium_high_risk_cols:
                    needs_remediation = False
                    risk_fields_affected = []
                    
                    for col in medium_high_risk_cols:
                        if row[col] is not None and row[col] != "":
                            needs_remediation = True
                            risk_fields_affected.append(col)
                    
                    if needs_remediation and risk_fields_affected:
                        # Check for duplicate row index in current issues list
                        is_duplicate = False
                        for issue in row_level_issues:
                            if issue["row_index"] == row_idx:
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            row_level_issues.append({
                                "row_index": int(row_idx),
                                "column": ", ".join(risk_fields_affected),
                                "issue_type": "remediation_needed",
                                "severity": "warning",
                                "message": f"Row contains {len(risk_fields_affected)} field(s) requiring security remediation",
                                "affected_fields": risk_fields_affected
                            })
        
        # Calculate issue summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {},
            "affected_rows": len(set(issue["row_index"] for issue in row_level_issues)),
            "affected_columns": sorted(list(set(col for issue in row_level_issues for col in issue.get("column", "").split(", "))))
        }
        
        # Aggregate by type
        for issue in row_level_issues:
            issue_type = issue.get("issue_type", "unknown")
            issue_summary["by_type"][issue_type] = issue_summary["by_type"].get(issue_type, 0) + 1
        
        # Aggregate by severity
        for issue in row_level_issues:
            severity = issue.get("severity", "info")
            issue_summary["by_severity"][severity] = issue_summary["by_severity"].get(severity, 0) + 1
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        sensitive_non_pii = sensitive_fields_detected - pii_fields_detected
        impacted_frameworks = risk_summary["compliance_frameworks_impacted"]
        
        # Overall risk alert - Primary
        if overall_risk_level == "high":
            alerts.append({
                "alert_id": "alert_risk_001_overall_critical",
                "severity": "critical",
                "category": "risk_compliance",
                "message": f"CRITICAL RISK: Overall risk score {overall_risk_score:.1f}/100 - Dataset contains high-risk data",
                "affected_fields_count": total_high_risk,
                "recommendation": f"IMMEDIATE ACTION: Secure {total_high_risk} high-risk field(s). Implement encryption, access controls, audit logging, and monitoring."
            })
        elif overall_risk_level == "medium":
            alerts.append({
                "alert_id": "alert_risk_002_overall_high",
                "severity": "high",
                "category": "risk_compliance",
                "message": f"MEDIUM RISK: Overall risk score {overall_risk_score:.1f}/100 - Dataset contains sensitive data",
                "affected_fields_count": total_high_risk + total_medium_risk,
                "recommendation": f"Address {total_high_risk + total_medium_risk} at-risk field(s). Review security controls and compliance requirements."
            })
        else:
            alerts.append({
                "alert_id": "alert_risk_003_overall_low",
                "severity": "low",
                "category": "risk_compliance",
                "message": f"LOW RISK: Overall risk score {overall_risk_score:.1f}/100 - Dataset risk is acceptable",
                "affected_fields_count": total_low_risk,
                "recommendation": "Continue monitoring data security and compliance posture regularly."
            })
        
        # PII detection alerts
        if pii_fields_detected > 0:
            alerts.append({
                "alert_id": "alert_pii_001_detected_critical",
                "severity": "critical",
                "category": "pii_detected",
                "message": f"PII DETECTED: {pii_fields_detected} field(s) contain personally identifiable information",
                "affected_fields_count": pii_fields_detected,
                "recommendation": "CRITICAL: Implement end-to-end encryption (AES-256), restrict access to PII, enable audit logging, establish retention policies, and enforce data minimization."
            })
        
        # High-risk field count alert
        if total_high_risk > 0:
            alerts.append({
                "alert_id": "alert_risk_high_volume",
                "severity": "critical" if total_high_risk > 5 else "high",
                "category": "high_risk_fields",
                "message": f"HIGH-RISK FIELDS: {total_high_risk} field(s) scored as high-risk (>={high_risk_threshold})",
                "affected_fields_count": total_high_risk,
                "recommendation": f"Implement security measures immediately for all {total_high_risk} high-risk field(s): encryption, role-based access, audit trails."
            })
        
        # Medium-risk fields alert
        if total_medium_risk > 0:
            alerts.append({
                "alert_id": "alert_risk_medium_volume",
                "severity": "high",
                "category": "medium_risk_fields",
                "message": f"MEDIUM-RISK FIELDS: {total_medium_risk} field(s) scored as medium-risk",
                "affected_fields_count": total_medium_risk,
                "recommendation": f"Review and improve security controls for {total_medium_risk} medium-risk field(s). Consider data masking or tokenization."
            })
        
        # Sensitive fields alert (separate from PII)
        if sensitive_non_pii > 0:
            alerts.append({
                "alert_id": "alert_sensitive_001_high",
                "severity": "high",
                "category": "sensitive_data",
                "message": f"SENSITIVE DATA: {sensitive_non_pii} field(s) detected as sensitive but not categorized as PII",
                "affected_fields_count": sensitive_non_pii,
                "recommendation": f"Implement controls for {sensitive_non_pii} sensitive field(s): access restrictions, monitoring, classification tagging."
            })
        
        # Governance gaps alert
        if governance_gaps > 0:
            alerts.append({
                "alert_id": "alert_governance_gaps_001",
                "severity": "high",
                "category": "governance_gaps",
                "message": f"GOVERNANCE GAPS: {governance_gaps} sensitive field(s) lack encryption or security controls",
                "affected_fields_count": governance_gaps,
                "recommendation": f"Address governance gaps: encrypt {governance_gaps} field(s), implement access controls, audit logging, and data retention policies."
            })
        
        # Compliance framework alerts - GDPR
        if "GDPR" in impacted_frameworks:
            gdpr_fields = len([f for f in field_risk_assessments if "GDPR" in str(f.get("compliance_issues", []))])
            alerts.append({
                "alert_id": "alert_compliance_gdpr_critical",
                "severity": "critical",
                "category": "compliance_gdpr",
                "message": f"GDPR COMPLIANCE: {gdpr_fields} field(s) contain personal data covered by GDPR",
                "affected_fields_count": gdpr_fields,
                "recommendation": "Implement GDPR compliance: explicit consent mechanisms, data subject rights (access, erasure, portability), DPA records, breach notification procedures (72 hours)."
            })
        
        # Compliance framework alerts - HIPAA
        if "HIPAA" in impacted_frameworks:
            hipaa_fields = len([f for f in field_risk_assessments if "HIPAA" in str(f.get("compliance_issues", []))])
            alerts.append({
                "alert_id": "alert_compliance_hipaa_critical",
                "severity": "critical",
                "category": "compliance_hipaa",
                "message": f"HIPAA COMPLIANCE REQUIRED: {hipaa_fields} field(s) contain protected health information (PHI)",
                "affected_fields_count": hipaa_fields,
                "recommendation": "IMMEDIATE: Implement end-to-end encryption, role-based access control, Business Associate Agreements (BAAs), audit controls, 6-year retention requirements."
            })
        
        # Compliance framework alerts - CCPA
        if "CCPA" in impacted_frameworks:
            ccpa_fields = len([f for f in field_risk_assessments if "CCPA" in str(f.get("compliance_issues", []))])
            alerts.append({
                "alert_id": "alert_compliance_ccpa_high",
                "severity": "high",
                "category": "compliance_ccpa",
                "message": f"CCPA COMPLIANCE: {ccpa_fields} field(s) contain consumer personal information",
                "affected_fields_count": ccpa_fields,
                "recommendation": "Implement CCPA compliance: consumer rights mechanisms (access, delete, opt-out), privacy notices, opt-out mechanisms, data inventory, verification procedures."
            })
        
        # Encryption not implemented alert
        unencrypted_pii = total_high_risk
        if unencrypted_pii > 0:
            alerts.append({
                "alert_id": "alert_encryption_missing",
                "severity": "critical",
                "category": "encryption_gap",
                "message": f"ENCRYPTION MISSING: {unencrypted_pii} high-risk field(s) may lack encryption",
                "affected_fields_count": unencrypted_pii,
                "recommendation": "Implement encryption immediately: AES-256 at rest, TLS 1.2+ in transit, key management system with HSM, field-level encryption for PII."
            })
        
        # Multiple compliance frameworks alert
        if len(impacted_frameworks) > 1:
            alerts.append({
                "alert_id": "alert_multiple_compliance_critical",
                "severity": "critical",
                "category": "multi_compliance",
                "message": f"MULTIPLE COMPLIANCE FRAMEWORKS TRIGGERED: {', '.join(impacted_frameworks)}",
                "affected_fields_count": len(field_risk_assessments),
                "recommendation": f"CRITICAL: Address compliance requirements for all {len(impacted_frameworks)} frameworks. This increases implementation complexity and audit requirements significantly."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        # Add field risk issues with comprehensive issue types
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
                    "severity": "critical" if risk_level == "high" else "high",
                    "message": f"{field_name} - Risk {risk_score}/100 ({risk_level.upper()})",
                    "remediation_time_hours": 4 if risk_level == "high" else 2
                })
                
                # Add comprehensive PII detection issues
                for risk_factor in risk_factors:
                    factor_type = risk_factor.get("factor", "unknown")
                    pii_type = risk_factor.get("pii_type")
                    confidence = risk_factor.get("confidence", 0)
                    
                    if factor_type == "pii_detected" and pii_type:
                        pii_type_display = pii_type.replace("_", " ").title()
                        issues.append({
                            "issue_id": f"issue_pii_{field_id}_{pii_type}",
                            "agent_id": "score-risk",
                            "field_name": field_name,
                            "issue_type": f"pii_{pii_type}",
                            "severity": "critical",
                            "message": f"PII detected: {pii_type_display} (confidence: {confidence:.0%})",
                            "pii_category": pii_type,
                            "confidence_score": confidence,
                            "remediation_time_hours": 8
                        })
                        
                        # Add specific PII subtype issues
                        if pii_type == "email":
                            issues.append({
                                "issue_id": f"issue_pii_email_{field_id}",
                                "agent_id": "score-risk",
                                "field_name": field_name,
                                "issue_type": "email_exposure",
                                "severity": "high",
                                "message": f"Email address exposure risk in {field_name}",
                                "remediation_time_hours": 6
                            })
                        elif pii_type == "phone":
                            issues.append({
                                "issue_id": f"issue_pii_phone_{field_id}",
                                "agent_id": "score-risk",
                                "field_name": field_name,
                                "issue_type": "phone_exposure",
                                "severity": "high",
                                "message": f"Phone number exposure risk in {field_name}",
                                "remediation_time_hours": 6
                            })
                        elif pii_type == "ssn":
                            issues.append({
                                "issue_id": f"issue_pii_ssn_{field_id}",
                                "agent_id": "score-risk",
                                "field_name": field_name,
                                "issue_type": "ssn_exposure",
                                "severity": "critical",
                                "message": f"Social Security Number exposure risk in {field_name}",
                                "remediation_time_hours": 12
                            })
                        elif pii_type == "credit_card":
                            issues.append({
                                "issue_id": f"issue_pii_credit_card_{field_id}",
                                "agent_id": "score-risk",
                                "field_name": field_name,
                                "issue_type": "credit_card_exposure",
                                "severity": "critical",
                                "message": f"Credit card number exposure risk in {field_name}",
                                "remediation_time_hours": 12
                            })
                        elif pii_type == "zipcode":
                            issues.append({
                                "issue_id": f"issue_pii_zipcode_{field_id}",
                                "agent_id": "score-risk",
                                "field_name": field_name,
                                "issue_type": "zipcode_exposure",
                                "severity": "medium",
                                "message": f"Zipcode exposure risk in {field_name}",
                                "remediation_time_hours": 4
                            })
                    
                    elif factor_type == "contains_personal_identifier":
                        issues.append({
                            "issue_id": f"issue_sensitive_{field_id}",
                            "agent_id": "score-risk",
                            "field_name": field_name,
                            "issue_type": "sensitive_personal_data",
                            "severity": "high",
                            "message": f"Contains personal identifier or sensitive information",
                            "remediation_time_hours": 6
                        })
                
                # Add governance and access control issues
                if "governance" in str(risk_factors).lower():
                    issues.append({
                        "issue_id": f"issue_governance_{field_id}",
                        "agent_id": "score-risk",
                        "field_name": field_name,
                        "issue_type": "governance_gap",
                        "severity": "high",
                        "message": f"Governance gap detected for {field_name}: No access control policy defined",
                        "remediation_time_hours": 8
                    })
                
                # Add data classification issues
                issues.append({
                    "issue_id": f"issue_classification_{field_id}",
                    "agent_id": "score-risk",
                    "field_name": field_name,
                    "issue_type": "data_classification",
                    "severity": "high",
                    "message": f"{field_name} requires explicit classification: Personal/Sensitive/Confidential",
                    "remediation_time_hours": 2
                })
                
                # Add compliance issues with detailed framework tracking
                compliance_issues = field.get("compliance_issues", [])
                for idx, compliance_issue in enumerate(compliance_issues):
                    framework = "GDPR"
                    if "HIPAA" in compliance_issue:
                        framework = "HIPAA"
                    elif "CCPA" in compliance_issue:
                        framework = "CCPA"
                    
                    issues.append({
                        "issue_id": f"issue_compliance_{field_id}_{idx}",
                        "agent_id": "score-risk",
                        "field_name": field_name,
                        "issue_type": "compliance_violation",
                        "severity": "critical" if framework in ["HIPAA", "GDPR"] else "high",
                        "message": f"{framework} violation: {compliance_issue}",
                        "framework": framework,
                        "remediation_time_hours": 12 if framework == "HIPAA" else 8
                    })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        recommendations = []
        
        # Critical priority: High-risk field encryption recommendations
        high_risk_fields = [f for f in field_risk_assessments if f.get("risk_level") == "high"][:3]
        for field in high_risk_fields:
            field_name = field.get("field_name")
            field_id = field.get("field_id")
            risk_factors = field.get("risk_factors", [])
            risk_score = field.get("risk_score", 0)
            
            # Determine specific recommendation based on risk factors
            pii_detected = any(rf.get("factor") == "pii_detected" for rf in risk_factors)
            
            if pii_detected:
                recommendation_text = f"CRITICAL: Encrypt {field_name} using AES-256 (NIST approved). Implement role-based access control (RBAC) with principle of least privilege, comprehensive audit logging, and data access monitoring"
            else:
                recommendation_text = f"CRITICAL: Implement multi-layered security for {field_name} - Risk score {risk_score}/100. Requires encryption, access controls, and audit trails"
            
            recommendations.append({
                "recommendation_id": f"rec_risk_{field_id}",
                "agent_id": "score-risk",
                "field_name": field_name,
                "priority": "critical",
                "recommendation": recommendation_text,
                "timeline": "immediate",
                "estimated_effort_hours": 8,
                "owner": "Data Security Team",
                "depends_on": []
            })
        
        # High priority: Medium-risk field data masking/tokenization
        medium_risk_fields = [f for f in field_risk_assessments if f.get("risk_level") == "medium"][:3]
        for idx, field in enumerate(medium_risk_fields):
            field_name = field.get("field_name")
            field_id = field.get("field_id")
            
            recommendations.append({
                "recommendation_id": f"rec_risk_medium_{field_id}",
                "agent_id": "score-risk",
                "field_name": field_name,
                "priority": "high",
                "recommendation": f"Implement data masking or tokenization for {field_name} - Medium risk level. Consider Format-Preserving Encryption (FPE) for operational requirements",
                "timeline": "1 week",
                "estimated_effort_hours": 4,
                "owner": "Data Engineering Team",
                "depends_on": ["rec_risk_*"] if idx == 0 else []
            })
        
        # Critical priority: PII protection strategy
        if pii_fields_detected > 0:
            pii_details = []
            for pii_type in ["email", "phone", "ssn", "credit_card", "zipcode"]:
                pii_type_display = pii_type.replace("_", " ").title()
                pii_details.append(f"{pii_type_display}: implement encryption and access logs")
            
            recommendations.append({
                "recommendation_id": "rec_pii_handling",
                "agent_id": "score-risk",
                "field_name": f"{pii_fields_detected} fields with PII",
                "priority": "critical",
                "recommendation": f"Implement comprehensive PII protection strategy for {pii_fields_detected} field(s): 1) Encryption (AES-256), 2) Anonymization/Pseudonymization for non-prod, 3) Tokenization for APIs, 4) Access controls with audit trails. Specific PII types: {'; '.join(pii_details[:3])}",
                "timeline": "immediate",
                "estimated_effort_hours": 16,
                "owner": "Privacy & Security Officer",
                "depends_on": []
            })
        
        # High priority: Governance and access control implementation
        if governance_gaps > 0:
            recommendations.append({
                "recommendation_id": "rec_governance_gaps",
                "agent_id": "score-risk",
                "field_name": f"{governance_gaps} fields without governance",
                "priority": "high",
                "recommendation": f"Address {governance_gaps} governance gap(s): 1) Implement data classification (Public/Internal/Confidential/Restricted), 2) Define data lineage tracking, 3) Establish role-based access policies, 4) Create data ownership assignments, 5) Implement data quality standards",
                "timeline": "1-2 weeks",
                "estimated_effort_hours": 12,
                "owner": "Data Governance Team",
                "depends_on": []
            })
        
        # Critical priority: GDPR compliance recommendation
        if "GDPR" in impacted_frameworks:
            recommendations.append({
                "recommendation_id": "rec_gdpr_compliance",
                "agent_id": "score-risk",
                "field_name": "all PII fields (GDPR scope)",
                "priority": "critical",
                "recommendation": "GDPR compliance: 1) Implement consent management system with explicit opt-in, 2) Enable data portability (export in standard formats), 3) Implement right to erasure (complete PII removal), 4) Establish breach notification procedures (72-hour notification), 5) Conduct Data Protection Impact Assessments (DPIA), 6) Update privacy policies and data processing agreements",
                "timeline": "immediate",
                "estimated_effort_hours": 24,
                "owner": "Legal & Compliance Team",
                "depends_on": ["rec_pii_handling"]
            })
        
        # Critical priority: HIPAA compliance recommendation
        if "HIPAA" in impacted_frameworks:
            recommendations.append({
                "recommendation_id": "rec_hipaa_compliance",
                "agent_id": "score-risk",
                "field_name": "all PHI fields (HIPAA scope)",
                "priority": "critical",
                "recommendation": "HIPAA compliance: 1) Implement end-to-end encryption (minimum AES-256), 2) Deploy granular access controls with role separation, 3) Maintain comprehensive audit trails (minimum 6 years), 4) Execute Business Associate Agreements (BAAs) with all vendors, 5) Implement HIPAA-compliant backup and disaster recovery, 6) Conduct Security Risk Analysis (SRA) annually",
                "timeline": "immediate",
                "estimated_effort_hours": 32,
                "owner": "HIPAA Compliance Officer",
                "depends_on": ["rec_pii_handling"]
            })
        
        # High priority: CCPA compliance recommendation
        if "CCPA" in impacted_frameworks:
            recommendations.append({
                "recommendation_id": "rec_ccpa_compliance",
                "agent_id": "score-risk",
                "field_name": "all personal information (CCPA scope)",
                "priority": "high",
                "recommendation": "CCPA compliance: 1) Implement consumer rights mechanisms (access, delete, do-not-sell), 2) Create opt-out mechanisms for data sales, 3) Update privacy notices with California-specific disclosures, 4) Maintain data inventory (sources, uses, retention), 5) Establish vendor management procedures, 6) Implement data minimization practices",
                "timeline": "2-3 weeks",
                "estimated_effort_hours": 20,
                "owner": "Privacy Counsel",
                "depends_on": []
            })
        
        # High priority: Audit logging and monitoring
        recommendations.append({
            "recommendation_id": "rec_audit_logging",
            "agent_id": "score-risk",
            "field_name": "all sensitive fields",
            "priority": "high",
            "recommendation": "Implement comprehensive audit logging for all sensitive fields: 1) Log all access events (user, timestamp, action), 2) Implement real-time alerting for suspicious access patterns, 3) Maintain audit logs for minimum 1 year (encrypted), 4) Setup SIEM (Security Information & Event Management) integration, 5) Regular audit log reviews and anomaly detection",
            "timeline": "1-2 weeks",
            "estimated_effort_hours": 10,
            "owner": "Security Operations Center",
            "depends_on": []
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
                "risk_summary": risk_summary,
                "row_level_issues": row_level_issues[:100],
                "issue_summary": issue_summary,
                "overrides": {
                    "pii_sample_size": pii_sample_size,
                    "high_risk_threshold": high_risk_threshold,
                    "medium_risk_threshold": medium_risk_threshold,
                    "pii_detection_enabled": pii_detection_enabled,
                    "sensitive_field_detection_enabled": sensitive_field_detection_enabled,
                    "governance_check_enabled": governance_check_enabled
                }
            },
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
