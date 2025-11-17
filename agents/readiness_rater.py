"""
Readiness Rater Agent

Rates data readiness for analysis based on quality metrics and component scoring.
Input: CSV/JSON/XLSX file (primary)
Output: Uniform readiness rating structure matching API specification
"""

import pandas as pd
import io
import time
from typing import Dict, Any, Optional


def rate_readiness(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Rate data readiness based on quality metrics.
    
    Args:
        file_contents: File bytes
        filename: Original filename
        parameters: Agent parameters matching tool.json (ready_threshold, needs_review_threshold, component weights)
        
    Returns:
        Uniform output structure matching API_SPECIFICATION.js response format
    """
    
    start_time = time.time()
    parameters = parameters or {}
    
    # Get parameters with defaults (matching tool.json)
    ready_threshold = parameters.get("ready_threshold", 80)
    needs_review_threshold = parameters.get("needs_review_threshold", 50)
    completeness_weight = parameters.get("completeness_weight", 0.3)
    consistency_weight = parameters.get("consistency_weight", 0.3)
    schema_health_weight = parameters.get("schema_health_weight", 0.4)
    
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
        
        # Calculate completeness score
        total_cells = len(df) * len(df.columns)
        missing_cells = df.isna().sum().sum()
        completeness_score = ((total_cells - missing_cells) / total_cells * 100) if total_cells > 0 else 0
        
        # Calculate consistency score
        # Check for data type consistency within columns
        consistency_issues = 0
        for col in df.columns:
            col_data = df[col].dropna()
            if len(col_data) > 0:
                # Check if numeric column has non-numeric values (simple check)
                try:
                    pd.to_numeric(col_data)
                except:
                    # Mixed types in numeric-looking column
                    if any(c.isdigit() for c in str(col_data.iloc[0])):
                        consistency_issues += 1
        
        consistency_score = 100 - (consistency_issues / max(len(df.columns), 1) * 20)
        consistency_score = max(0, min(100, consistency_score))
        
        # Calculate schema health
        # Check for missing column names, unexpected nulls, etc.
        schema_health = 100
        
        # Count problematic columns
        null_columns = 0
        unnamed_columns = 0
        inconsistent_columns = 0
        
        for col in df.columns:
            # Deduct for columns with all nulls (completely unusable)
            if df[col].isna().all():
                null_columns += 1
                schema_health -= 15  # Significant deduction for unusable column
            
            # Deduct for unnamed/auto-generated columns
            if str(col).startswith('Unnamed'):
                unnamed_columns += 1
                schema_health -= 8  # Moderate deduction for unnamed columns
            
            # Check for inconsistent data types within column
            if df[col].dtype == 'object':
                non_null = df[col].dropna().astype(str)
                if len(non_null) > 0:
                    # Try to detect mixed types (e.g., some numeric-looking, some text)
                    numeric_like = non_null.str.match(r'^-?\d+\.?\d*$').sum()
                    if 0 < numeric_like < len(non_null) * 0.3:
                        inconsistent_columns += 1
                        schema_health -= 5  # Minor deduction for mixed types
        
        # Cap schema health at 0
        schema_health = max(0, min(100, schema_health))
        
        # Calculate weighted readiness score
        readiness_score = (completeness_score * completeness_weight + 
                          consistency_score * consistency_weight + 
                          schema_health * schema_health_weight)
        
        # Determine status
        if readiness_score >= ready_threshold:
            status = "ready"
            status_description = "Dataset is suitable for analytics and ML with minor improvements"
            recommendation = "Proceed with analysis - dataset meets quality standards"
        elif readiness_score >= needs_review_threshold:
            status = "needs_review"
            status_description = "Dataset requires review and potential improvements before use"
            recommendation = "Address identified issues before production use"
        else:
            status = "not_ready"
            status_description = "Dataset requires significant improvements before analysis"
            recommendation = "Use 'Clean My Data' tool to improve data quality"
        
        # Find issues (deductions)
        deductions = []
        
        # Check for missing values - calculate actual impact
        for col in df.columns:
            missing_pct = (df[col].isna().sum() / len(df) * 100) if len(df) > 0 else 0
            if missing_pct > 10:
                # Impact calculation: higher missing % = higher deduction
                deduction_amount = min(missing_pct / 5, 25)  # Max 25 point deduction
                
                deductions.append({
                    "deduction_reason": "missing_values",
                    "fields_affected": [col],
                    "deduction_amount": round(deduction_amount, 2),
                    "severity": "critical" if missing_pct > 80 else "high" if missing_pct > 50 else "medium" if missing_pct > 25 else "low",
                    "remediation": "Impute missing values using domain knowledge, statistical methods, or remove records"
                })
        
        # Check for format inconsistencies (e.g., date formats)
        date_patterns = ['date', 'time', 'created', 'updated', 'timestamp', 'datetime']
        for col in df.columns:
            col_lower = col.lower()
            if any(x in col_lower for x in date_patterns):
                try:
                    # Try to parse as datetime
                    pd.to_datetime(df[col].dropna())
                except:
                    # Failed to parse all values as datetime
                    unparseable_count = 0
                    for val in df[col].dropna():
                        try:
                            pd.to_datetime(val)
                        except:
                            unparseable_count += 1
                    
                    unparseable_pct = (unparseable_count / len(df[col].dropna()) * 100) if len(df[col].dropna()) > 0 else 0
                    
                    if unparseable_pct > 0:
                        deduction_amount = min(unparseable_pct / 10, 12)  # Max 12 point deduction
                        
                        deductions.append({
                            "deduction_reason": "format_inconsistency",
                            "fields_affected": [col],
                            "deduction_amount": round(deduction_amount, 2),
                            "severity": "high" if unparseable_pct > 25 else "medium" if unparseable_pct > 10 else "low",
                            "remediation": f"Standardize date/time format. {unparseable_pct:.1f}% of values have inconsistent format"
                        })
        
        # Check for outliers (data quality indicator)
        for col in df.columns:
            if df[col].dtype in ['int64', 'float64']:
                col_data = df[col].dropna()
                if len(col_data) > 0:
                    Q1 = col_data.quantile(0.25)
                    Q3 = col_data.quantile(0.75)
                    IQR = Q3 - Q1
                    
                    outliers = col_data[(col_data < (Q1 - 1.5 * IQR)) | (col_data > (Q3 + 1.5 * IQR))]
                    outlier_pct = (len(outliers) / len(col_data) * 100) if len(col_data) > 0 else 0
                    
                    if outlier_pct > 5:
                        deduction_amount = min(outlier_pct / 20, 8)  # Max 8 point deduction
                        
                        deductions.append({
                            "deduction_reason": "potential_outliers",
                            "fields_affected": [col],
                            "deduction_amount": round(deduction_amount, 2),
                            "severity": "medium" if outlier_pct > 15 else "low",
                            "remediation": f"Review {outlier_pct:.1f}% of values as potential outliers. Validate or clean as needed"
                        })
        
        # Check for duplicate rows
        duplicate_count = len(df[df.duplicated()])
        duplicate_pct = (duplicate_count / len(df) * 100) if len(df) > 0 else 0
        
        if duplicate_pct > 0:
            deduction_amount = min(duplicate_pct / 10, 15)  # Max 15 point deduction
            
            deductions.append({
                "deduction_reason": "duplicate_rows",
                "fields_affected": [],
                "deduction_amount": round(deduction_amount, 2),
                "severity": "high" if duplicate_pct > 10 else "medium" if duplicate_pct > 5 else "low",
                "remediation": f"{duplicate_count} duplicate rows ({duplicate_pct:.1f}%) detected. Remove or consolidate duplicates"
            })
        
        # Component scores
        component_scores = [
            {
                "component": "completeness",
                "weight": completeness_weight,
                "score": round(completeness_score, 2),
                "status": "excellent" if completeness_score >= 95 else "good" if completeness_score >= 80 else "fair" if completeness_score >= 60 else "poor",
                "description": "Data has very few missing values" if completeness_score >= 95 else "Data has acceptable missing values" if completeness_score >= 80 else "Data has significant missing values"
            },
            {
                "component": "consistency",
                "weight": consistency_weight,
                "score": round(consistency_score, 2),
                "status": "excellent" if consistency_score >= 95 else "good" if consistency_score >= 80 else "fair" if consistency_score >= 60 else "poor",
                "description": "Data types are consistent" if consistency_score >= 90 else "Some data type inconsistencies detected"
            },
            {
                "component": "schema_health",
                "weight": schema_health_weight,
                "score": round(schema_health, 2),
                "status": "excellent" if schema_health >= 95 else "good" if schema_health >= 80 else "fair" if schema_health >= 60 else "poor",
                "description": "Schema is well-defined" if schema_health >= 90 else "Schema has minor issues"
            }
        ]
        
        return {
            "status": "success",
            "agent_id": "readiness-rater",
            "agent_name": "ReadinessRater",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "readiness_score": round(readiness_score, 2),
                "readiness_status": status,
                "components_ready": len([c for c in component_scores if c["score"] >= 80]),
                "components_needs_review": len([c for c in component_scores if 60 <= c["score"] < 80]),
                "components_not_ready": len([c for c in component_scores if c["score"] < 60])
            },
            "data": {
                "readiness_assessment": {
                    "overall_score": round(readiness_score, 2),
                    "overall_status": status,
                    "status_description": status_description,
                    "recommendation": recommendation
                },
                "component_scores": component_scores,
                "deductions": deductions
            }
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }
