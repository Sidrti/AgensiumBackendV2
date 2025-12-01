"""
Semantic Mapper Agent

Maps input column names, keywords, and values to a standardized semantic schema.
Ensures that data from different sources with inconsistent column names or terminology
is unified into one consistent structure.

Key Responsibilities:
1. Standardize Column Names - Map raw/unstructured column names to a standardized schema
2. Standardize Field Values - Normalize domain-specific values to consistent semantic labels
3. Auto-Semantic Detection - Analyze patterns and use semantic similarity for unmapped fields

Input: CSV file (primary)
Output: Semantic mapping results with column mappings, value mappings, and confidence scores
"""

import io
import re
import time
import base64
import polars as pl
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime


def execute_semantic_mapper(
    file_contents: bytes,
    filename: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Map columns and values to standardized semantic schema.

    Args:
        file_contents: File bytes (read as binary)
        filename: Original filename (used to detect format)
        parameters: Agent parameters including custom mappings and thresholds

    Returns:
        Standardized output dictionary with semantic mapping results
    """

    start_time = time.time()
    parameters = parameters or {}

    # Extract parameters with defaults
    custom_column_mappings = parameters.get("custom_column_mappings", {})  # raw_name -> standard_name
    custom_value_mappings = parameters.get("custom_value_mappings", {})  # column -> {raw_value -> standard_value}
    confidence_threshold = parameters.get("confidence_threshold", 0.7)
    auto_detect_semantics = parameters.get("auto_detect_semantics", True)
    apply_mappings = parameters.get("apply_mappings", True)
    
    # Scoring weights
    name_similarity_weight = parameters.get("name_similarity_weight", 0.4)
    pattern_match_weight = parameters.get("pattern_match_weight", 0.3)
    value_analysis_weight = parameters.get("value_analysis_weight", 0.3)
    excellent_threshold = parameters.get("excellent_threshold", 90)
    good_threshold = parameters.get("good_threshold", 75)

    try:
        # Read file - CSV only
        if not filename.endswith('.csv'):
            return {
                "status": "error",
                "agent_id": "semantic-mapper",
                "error": f"Unsupported file format: {filename}. Only CSV files are supported.",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        try:
            df = pl.read_csv(io.BytesIO(file_contents), ignore_errors=True, infer_schema_length=10000)
        except Exception as e:
            return {
                "status": "error",
                "agent_id": "semantic-mapper",
                "error": f"Failed to parse CSV: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate data
        if df.height == 0:
            return {
                "status": "error",
                "agent_id": "semantic-mapper",
                "agent_name": "Semantic Mapper",
                "error": "File is empty",
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }

        original_df = df.clone()
        total_rows = df.height
        total_columns = len(df.columns)
        
        # Initialize tracking
        column_mappings = []
        value_mappings = []
        unmapped_columns = []
        unmapped_values = []
        transformations = []
        row_level_issues = []
        
        # ==================== COLUMN NAME MAPPING ====================
        for col in df.columns:
            mapping_result = _map_column_name(
                col, 
                custom_column_mappings, 
                auto_detect_semantics,
                confidence_threshold
            )
            
            column_mappings.append(mapping_result)
            
            if mapping_result["status"] == "mapped":
                if apply_mappings and mapping_result["standard_name"] != col:
                    df = df.rename({col: mapping_result["standard_name"]})
                    transformations.append({
                        "transformation_id": f"transform_rename_{col}",
                        "type": "column_rename",
                        "original_column": col,
                        "new_column": mapping_result["standard_name"],
                        "confidence": mapping_result["confidence"],
                        "description": f"Renamed column '{col}' to '{mapping_result['standard_name']}'"
                    })
            elif mapping_result["status"] == "unmapped":
                unmapped_columns.append({
                    "column": col,
                    "suggestions": mapping_result.get("suggestions", []),
                    "reason": mapping_result.get("reason", "No matching semantic pattern found")
                })
                row_level_issues.append({
                    "row_index": -1,  # Column-level issue
                    "column": col,
                    "issue_type": "unmapped_semantic_field",
                    "severity": "warning",
                    "original_value": col,
                    "message": f"Column '{col}' could not be mapped to a standard semantic field"
                })
        
        # ==================== VALUE STANDARDIZATION ====================
        # Use mapped column names for value mapping
        current_columns = df.columns
        
        for col in current_columns:
            col_data = df[col]
            
            # Skip non-string columns for value mapping
            if col_data.dtype != pl.Utf8:
                continue
            
            value_mapping_result = _map_column_values(
                col,
                col_data,
                custom_value_mappings.get(col, {}),
                auto_detect_semantics,
                confidence_threshold
            )
            
            if value_mapping_result["mappings"]:
                value_mappings.append({
                    "column": col,
                    "mappings": value_mapping_result["mappings"],
                    "total_values_mapped": value_mapping_result["total_mapped"],
                    "total_values_unchanged": value_mapping_result["total_unchanged"]
                })
                
                if apply_mappings:
                    # Apply value transformations
                    mapping_dict = {m["original"]: m["standard"] for m in value_mapping_result["mappings"]}
                    df = df.with_columns(
                        pl.col(col).replace(mapping_dict).alias(col)
                    )
                    
                    for mapping in value_mapping_result["mappings"]:
                        transformations.append({
                            "transformation_id": f"transform_value_{col}_{mapping['original'][:20]}",
                            "type": "value_standardization",
                            "column": col,
                            "original_value": mapping["original"],
                            "new_value": mapping["standard"],
                            "confidence": mapping["confidence"],
                            "occurrences": mapping.get("occurrences", 0),
                            "description": f"Standardized '{mapping['original']}' to '{mapping['standard']}' in column '{col}'"
                        })
            
            # Track unmapped values
            if value_mapping_result["unmapped_values"]:
                unmapped_values.extend([{
                    "column": col,
                    "value": v["value"],
                    "occurrences": v["occurrences"],
                    "suggestions": v.get("suggestions", [])
                } for v in value_mapping_result["unmapped_values"][:10]])  # Limit to top 10
                
                for unmapped in value_mapping_result["unmapped_values"][:5]:
                    row_level_issues.append({
                        "row_index": -1,
                        "column": col,
                        "issue_type": "unmapped_value",
                        "severity": "info",
                        "original_value": unmapped["value"],
                        "message": f"Value '{unmapped['value']}' in column '{col}' has no standard mapping"
                    })
        
        # Cap row-level issues
        row_level_issues = row_level_issues[:1000]
        
        # ==================== CALCULATE SCORES ====================
        mapped_columns_count = len([m for m in column_mappings if m["status"] == "mapped"])
        high_confidence_mappings = len([m for m in column_mappings if m.get("confidence", 0) >= confidence_threshold])
        
        column_mapping_rate = (mapped_columns_count / total_columns * 100) if total_columns > 0 else 0
        avg_confidence = sum(m.get("confidence", 0) for m in column_mappings) / len(column_mappings) if column_mappings else 0
        
        overall_score = (column_mapping_rate * 0.5) + (avg_confidence * 100 * 0.5)
        
        if overall_score >= excellent_threshold:
            quality_status = "excellent"
        elif overall_score >= good_threshold:
            quality_status = "good"
        else:
            quality_status = "needs_improvement"
        
        # Calculate issue summary
        issue_summary = {
            "total_issues": len(row_level_issues),
            "by_type": {},
            "by_severity": {},
            "affected_rows": len(set(issue["row_index"] for issue in row_level_issues if issue["row_index"] >= 0)),
            "affected_columns": sorted(list(set(issue["column"] for issue in row_level_issues)))
        }
        
        for issue in row_level_issues:
            issue_type = issue.get("issue_type", "unknown")
            issue_summary["by_type"][issue_type] = issue_summary["by_type"].get(issue_type, 0) + 1
            severity = issue.get("severity", "info")
            issue_summary["by_severity"][severity] = issue_summary["by_severity"].get(severity, 0) + 1
        
        # Build semantic mapping data
        semantic_mapping_data = {
            "mapping_score": round(overall_score, 1),
            "quality_status": quality_status,
            "column_mappings": column_mappings,
            "value_mappings": value_mappings,
            "unmapped_columns": unmapped_columns,
            "unmapped_values": unmapped_values[:50],  # Limit
            "transformations": transformations,
            "statistics": {
                "total_columns": total_columns,
                "mapped_columns": mapped_columns_count,
                "unmapped_columns": len(unmapped_columns),
                "high_confidence_mappings": high_confidence_mappings,
                "average_confidence": round(avg_confidence, 3),
                "total_value_mappings": sum(len(vm["mappings"]) for vm in value_mappings),
                "total_transformations": len(transformations)
            },
            "summary": f"Semantic mapping completed. {mapped_columns_count}/{total_columns} columns mapped, "
                      f"{len(transformations)} transformations applied, "
                      f"average confidence: {avg_confidence:.2f}",
            "row_level_issues": row_level_issues[:100],
            "issue_summary": issue_summary,
            "overrides": {
                "confidence_threshold": confidence_threshold,
                "auto_detect_semantics": auto_detect_semantics,
                "apply_mappings": apply_mappings
            }
        }
        
        # ==================== GENERATE EXECUTIVE SUMMARY ====================
        executive_summary = [{
            "summary_id": "exec_semantic_mapper",
            "title": "Semantic Mapping Status",
            "value": f"{overall_score:.1f}",
            "status": "excellent" if quality_status == "excellent" else "good" if quality_status == "good" else "needs_improvement",
            "description": f"Mapped {mapped_columns_count}/{total_columns} columns, "
                          f"Avg Confidence: {avg_confidence:.2f}, "
                          f"Transformations: {len(transformations)}"
        }]
        
        # ==================== GENERATE AI ANALYSIS TEXT ====================
        ai_analysis_parts = []
        ai_analysis_parts.append(f"SEMANTIC MAPPER ANALYSIS:")
        ai_analysis_parts.append(f"- Mapping Score: {overall_score:.1f}/100 ({quality_status})")
        ai_analysis_parts.append(f"- Columns Mapped: {mapped_columns_count}/{total_columns} ({column_mapping_rate:.1f}%)")
        ai_analysis_parts.append(f"- Average Confidence: {avg_confidence:.2f}")
        ai_analysis_parts.append(f"- Transformations Applied: {len(transformations)}")
        
        if unmapped_columns:
            ai_analysis_parts.append(f"- Unmapped Columns: {len(unmapped_columns)}")
            ai_analysis_parts.append(f"  Examples: {', '.join([u['column'] for u in unmapped_columns[:3]])}")
        
        if value_mappings:
            total_value_maps = sum(len(vm["mappings"]) for vm in value_mappings)
            ai_analysis_parts.append(f"- Value Standardizations: {total_value_maps} across {len(value_mappings)} columns")
        
        ai_analysis_text = "\n".join(ai_analysis_parts)
        
        # ==================== GENERATE ALERTS ====================
        alerts = []
        
        # Alert: Unmapped columns
        if unmapped_columns:
            alerts.append({
                "alert_id": "alert_semantic_unmapped_columns",
                "severity": "medium" if len(unmapped_columns) <= 3 else "high",
                "category": "semantic_mapping",
                "message": f"{len(unmapped_columns)} column(s) could not be mapped to standard schema",
                "affected_fields_count": len(unmapped_columns),
                "recommendation": "Review unmapped columns and add custom mappings if needed."
            })
        
        # Alert: Low confidence mappings
        low_confidence = [m for m in column_mappings if 0 < m.get("confidence", 0) < confidence_threshold]
        if low_confidence:
            alerts.append({
                "alert_id": "alert_semantic_low_confidence",
                "severity": "medium",
                "category": "mapping_quality",
                "message": f"{len(low_confidence)} column mapping(s) have low confidence scores",
                "affected_fields_count": len(low_confidence),
                "recommendation": "Review low-confidence mappings and verify correctness."
            })
        
        # Alert: Many unmapped values
        if len(unmapped_values) > 20:
            alerts.append({
                "alert_id": "alert_semantic_unmapped_values",
                "severity": "medium",
                "category": "value_standardization",
                "message": f"{len(unmapped_values)} unique values could not be standardized",
                "affected_fields_count": len(set(v["column"] for v in unmapped_values)),
                "recommendation": "Add custom value mappings for frequently occurring non-standard values."
            })
        
        # Alert: Quality score
        if overall_score < good_threshold:
            alerts.append({
                "alert_id": "alert_semantic_quality",
                "severity": "high",
                "category": "overall_quality",
                "message": f"Semantic mapping quality score ({overall_score:.1f}%) is below threshold",
                "affected_fields_count": total_columns,
                "recommendation": "Review column names and provide custom mappings for better standardization."
            })
        
        # ==================== GENERATE ISSUES ====================
        issues = []
        
        for unmapped in unmapped_columns:
            issues.append({
                "issue_id": f"issue_unmapped_col_{unmapped['column']}",
                "agent_id": "semantic-mapper",
                "field_name": unmapped["column"],
                "issue_type": "unmapped_column",
                "severity": "warning",
                "message": f"Column '{unmapped['column']}' has no standard semantic mapping"
            })
        
        for mapping in column_mappings:
            if mapping.get("confidence", 0) > 0 and mapping.get("confidence", 0) < confidence_threshold:
                issues.append({
                    "issue_id": f"issue_low_conf_{mapping['original_name']}",
                    "agent_id": "semantic-mapper",
                    "field_name": mapping["original_name"],
                    "issue_type": "low_confidence_mapping",
                    "severity": "info",
                    "message": f"Mapping for '{mapping['original_name']}' has low confidence ({mapping['confidence']:.2f})"
                })
        
        # ==================== GENERATE RECOMMENDATIONS ====================
        agent_recommendations = []
        
        # Recommendation 1: Review unmapped columns
        if unmapped_columns:
            agent_recommendations.append({
                "recommendation_id": "rec_semantic_unmapped",
                "agent_id": "semantic-mapper",
                "field_name": ", ".join([u["column"] for u in unmapped_columns[:3]]),
                "priority": "high",
                "recommendation": f"Review {len(unmapped_columns)} unmapped column(s) and add custom mappings",
                "timeline": "1 week"
            })
        
        # Recommendation 2: Verify low-confidence mappings
        if low_confidence:
            agent_recommendations.append({
                "recommendation_id": "rec_semantic_verify",
                "agent_id": "semantic-mapper",
                "field_name": ", ".join([m["original_name"] for m in low_confidence[:3]]),
                "priority": "medium",
                "recommendation": f"Verify {len(low_confidence)} low-confidence mapping(s) for accuracy",
                "timeline": "1 week"
            })
        
        # Recommendation 3: Standardize values
        if unmapped_values:
            affected_cols = list(set(v["column"] for v in unmapped_values))
            agent_recommendations.append({
                "recommendation_id": "rec_semantic_values",
                "agent_id": "semantic-mapper",
                "field_name": ", ".join(affected_cols[:3]),
                "priority": "medium",
                "recommendation": f"Add value mappings for {len(unmapped_values)} non-standard values",
                "timeline": "2 weeks"
            })
        
        # Recommendation 4: Document schema
        agent_recommendations.append({
            "recommendation_id": "rec_semantic_documentation",
            "agent_id": "semantic-mapper",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Document standardized schema and share with data providers",
            "timeline": "3 weeks"
        })
        
        # Recommendation 5: Implement at source
        agent_recommendations.append({
            "recommendation_id": "rec_semantic_source",
            "agent_id": "semantic-mapper",
            "field_name": "all",
            "priority": "low",
            "recommendation": "Implement semantic standards at data source to reduce mapping needs",
            "timeline": "1 month"
        })

        # Generate cleaned file (CSV format)
        cleaned_file_bytes = _generate_cleaned_file(df, filename)
        cleaned_file_base64 = base64.b64encode(cleaned_file_bytes).decode('utf-8')

        return {
            "status": "success",
            "agent_id": "semantic-mapper",
            "agent_name": "Semantic Mapper",
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "summary_metrics": {
                "total_columns": total_columns,
                "mapped_columns": mapped_columns_count,
                "unmapped_columns": len(unmapped_columns),
                "high_confidence_mappings": high_confidence_mappings,
                "average_confidence": round(avg_confidence, 3),
                "total_value_mappings": sum(len(vm["mappings"]) for vm in value_mappings),
                "total_transformations": len(transformations),
                "total_issues": len(row_level_issues)
            },
            "data": semantic_mapping_data,
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
            "agent_id": "semantic-mapper",
            "agent_name": "Semantic Mapper",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


# ==================== SEMANTIC MAPPING DICTIONARIES ====================

# Standard column name mappings
STANDARD_COLUMN_MAPPINGS = {
    # Name fields
    "first_name": ["fname", "first name", "firstname", "f_name", "given_name", "givenname"],
    "last_name": ["lname", "last name", "lastname", "l_name", "surname", "family_name", "familyname"],
    "full_name": ["name", "fullname", "full name", "customer_name", "person_name"],
    "middle_name": ["mname", "middle name", "middlename", "m_name"],
    
    # Contact fields
    "email": ["email_address", "emailaddress", "e_mail", "mail", "email_id", "contact_email"],
    "phone": ["phone_number", "phonenumber", "telephone", "tel", "mobile", "cell", "contact_number", "phone_no"],
    "address": ["street_address", "streetaddress", "addr", "address_line_1", "address1", "street"],
    "city": ["town", "municipality", "locality"],
    "state": ["province", "region", "state_code", "state_province"],
    "country": ["nation", "country_code", "country_name"],
    "zip_code": ["zipcode", "postal_code", "postalcode", "zip", "postcode", "pin_code", "pincode"],
    
    # Financial fields
    "price": ["amount", "cost", "total_cost", "unit_price", "sale_price", "value"],
    "quantity": ["qty", "count", "units", "amount", "num_items"],
    "total": ["total_amount", "grand_total", "sum", "total_value"],
    "discount": ["discount_amount", "disc", "rebate"],
    "tax": ["tax_amount", "vat", "gst", "sales_tax"],
    
    # Date fields
    "date": ["dt", "datetime", "timestamp", "created_at", "updated_at"],
    "created_date": ["created_at", "creation_date", "date_created", "create_date"],
    "updated_date": ["updated_at", "modification_date", "date_updated", "update_date", "modified_at"],
    "birth_date": ["dob", "date_of_birth", "birthdate", "birthday"],
    
    # ID fields
    "id": ["identifier", "record_id", "row_id", "uid", "uuid"],
    "customer_id": ["cust_id", "customerid", "customer_no", "customer_number", "client_id"],
    "order_id": ["orderid", "order_no", "order_number", "order_ref"],
    "product_id": ["productid", "prod_id", "item_id", "sku", "product_code"],
    "employee_id": ["emp_id", "employeeid", "staff_id", "worker_id"],
    
    # Status fields
    "status": ["state", "condition", "status_code", "current_status"],
    "active": ["is_active", "enabled", "active_flag"],
    
    # Demographic fields
    "gender": ["sex", "gender_code"],
    "age": ["years_old", "customer_age"],
}

# Standard value mappings
STANDARD_VALUE_MAPPINGS = {
    "country": {
        "united states": ["usa", "u.s.", "u.s.a", "us", "america", "united states of america"],
        "united kingdom": ["uk", "u.k.", "britain", "great britain", "england"],
        "canada": ["ca", "can"],
        "australia": ["au", "aus"],
        "germany": ["de", "deutschland"],
        "france": ["fr"],
        "japan": ["jp", "jpn"],
        "china": ["cn", "chn"],
        "india": ["in", "ind"],
    },
    "gender": {
        "male": ["m", "man", "boy", "masculine"],
        "female": ["f", "woman", "girl", "feminine"],
        "other": ["o", "non-binary", "nb", "x"],
    },
    "status": {
        "active": ["a", "enabled", "on", "yes", "y", "1", "true"],
        "inactive": ["i", "disabled", "off", "no", "n", "0", "false"],
        "pending": ["p", "waiting", "hold", "on hold"],
        "completed": ["c", "done", "finished", "complete", "success"],
        "cancelled": ["x", "canceled", "void", "voided"],
    },
    "payment_status": {
        "paid": ["p", "completed", "done", "success", "settled"],
        "pending": ["waiting", "processing", "in progress"],
        "failed": ["f", "declined", "rejected", "error"],
        "refunded": ["r", "returned", "reversed"],
    },
    "boolean": {
        "true": ["yes", "y", "1", "on", "enabled", "active"],
        "false": ["no", "n", "0", "off", "disabled", "inactive"],
    }
}


def _map_column_name(
    column_name: str,
    custom_mappings: Dict[str, str],
    auto_detect: bool,
    confidence_threshold: float
) -> Dict[str, Any]:
    """Map a column name to its standard semantic name."""
    col_lower = column_name.lower().strip()
    col_normalized = re.sub(r'[^a-z0-9]', '_', col_lower).strip('_')
    
    result = {
        "original_name": column_name,
        "standard_name": column_name,
        "status": "unmapped",
        "confidence": 0.0,
        "mapping_source": None,
        "suggestions": []
    }
    
    # Check custom mappings first
    if column_name in custom_mappings:
        result["standard_name"] = custom_mappings[column_name]
        result["status"] = "mapped"
        result["confidence"] = 1.0
        result["mapping_source"] = "custom"
        return result
    
    if col_lower in custom_mappings:
        result["standard_name"] = custom_mappings[col_lower]
        result["status"] = "mapped"
        result["confidence"] = 1.0
        result["mapping_source"] = "custom"
        return result
    
    # Check standard mappings
    for standard_name, variants in STANDARD_COLUMN_MAPPINGS.items():
        # Exact match with standard name
        if col_lower == standard_name or col_normalized == standard_name.replace('_', ''):
            result["standard_name"] = standard_name
            result["status"] = "mapped"
            result["confidence"] = 1.0
            result["mapping_source"] = "standard"
            return result
        
        # Check variants
        for variant in variants:
            variant_normalized = re.sub(r'[^a-z0-9]', '', variant.lower())
            if col_lower == variant or col_normalized == variant_normalized:
                result["standard_name"] = standard_name
                result["status"] = "mapped"
                result["confidence"] = 0.95
                result["mapping_source"] = "standard_variant"
                return result
    
    # Auto-detect semantics using patterns
    if auto_detect:
        pattern_result = _detect_semantic_pattern(column_name, col_lower)
        if pattern_result["detected"]:
            result["standard_name"] = pattern_result["standard_name"]
            result["status"] = "mapped" if pattern_result["confidence"] >= confidence_threshold else "low_confidence"
            result["confidence"] = pattern_result["confidence"]
            result["mapping_source"] = "pattern_detection"
            return result
        
        # Add suggestions for unmapped columns
        result["suggestions"] = pattern_result.get("suggestions", [])
    
    return result


def _detect_semantic_pattern(column_name: str, col_lower: str) -> Dict[str, Any]:
    """Detect semantic patterns in column names."""
    result = {
        "detected": False,
        "standard_name": None,
        "confidence": 0.0,
        "suggestions": []
    }
    
    # Pattern-based detection
    patterns = [
        (r'.*email.*', 'email', 0.85),
        (r'.*phone.*|.*tel.*|.*mobile.*|.*cell.*', 'phone', 0.85),
        (r'.*name.*first.*|.*first.*name.*', 'first_name', 0.80),
        (r'.*name.*last.*|.*last.*name.*|.*surname.*', 'last_name', 0.80),
        (r'.*full.*name.*|^name$', 'full_name', 0.75),
        (r'.*address.*|.*addr.*|.*street.*', 'address', 0.80),
        (r'.*city.*|.*town.*', 'city', 0.85),
        (r'.*state.*|.*province.*', 'state', 0.85),
        (r'.*country.*|.*nation.*', 'country', 0.85),
        (r'.*zip.*|.*postal.*|.*postcode.*', 'zip_code', 0.85),
        (r'.*price.*|.*cost.*|.*amount.*', 'price', 0.75),
        (r'.*date.*|.*time.*', 'date', 0.70),
        (r'.*birth.*|.*dob.*', 'birth_date', 0.85),
        (r'.*creat.*', 'created_date', 0.75),
        (r'.*updat.*|.*modif.*', 'updated_date', 0.75),
        (r'.*status.*|.*state.*', 'status', 0.70),
        (r'.*gender.*|.*sex.*', 'gender', 0.85),
        (r'.*age.*', 'age', 0.80),
        (r'.*qty.*|.*quantity.*', 'quantity', 0.85),
        (r'.*id$|.*_id$|^id$', 'id', 0.70),
        (r'.*customer.*id.*|.*cust.*id.*', 'customer_id', 0.85),
        (r'.*order.*id.*|.*order.*no.*', 'order_id', 0.85),
        (r'.*product.*id.*|.*prod.*id.*|.*sku.*', 'product_id', 0.85),
    ]
    
    for pattern, standard_name, confidence in patterns:
        if re.match(pattern, col_lower):
            result["detected"] = True
            result["standard_name"] = standard_name
            result["confidence"] = confidence
            return result
    
    # Generate suggestions based on partial matches
    suggestions = []
    for standard_name in STANDARD_COLUMN_MAPPINGS.keys():
        # Simple substring matching for suggestions
        if any(word in col_lower for word in standard_name.split('_')):
            suggestions.append({
                "standard_name": standard_name,
                "reason": f"Partial match with '{standard_name}'"
            })
    
    result["suggestions"] = suggestions[:3]
    return result


def _map_column_values(
    column_name: str,
    col_data: pl.Series,
    custom_mappings: Dict[str, str],
    auto_detect: bool,
    confidence_threshold: float
) -> Dict[str, Any]:
    """Map values in a column to standardized values."""
    result = {
        "mappings": [],
        "unmapped_values": [],
        "total_mapped": 0,
        "total_unchanged": 0
    }
    
    # Get unique values and their counts
    value_counts = col_data.drop_nulls().value_counts(sort=True)
    if value_counts.height == 0:
        return result
    
    # Detect column type for value mapping
    col_lower = column_name.lower()
    applicable_mappings = {}
    
    # Find applicable standard value mappings based on column name
    for category, mappings in STANDARD_VALUE_MAPPINGS.items():
        if category in col_lower or any(cat_word in col_lower for cat_word in category.split('_')):
            applicable_mappings.update(mappings)
    
    # Apply custom mappings (highest priority)
    applicable_mappings.update({v: k for k, variants in custom_mappings.items() if isinstance(variants, list) for v in variants})
    applicable_mappings.update(custom_mappings)
    
    # Process each unique value
    for row in value_counts.iter_rows(named=True):
        original_value = row[column_name]
        count = row["count"]
        
        if original_value is None:
            continue
        
        value_lower = str(original_value).lower().strip()
        mapped = False
        
        # Check direct custom mapping
        if original_value in custom_mappings:
            result["mappings"].append({
                "original": original_value,
                "standard": custom_mappings[original_value],
                "confidence": 1.0,
                "occurrences": count,
                "source": "custom"
            })
            result["total_mapped"] += count
            mapped = True
            continue
        
        # Check standard value mappings
        for standard_value, variants in applicable_mappings.items():
            if isinstance(variants, list):
                if value_lower in [v.lower() for v in variants]:
                    result["mappings"].append({
                        "original": original_value,
                        "standard": standard_value,
                        "confidence": 0.90,
                        "occurrences": count,
                        "source": "standard"
                    })
                    result["total_mapped"] += count
                    mapped = True
                    break
        
        if not mapped:
            # Check if value is already standard
            if value_lower in [k.lower() for k in applicable_mappings.keys()]:
                result["total_unchanged"] += count
            elif auto_detect:
                # Track unmapped values for potential review
                result["unmapped_values"].append({
                    "value": original_value,
                    "occurrences": count,
                    "suggestions": []
                })
                result["total_unchanged"] += count
            else:
                result["total_unchanged"] += count
    
    return result


def _generate_cleaned_file(df: pl.DataFrame, original_filename: str) -> bytes:
    """Generate cleaned data file in CSV format."""
    output = io.BytesIO()
    df.write_csv(output)
    return output.getvalue()
