# Agent Parameters Reference

This document lists all configurable parameters for Agensium agents where the parameter is either required or exposed in the UI (`show: true`).

## Tool: Master My Data

### Agent: Stewardship Flagger

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `business_rules` | `array` | No | Custom business rules [{name, condition: {column, operator, value}, severity, action}] | `[{"name": "high_value_check", "condition": {"column": "amount", "operator": "gt", "value": 10000}, "severity": "high", "action": "Manual Review"}, {"name": "active_user_check", "condition": {"column": "status", "operator": "eq", "value": "Active"}, "severity": "medium", "action": "Verify Activity"}]` |
| `duplicate_key_columns` | `array` | No | Columns to use for duplicate detection | `["email", "phone", "tax_id"]` |
| `required_columns` | `array` | No | List of columns that must have values | `["customer_id", "email", "created_at"]` |
| `field_validation_rules` | `object` | No | Field-specific validation rules (column -> {pattern, min_length, allowed_values}) | `{"zip_code": {"pattern": "^\\d{5}(-\\d{4})?$"}, "country_code": {"min_length": 2, "allowed_values": ["US", "CA", "UK"]}}` |
| `outlier_thresholds` | `object` | No | Field-specific outlier thresholds (field_type or column -> {min, max}) | `{"transaction_amount": {"min": 0, "max": 10000}, "age": {"min": 0, "max": 120}}` |

### Agent: Survivorship Resolver

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `match_key_columns` | `array` | **Yes** | Columns to use for identifying related records | `["Email", "Phone"]` |
| `field_validation_rules` | `object` | No | Field-specific validation rules (column -> {pattern, min_length, allowed_values}) | `{"email": {"pattern": "^.+@.+$"}, "age": {"min": 18}}` |
| `source_priority` | `object` | No | Source -> priority mapping (lower = higher priority) | `{"CRM": 1, "ERP": 2, "Web": 3, "Legacy": 4}` |
| `survivorship_rules` | `object` | No | Column -> rule mapping (freshness, quality_score, completeness, source_priority, frequency, richness, validation, min, max, first, last) | `{"email": "most_recent", "phone": "most_frequent", "address": "source_priority", "name": "most_complete", "score": "max"}` |
| `source_column` | `string` | **Yes** | Column identifying the record source | `"SourceSystem"` |
| `timestamp_column` | `string` | No | Column for freshness-based resolution | `"updated_at"` |

### Agent: Golden Record Builder

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `match_key_columns` | `array` | **Yes** | Columns to use for identifying related records | `["Email", "Phone"]` |
| `fuzzy_config` | `object` | No | Configuration for fuzzy matching (columns -> {type, weight}) | `{"name": {"type": "name", "weight": 2.0}, "address": {"type": "address", "weight": 1.0}, "email": {"type": "email", "weight": 3.0}}` |
| `source_priority` | `object` | No | Source -> priority mapping for source_priority rule | `{"Salesforce": 1, "HubSpot": 2, "Manual": 3}` |
| `survivorship_rules` | `object` | No | Column -> rule mapping (most_complete, most_recent, source_priority, most_frequent, min, max, first, last) | `{"name": "most_complete", "updated_at": "most_recent", "status": "source_priority", "category": "most_frequent"}` |
| `source_column` | `string` | **Yes** | Column identifying the record source | `"SourceSystem"` |
| `timestamp_column` | `string` | No | Column for recency-based survivorship rules | `"updated_at"` |

### Agent: Contract Enforcer

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `contract` | `object` | **Yes** | Contract definition containing required_columns, optional_columns, column_types, column_mappings, value_constraints, uniqueness_constraints | `{"required_columns": ["id", "name", "email"], "optional_columns": ["phone", "address"], "column_types": {"id": "integer", "name": "string", "email": "string", "phone": "string"}, "value_constraints": {"email": {"pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"}}, "uniqueness_constraints": ["id", "email"]}` |

### Agent: Semantic Mapper

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `custom_column_mappings` | `object` | No | Custom column name mappings (raw_name -> standard_name) | `{"CustomerID": "customer_id", "SourceSystem": "source_system", "FirstName": "first_name", "LastName": "last_name", "Email": "email"}` |
| `custom_value_mappings` | `object` | No | Custom value mappings by column (column -> {raw_value -> standard_value}) | `{"Country": {"U.S.A": "USA", "United States": "USA", "England": "UK"}, "State": {"N.Y.": "NY", "Calif.": "CA"}}` |

### Agent: Key Identifier

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `reference_tables` | `object` | No | Dictionary of reference tables for FK detection (table_name -> {column: [values]}) | `{"customers": {"customer_id": ["C001", "C002", "C003"]}, "products": {"product_id": ["P001", "P002", "P003"]}, "regions": {"region_code": ["NA", "EMEA", "APAC"]}}` |

## Tool: Clean My Data

### Agent: Cleanse Previewer

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `preview_rules` | `array` | No | List of cleaning rules to preview. Each rule specifies: {type, target_columns, description, ...}. Supported types: drop_nulls, impute_nulls, remove_outliers, drop_duplicates, drop_columns, convert_types | `[{"type": "drop_nulls", "target_columns": ["email", "customer_id"], "description": "Drop rows with missing critical identifiers"}, {"type": "impute_nulls", "target_columns": ["age"], "strategy": "mean", "description": "Impute missing age with mean"}, {"type": "remove_outliers", "target_columns": ["salary"], "method": "iqr", "threshold": 1.5, "description": "Remove salary outliers using IQR"}]` |

### Agent: Duplicate Resolver

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `email_columns` | `array` | No | Column names containing email addresses (auto-detected if empty) | `["email", "work_email"]` |
| `key_columns` | `array` | No | Columns to use as deduplication key (all columns if empty) | `["first_name", "last_name", "dob"]` |
| `merge_strategy` | `string` | No | Strategy for handling duplicates | `"merge_smart"` |

### Agent: Field Standardization

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `preserve_columns` | `array` | No | Columns to exclude from standardization | `["id", "metadata"]` |
| `target_columns` | `array` | No | Specific columns to standardize (all columns if empty) | `["first_name", "last_name", "city"]` |
| `synonym_mappings` | `object` | No | Column-specific synonym mappings (column -> {synonym -> standard_value}). Example: {'address': {'St.': 'Street', 'Ave.': 'Avenue', 'Rd.': 'Road'}} | `{"country": {"USA": "United States", "US": "United States", "UK": "United Kingdom"}, "status": {"Y": "Active", "N": "Inactive", "1": "Active", "0": "Inactive"}}` |
| `unit_mappings` | `object` | No | Column-specific unit conversion mappings (column -> {unit_pattern -> {factor: number, target_unit: string}}). Example: {'height': {'ft': {'factor': 12, 'target_unit': 'inches'}}} | `{"weight": {"kg": {"factor": 2.20462, "target_unit": "lbs"}, "g": {"factor": 0.00220462, "target_unit": "lbs"}}, "distance": {"km": {"factor": 0.621371, "target_unit": "miles"}, "m": {"factor": 0.000621371, "target_unit": "miles"}}}` |
| `case_strategy` | `string` | No | Case normalization strategy to apply | `"lowercase"` |
| `target_date_format` | `string` | No | Target format for date standardization (e.g., %Y-%m-%d) | `"%Y-%m-%d"` |

### Agent: Quarantine Agent

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `required_fields` | `array` | No | List of required field names | `["customer_id", "email", "created_at"]` |
| `format_constraints` | `object` | No | Format constraints (column -> regex pattern) | `{"email": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", "phone": "^\\+?[1-9]\\d{1,14}$", "zip_code": "^\\d{5}(-\\d{4})?$"}` |
| `range_constraints` | `object` | No | Numeric range constraints (column -> {min, max}) | `{"age": {"min": 18, "max": 120}, "salary": {"min": 0, "max": 1000000}, "score": {"min": 0, "max": 100}}` |

### Agent: Outlier Remover

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `detection_method` | `string` | No | Outlier detection method | `"iqr"` |
| `removal_strategy` | `string` | No | Strategy for handling detected outliers | `"impute_median"` |

### Agent: Null Handler

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `global_strategy` | `string` | No | Global strategy for handling nulls | `"column_specific"` |

## Tool: Profile My Data

### Agent: Test Coverage Agent

| Parameter | Type | Required | Description | Perfect Example |
| :--- | :--- | :--- | :--- | :--- |
| `unique_columns` | `array` | No | List of columns that should have unique values | `["user_id", "email", "ssn", "order_id"]` |
| `format_tests` | `object` | No | Format constraints for columns (column -> pattern or {pattern, description}) | `{"email": {"pattern": "^[^@]+@[^@]+\\.[^@]+$", "description": "Valid email address"}, "sku": "^[A-Z]{3}-\\d{4}$", "phone": "^\\+?[1-9]\\d{1,14}$"}` |
| `range_tests` | `object` | No | Range constraints for numeric columns (column -> {min, max}) | `{"age": {"min": 0, "max": 120}, "rating": {"min": 1, "max": 5}, "percentage": {"min": 0, "max": 100}}` |

# UI Implementation Notes

This section outlines the UI components required for different parameter types.

## Type: Array | Items: Object
**Status:** `Yet to Decide`
**Comment:** Complex nested structures. Need to design a proper UI for these cases.
**Parameters:**
- `business_rules`
- `preview_rules`

## Type: Array | Items: String
**Status:** `Multi-Select Column Dropdown`
**Comment:** These parameters accept a list of columns. The UI should show all columns from the file for the user to select.
**Parameters:**
- `duplicate_key_columns`
- `email_columns`
- `key_columns`
- `match_key_columns`
- `preserve_columns`
- `required_columns`
- `required_fields`
- `target_columns`
- `unique_columns`

## Type: Object
**Status:** `Yet to Decide`
**Comment:** Complex mappings or configurations (dictionaries).
**Parameters:**
- `contract`
- `custom_column_mappings`
- `custom_value_mappings`
- `field_validation_rules`
- `format_constraints`
- `format_tests`
- `fuzzy_config`
- `outlier_thresholds`
- `range_constraints`
- `range_tests`
- `reference_tables`
- `source_priority`
- `survivorship_rules`
- `synonym_mappings`
- `unit_mappings`

## Type: String | Allowed Values
**Status:** `Dropdown`
**Comment:** Already showing dropdown for parameters with allowed values.
**Parameters:**
- `case_strategy`
- `detection_method`
- `global_strategy`
- `merge_strategy`
- `removal_strategy`

## Type: String | Column Reference
**Status:** `Single-Select Column Dropdown`
**Comment:** Parameter refers to a single column. Show columns which can be selected.
**Parameters:**
- `source_column`
- `timestamp_column`

## Type: String | Free Text
**Status:** `Text Input`
**Comment:** Standard text input.
**Parameters:**
- `target_date_format`
