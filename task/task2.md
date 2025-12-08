# Client Requirements Analysis & Implementation Plan (Task 2)

Based on the analysis of the client's requirements (`task.md`) and the existing agent implementations, the following plan outlines how the current system satisfies the requirements and what specific configurations or minor adjustments are needed.

## 1. Contract Enforcer

**Status:** ✅ Implemented
**Client Requirement:** Enforce required fields, drop extra columns, rename columns, cast types, enforce allowed values.

- **Code Analysis:** `backend/agents/contract_enforcer.py` supports all these features via the `contract` parameter.
- **Action Items:**
  - **Configuration:** Define the `contract` JSON to match client specifics:
    - Set `drop_extra_columns: true`.
    - Set `rename_columns: true`.
    - Define `allowed_values` for "Country" (USA, Canada, UK, Spain, China, UAE).
  - **Refinement:** The client requests invalid values be replaced with `null`. The current code defaults to `"Unknown"` if a default isn't provided.
    - _Adjustment:_ Ensure the `default_value` in the contract is set to `null` (or `None`) for these fields, or update the agent to default to `null` if `default_value` is missing.

## 2. Semantic Mapper

**Status:** ✅ Implemented
**Client Requirement:** Clean column names/values (e.g., "FName" -> "FirstName", "U.S.A" -> "USA").

- **Code Analysis:** `backend/agents/semantic_mapper.py` includes `STANDARD_COLUMN_MAPPINGS` and `STANDARD_VALUE_MAPPINGS`.
- **Action Items:**
  - **Configuration:**
    - Verify `STANDARD_COLUMN_MAPPINGS` includes "FName" -> "FirstName" (It currently maps "fname" -> "first_name", so we may need to adjust the standard target to match the client's preferred "FirstName" or use a custom mapping).
    - Verify `STANDARD_VALUE_MAPPINGS` includes "U.S.A" -> "USA" (It currently maps "u.s.a" -> "united states").
  - **Refinement:** The client specifically mentioned "FirstName" and "USA". The current agent standardizes to snake_case ("first_name") and full names ("united states").
    - _Adjustment:_ Use `custom_column_mappings` and `custom_value_mappings` parameters to override defaults to match the client's exact preference ("FirstName", "USA").

## 3. Survivorship Resolver

**Status:** ✅ Implemented
**Client Requirement:** Resolve duplicates using Freshness, Frequency, Completeness, Validation. Fallback to Source Priority.

- **Code Analysis:** `backend/agents/survivorship_resolver.py` implements these rules.
- **Action Items:**
  - **Configuration:**
    - Configure `survivorship_rules` for each field (e.g., `Phone: "frequency"`, `Address: "completeness"`).
    - Configure `source_priority` map: `{"CRM": 1, "ERP": 2, "WebPortal": 3, "Marketing": 4, "Support": 5}`.
  - **Refinement:** The client implies a "tie-breaker" chain (Rule -> Fallback). The current code applies one rule.
    - _Verification:_ Ensure the `source_priority` rule is used as the explicit fallback in the configuration if the primary rule (like freshness) fails (e.g., null timestamps).

## 4. Golden Record Builder

**Status:** ✅ Implemented
**Client Requirement:** Create golden record, trust scores, flag low confidence (<0.5).

- **Code Analysis:** `backend/agents/golden_record_builder.py` builds records and calculates `__trust_score__`.
- **Action Items:**
  - **Configuration:**
    - Set `min_trust_score: 0.5`.
    - Ensure `match_key_columns` are correctly identified (or auto-detected) to form clusters.

## 5. Stewardship Flagger

**Status:** ✅ Implemented
**Client Requirement:** Flag records for review (required fields, formats, outliers, duplicates, business rules).

- **Code Analysis:** `backend/agents/stewardship_flagger.py` generates tasks for `MISSING_REQUIRED`, `INVALID_FORMAT`, `OUTLIER_VALUE`, etc.
- **Action Items:**
  - **Configuration:**
    - Define `business_rules` for specific client cases (e.g., "promo.com emails flagged").
    - Example Rule: `{"name": "Promo Email", "condition": {"column": "email", "operator": "contains", "value": "promo.com"}, "severity": "medium", "action": "Review promo email"}`.

## 6. Transformers, Downloads & Tool Definition

**Status:** ✅ Implemented
**Client Requirement:** Produce a single trusted "golden record" per customer while flagging anything suspicious.

- **Tool Definition (`master_my_data_tool.json`):**
  - The agent sequence is defined as: `key-identifier` -> `contract-enforcer` -> `semantic-mapper` -> `survivorship-resolver` -> `golden-record-builder` -> `stewardship-flagger`.
  - _Analysis:_ This order is correct. `golden-record-builder` consolidates duplicates into a single record. `stewardship-flagger` then runs on this _consolidated_ record to flag any remaining issues.
- **Transformer (`master_my_data_transformer.py`):**
  - Logic: Selects the "most processed" file (highest `mastered_count`) as the final download.
  - _Analysis:_ Since the pipeline is linear, the final file output by `stewardship-flagger` will contain the cumulative results:
    - Standardized columns (from Semantic Mapper)
    - Golden Record metadata (`__trust_score__`, `__cluster_id__` from Golden Record Builder)
    - Stewardship flags (`__stewardship_issues__`, `__needs_review__` from Stewardship Flagger)
  - _Conclusion:_ No changes needed. The logic correctly identifies the final artifact.
- **Downloads (`master_my_data_downloads.py`):**
  - Logic: Generates "Master My Data - Final Mastered Data" CSV.
  - _Analysis:_ This file will be the CSV produced by the final agent. It will satisfy the requirement to show "Clean records", "Scores", and "Flags" in one file.

## Summary of Next Steps

To fully satisfy the client request with the existing tools:

1.  **Create a Configuration Profile:** We do not need to rewrite code. We need to construct the correct input `parameters` (Contract JSON, Mappings, Rules) that drive these agents.
2.  **Test Data Generation:** Create a `test_data.csv` that specifically contains the edge cases mentioned:
    - Columns: "FName", "E-mail"
    - Values: "U.S.A", "Calif.", "promo.com" email
    - Duplicates: Records with same CustomerID but different data.
3.  **Execution:** Run the `Master My Data` tool with this configuration.
4.  **Verification:** Check the final downloaded CSV to ensure it contains:
    - Standardized columns ("FirstName", "USA").
    - Golden Record columns (`__trust_score__`).
    - Stewardship columns (`__stewardship_issues__`).

This `task2.md` serves as the blueprint for configuring the existing powerful engine to meet the specific client needs.
