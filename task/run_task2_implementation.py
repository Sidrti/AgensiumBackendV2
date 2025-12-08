import base64
import json
import os
import sys
import polars as pl
from io import BytesIO

# Add project root to path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.key_identifier import execute_key_identifier
from agents.contract_enforcer import execute_contract_enforcer
from agents.semantic_mapper import execute_semantic_mapper
from agents.survivorship_resolver import execute_survivorship_resolver
from agents.golden_record_builder import execute_golden_record_builder
from agents.stewardship_flagger import execute_stewardship_flagger

def print_df_info(name, file_bytes):
    try:
        df = pl.read_csv(BytesIO(file_bytes))
        print(f"\n[{name}] Columns: {df.columns}")
        print(f"[{name}] Row Count: {len(df)}")
        # print(f"[{name}] Head:\n{df.head(2)}")
    except Exception as e:
        print(f"[{name}] Error reading CSV: {e}")

def run_pipeline():
    print("Starting Master My Data Pipeline Execution...")

    # 1. Create Test Data
    csv_content_with_extra = """CustomerID,FName,E-mail,Phone,Country,LastUpdated,ExtraCol
C001,John,john@example.com,555-0101,U.S.A,2023-01-01,IgnoreMe
C001,J.,john.doe@example.com,555-0101,USA,2023-01-02,IgnoreMe
C002,Jane,jane@promo.com,555-0102,Canada,2023-01-01,IgnoreMe
C003,Bob,bob@example.com,555-0103,UK,2023-01-01,IgnoreMe
C003,Robert,bob@example.com,555-0103,United Kingdom,2023-01-03,IgnoreMe
C004,Alice,alice@example.com,555-0104,Spain,2023-01-01,IgnoreMe
C005,Eve,eve@example.com,555-0105,China,2023-01-01,IgnoreMe
C006,Mallory,mallory@example.com,555-0106,UAE,2023-01-01,IgnoreMe
C007,Invalid,invalid@example.com,555-0107,Mars,2023-01-01,IgnoreMe
"""
    
    original_file_bytes = csv_content_with_extra.encode('utf-8')
    filename = "test_data.csv"
    
    print(f"Test Data Created ({len(original_file_bytes)} bytes)")
    print_df_info("Original", original_file_bytes)

    # ==================================================================================
    # 1. Key Identifier
    # ==================================================================================
    print("\n--- 1. Running Key Identifier ---")
    key_params = {} 
    key_result = execute_key_identifier(original_file_bytes, filename, key_params)
    
    if key_result['status'] != 'success':
        print(f"Key Identifier Failed: {key_result.get('error')}")
        return

    print(f"Identified Keys: {json.dumps(key_result['data']['candidate_primary_keys'][:1], indent=2)}")
    
    current_file_bytes = original_file_bytes

    # ==================================================================================
    # 2. Contract Enforcer
    # ==================================================================================
    print("\n--- 2. Running Contract Enforcer ---")
    # UPDATED: Added "U.S.A" and "United Kingdom" to allowed values to prevent them from being nulled
    # before Semantic Mapper can fix them. This ensures data isn't lost due to strictness.
    contract_params = {
        "contract": {
            "required_columns": ["CustomerID", "FirstName", "Email", "Phone", "Country"],
            "optional_columns": ["LastUpdated"],
            "column_mappings": {
                "FName": "FirstName",
                "E-mail": "Email"
            },
            "value_constraints": {
                "Country": {
                    "allowed_values": ["USA", "Canada", "UK", "Spain", "China", "UAE", "U.S.A", "United Kingdom"],
                    "default_value": None 
                }
            }
        },
        "drop_extra_columns": True,
        "rename_columns": True,
        "auto_transform": True 
    }
    
    contract_result = execute_contract_enforcer(current_file_bytes, filename, contract_params)
    
    if contract_result['status'] != 'success':
        print(f"Contract Enforcer Failed: {contract_result.get('error')}")
        return

    print(f"Transformations: {len(contract_result['data']['transformations'])}")
    
    current_file_bytes = base64.b64decode(contract_result['cleaned_file']['content'])
    print_df_info("After Contract Enforcer", current_file_bytes)

    # ==================================================================================
    # 3. Semantic Mapper
    # ==================================================================================
    print("\n--- 3. Running Semantic Mapper ---")
    # Check columns to see if we need to adjust mappings
    df_contract = pl.read_csv(BytesIO(current_file_bytes))
    cols = df_contract.columns
    
    semantic_params = {
        "custom_column_mappings": {}, 
        "custom_value_mappings": {}, # Rely on updated standard mappings
        "auto_detect_semantics": True
    }
    
    semantic_result = execute_semantic_mapper(current_file_bytes, filename, semantic_params)
    
    if semantic_result['status'] != 'success':
        print(f"Semantic Mapper Failed: {semantic_result.get('error')}")
        return

    print(f"Transformations: {len(semantic_result['data']['transformations'])}")
    
    current_file_bytes = base64.b64decode(semantic_result['cleaned_file']['content'])
    print_df_info("After Semantic Mapper", current_file_bytes)

    # ==================================================================================
    # 4. Survivorship Resolver
    # ==================================================================================
    print("\n--- 4. Running Survivorship Resolver ---")
    
    # Determine correct column names
    df_sem = pl.read_csv(BytesIO(current_file_bytes))
    cols = df_sem.columns
    id_col = "customer_id" if "customer_id" in cols else "CustomerID"
    phone_col = "phone" if "phone" in cols else "Phone"
    country_col = "country" if "country" in cols else "Country"
    email_col = "email" if "email" in cols else "Email"
    fname_col = "first_name" if "first_name" in cols else "FirstName"
    date_col = "last_updated" if "last_updated" in cols else "LastUpdated"

    survivorship_params = {
        "match_key_columns": [id_col],
        "survivorship_rules": {
            phone_col: "frequency",
            country_col: "most_frequent",
            email_col: "most_recent",
            fname_col: "most_complete"
        },
        "timestamp_column": date_col,
        "source_priority": {
            "CRM": 1, "ERP": 2
        }
    }
    
    survivorship_result = execute_survivorship_resolver(current_file_bytes, filename, survivorship_params)
    
    if survivorship_result['status'] != 'success':
        print(f"Survivorship Resolver Failed: {survivorship_result.get('error')}")
        return

    print(f"Conflicts Resolved: {survivorship_result['summary_metrics']['conflicts_resolved']}")
    
    current_file_bytes = base64.b64decode(survivorship_result['cleaned_file']['content'])
    print_df_info("After Survivorship", current_file_bytes)

    # ==================================================================================
    # 5. Golden Record Builder
    # ==================================================================================
    print("\n--- 5. Running Golden Record Builder ---")
    golden_params = {
        "match_key_columns": [id_col],
        "min_trust_score": 0.5,
        "survivorship_rules": survivorship_params["survivorship_rules"],
        "timestamp_column": date_col
    }
    
    golden_result = execute_golden_record_builder(current_file_bytes, filename, golden_params)
    
    if golden_result['status'] != 'success':
        print(f"Golden Record Builder Failed: {golden_result.get('error')}")
        return

    print(f"Golden Records Created: {golden_result['summary_metrics']['golden_records_created']}")
    print(f"Compression Ratio: {golden_result['summary_metrics']['compression_ratio']}")
    
    current_file_bytes = base64.b64decode(golden_result['cleaned_file']['content'])
    print_df_info("After Golden Record", current_file_bytes)

    # ==================================================================================
    # 6. Stewardship Flagger
    # ==================================================================================
    print("\n--- 6. Running Stewardship Flagger ---")
    stewardship_params = {
        "required_columns": [id_col, fname_col, email_col, country_col],
        "business_rules": [
            {
                "name": "Promo Email",
                "condition": {
                    "column": email_col,
                    "operator": "contains",
                    "value": "promo.com"
                },
                "severity": "medium",
                "action": "Review promo email"
            }
        ]
    }
    
    stewardship_result = execute_stewardship_flagger(current_file_bytes, filename, stewardship_params)
    
    if stewardship_result['status'] != 'success':
        print(f"Stewardship Flagger Failed: {stewardship_result.get('error')}")
        return

    print(f"Tasks Created: {stewardship_result['summary_metrics']['tasks_created']}")
    
    final_file_bytes = base64.b64decode(stewardship_result['cleaned_file']['content'])
    
    print("\n--- Final Output Preview ---")
    print(final_file_bytes.decode('utf-8'))

if __name__ == "__main__":
    run_pipeline()
