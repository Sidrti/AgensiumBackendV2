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
            "data": governance_data
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
