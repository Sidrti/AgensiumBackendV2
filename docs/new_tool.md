2. Tool: Master My Data :
   a. KeyIdentifier
   b. ContractEnforcer
   c. SemanticMapper
   d. LineageTracer
   e. GoldenRecordBuilder
   f. SurvivorshipResolver
   g. MasterWritebackAgent
   h. StewardshipFlagger

===================================================================================================================================

a. KeyIdentifier
The job of the KeyIdentifier agent is to analyze the structural properties of a dataset and propose a list of candidate primary keys or foreign keys.
It performs this crucial analytical step before other agents like EntityResolver and DedupAgent can run effectively.

Key Type
What the Agent Looks For (Heuristics)
Candidate Primary Key (PK)
A column with high uniqueness (e.g., 99%+ distinct values) and low null density (e.g., 0% nulls). It flags this as the best field to uniquely identify a record.
Candidate Foreign Key (FK)
A column that has high overlap in its value set with the primary key of another known table. This helps link disparate datasets (e.g., 'ProductID' in a Sales table).
Candidate Entity Key
A column that has moderate uniqueness but is vital for matching (e.g., 'EmailAddress'). This key is essential for the EntityResolver to find common ground between records.

In short, the KeyIdentifier uses statistical inference to solve the fundamental data problem of "How do I uniquely identify this record?

===================================================================================================================================

b. ContractEnforcer

Case
Condition
Enforcement Action
Missing Required Columns
The contract specifies ProductID is mandatory, but it is absent from the input dataset.
CRITICAL ALERT: Flag the manifest. Action: Stop the workflow or fail the job, as the downstream system cannot function.
Extra Unspecified Columns
The input dataset contains an unneeded column (Debug_Log) not listed in the contract.
ALERT/ACTION: Flag the manifest. Transformation: Automatically drop the extra column to prevent integration errors.
Incorrect Data Type
The contract requires OrderValue to be a Float, but the input is detected as Text (due to values like "$100.00").
WARNING/TRANSFORMATION: Flag the manifest. Action: Attempt to cast/align the column to the required Float type (Transformation).
Incorrect Column Naming
The contract requires customer_identifier, but the input has cust_id.
TRANSFORMATION: Automatically rename the column (cust_id → customer_identifier) based on mapping rules provided in the contract.
That is a crucial and practical question. The ContractEnforcer Agent is designed to act as a quality control gateway, ensuring that data is strictly compliant with external system requirements.
Based on the documentation available (particularly the "Shape" phase of the data lifecycle and the client's focus on structured integration), here are the comprehensive cases and conditions under which the ContractEnforcer agent operates.

The Job: Enforcing the External Data Contract

The ContractEnforcer agent belongs to the Shape phase (part of the "Cleanse My Data" toolset). Its sole job is to enforce a predefined contract—a strict set of rules that the data must meet to be accepted by a downstream system (like an API, a microservice, or a highly rigid financial model).
It takes two essential inputs: the dataset and the Contract Definition (a JSON/YAML file).

Key Cases and Conditions for Enforcement

The agent operates in two main enforcement categories: Structural (Schema) and Value (Content).

I. Structural (Schema) Contract Enforcement

This ensures the fundamental shape of the data matches the contract.
Case
Condition
Enforcement Action
Missing Required Columns
The contract specifies ProductID is mandatory, but it is absent from the input dataset.
CRITICAL ALERT: Flag the manifest. Action: Stop the workflow or fail the job, as the downstream system cannot function.
Extra Unspecified Columns
The input dataset contains an unneeded column (Debug_Log) not listed in the contract.
ALERT/ACTION: Flag the manifest. Transformation: Automatically drop the extra column to prevent integration errors.
Incorrect Data Type
The contract requires OrderValue to be a Float, but the input is detected as Text (due to values like "$100.00").
WARNING/TRANSFORMATION: Flag the manifest. Action: Attempt to cast/align the column to the required Float type (Transformation).
Incorrect Column Naming
The contract requires customer_identifier, but the input has cust_id.
TRANSFORMATION: Automatically rename the column (cust_id → customer_identifier) based on mapping rules provided in the contract.

II. Value (Content) Contract Enforcement
Case
Condition
Enforcement Action
Invalid Value Set
The contract requires the Status column to contain only values from ['Shipped', 'Pending'], but the input contains Complete or Done.
WARNING/TRANSFORMATION: Flag the manifest. Action: Replace the invalid value with a default (Unknown) or quarantine the record.
Out-of-Bounds Range
The contract specifies the Age field must be between 18 and 65, but the input contains a value of 150.
WARNING/TRANSFORMATION: Flag the manifest. Action: Cap the value (change 150 to 65) or nullify the record, depending on the severity.
Incorrect Format/Regex
The contract requires the ZipCode to match the pattern NNNNN-NNNN.
WARNING/TRANSFORMATION: Flag the manifest. Action: Automatically trim/format the value if possible, or mark the record as non-compliant.
Uniqueness Violation
The contract requires the TransactionID to be unique across all records processed.
CRITICAL ALERT: Flag the manifest. Action: The violating records must be dropped or sent to a Mastering Tool for merging.
That is a crucial and practical question. The ContractEnforcer Agent is designed to act as a quality control gateway, ensuring that data is strictly compliant with external system requirements.
Based on the documentation available (particularly the "Shape" phase of the data lifecycle and the client's focus on structured integration), here are the comprehensive cases and conditions under which the ContractEnforcer agent operates.

The Job: Enforcing the External Data Contract

The ContractEnforcer agent belongs to the Shape phase (part of the "Cleanse My Data" toolset). Its sole job is to enforce a predefined contract—a strict set of rules that the data must meet to be accepted by a downstream system (like an API, a microservice, or a highly rigid financial model).
It takes two essential inputs: the dataset and the Contract Definition (a JSON/YAML file).

Key Cases and Conditions for Enforcement

The agent operates in two main enforcement categories: Structural (Schema) and Value (Content).

I. Structural (Schema) Contract Enforcement

This ensures the fundamental shape of the data matches the contract.
Case
Condition
Enforcement Action
Missing Required Columns
The contract specifies ProductID is mandatory, but it is absent from the input dataset.
CRITICAL ALERT: Flag the manifest. Action: Stop the workflow or fail the job, as the downstream system cannot function.
Extra Unspecified Columns
The input dataset contains an unneeded column (Debug_Log) not listed in the contract.
ALERT/ACTION: Flag the manifest. Transformation: Automatically drop the extra column to prevent integration errors.
Incorrect Data Type
The contract requires OrderValue to be a Float, but the input is detected as Text (due to values like "$100.00").
WARNING/TRANSFORMATION: Flag the manifest. Action: Attempt to cast/align the column to the required Float type (Transformation).
Incorrect Column Naming
The contract requires customer_identifier, but the input has cust_id.
TRANSFORMATION: Automatically rename the column (cust_id → customer_identifier) based on mapping rules provided in the contract.

II. Value (Content) Contract Enforcement

This ensures the data within the columns adheres to business rules defined by the contract.
Case
Condition
Enforcement Action
Invalid Value Set
The contract requires the Status column to contain only values from ['Shipped', 'Pending'], but the input contains Complete or Done.
WARNING/TRANSFORMATION: Flag the manifest. Action: Replace the invalid value with a default (Unknown) or quarantine the record.
Out-of-Bounds Range
The contract specifies the Age field must be between 18 and 65, but the input contains a value of 150.
WARNING/TRANSFORMATION: Flag the manifest. Action: Cap the value (change 150 to 65) or nullify the record, depending on the severity.
Incorrect Format/Regex
The contract requires the ZipCode to match the pattern NNNNN-NNNN.
WARNING/TRANSFORMATION: Flag the manifest. Action: Automatically trim/format the value if possible, or mark the record as non-compliant.
Uniqueness Violation
The contract requires the TransactionID to be unique across all records processed.
CRITICAL ALERT: Flag the manifest. Action: The violating records must be dropped or sent to a Mastering Tool for merging.

Summary of Agent Function

The ContractEnforcer is essential for integration confidence. It runs the data through a legalistic filter to produce a transformed dataset that is guaranteed to match the downstream system's expectations. Its output manifest details every violation and every corrective action taken.

===================================================================================================================================

c. SemanticMapper

1. Purpose
   The SemanticMapper Agent is responsible for mapping input column names, keywords, and values to a standardized semantic schema.
   This ensures that data from different sources, with inconsistent column names or terminology, is unified into one consistent structure before cleaning, validation, enrichment, or analysis.

2.1. Standardize Column Names
Map raw/unstructured column names to a standardized schema.
Examples:
Raw NameMapped To

"fname", "first_name", "First Name"
"first_name"
"amount", "price", "total_cost"
"price"
"state", "province", "region"
"state"
2.2. Standardize Field Values
Normalize domain-specific values to consistent semantic labels.
Examples:
Country:
“USA”, “United States”, “U.S.” → “United States”
Gender:
“M”, “Male”, “male”, “m” → “Male”
Payment Status:
“completed”, “done”, “success” → “Completed”
2.3. Auto-Semantic Detection
If no mapping exists, the agent must:
Analyze patterns
Use semantic similarity (embedding model or keyword logic)
Recommend the best standard name/value
Add this to issue logs as “Unmapped Semantic Field”

===================================================================================================================================
d. LineageTracer

Lineage Array — Global Pipeline Execution Log
🎯 Purpose
The lineage array records each agent's execution step-by-step, creating a complete audit trail of:
What and which order the agents ran
In the current code, linage array is empty

===================================================================================================================================
e. GoldenRecordBuilder
Purpose
The GoldenRecordBuilder agent is responsible for creating the final unified, conflict-resolved, highest-quality version of a record—also known as the Golden Record.
It merges all incoming data representations (from multiple sources, systems, or formats) into one authoritative, cleansed, standardized, and trust-scored record.
This is the final step after mapping, standardizing, deduplicating, and tracing lineage.

Imagine the EntityResolver finds three different records for "Jane Doe," each with conflicting information:
Record 1: Name: Jane Doe, Phone: 555-1234, Address: 10 Elm St
Record 2: Name: J. Doe, Phone: (555) 123-4567, Address: NULL
Record 3: Name: Jane Doe, Phone: 555-1234, Tier: Gold
The GoldenRecordBuilder applies a set of Survivorship Rules to choose the best value for every single field:
Rule 1 (Completeness): Use the non-null value (choosing 10 Elm St over NULL).
Rule 2 (Recency): Use the newest value (e.g., the newest phone number).
Rule 3 (Source Priority): Use the value from the most trusted source (e.g., the Billing system always provides the authoritative Tier).
The output is the single, perfect, merged Golden Record:
Final Record: Name: Jane Doe, Phone: 555-1234, Address: 10 Elm St, Tier: Gold.

===================================================================================================================================
f. SurvivorshipResolver
Purpose
The SurvivorshipResolver determines which field values should “survive” when multiple sources provide different or conflicting values for the same entity.
It applies business rules, scoring logic, and priority models to pick the best possible value before the GoldenRecordBuilder constructs the final Golden Record.
This agent is the “brain” behind decision-making when merging records.

1. Compare Conflicting Field Values
   When multiple sources provide values for the same field (e.g., email, phone, name, date), the agent must:
   Identify conflicts
   Evaluate each value
   Choose which one “survives”
2. Apply Hierarchical Rule Engine
   a) Freshness / Timestamp
   Choose the value with the most recent:
   updatedAt
   lastModified
   ingestedAt
   b) Data Quality Scoring
   Score values based on:
   Completeness
   Valid format
   Validations (email regex, phone regex, date correctness)
   Confidence from SemanticMapper or FieldStandardizer
   c) Value Length / Data Richness
   Examples:
   For address → longest valid address wins
   For name → most complete form wins
   For description fields → more detailed field survives
   d) Business Rules
   Custom rules like:
   Prefer verified emails over unverified
   Prefer phone numbers with country code
3. Support Field-Level Custom Rules
   Some fields must have unique logic:
   Email → regex validity
   Phone → E.164 format + country validation
   Date → standardizable → “YYYY-MM-DD”
   Gender → allowed values only
   Boolean → normalize to true/false
4. Pass Resolved Fields to GoldenRecordBuilder
   The final output is a standardized, conflict-resolved field set that the GoldenRecordBuilder will merge.

===================================================================================================================================
g. MasterWritebackAgent
Create a final output file after applying all the agents result

===================================================================================================================================
h. StewardshipFlagger
Purpose
The StewardshipFlagger agent is responsible for identifying data issues that require human review or intervention.
It automatically flags suspicious, incomplete, inconsistent, or low-confidence data so that Data Stewards can take action.
It is the “quality gatekeeper” of the entire data pipeline.
📌 Key Responsibilities

1. Detect Data Quality Issues
   The agent evaluates each record and identifies issues such as:
   Missing required fields
   Invalid formats (email, phone, date, numeric fields)
   Conflicting values that survivorship cannot confidently resolve
   Low-confidence fields (below a threshold like 0.70)
   Duplicate records that need manual merging
   Suspicious or improbable values
   Age > 120
   Negative price
   Phone number too short
   Email without domain
2. Assign Stewardship Flags
   Each issue must be tagged with a consistent category, e.g.:
   CategoryMeaning

MISSING_REQUIRED
Required field missing
INVALID_FORMAT
Field format failed validation
CONFLICT_UNRESOLVED
SurvivorshipResolver couldn’t find a confident winner
DUPLICATE_SUSPECTED
Possible duplicate record group detected
LOW_CONFIDENCE
Confidence score low
OUTLIER_VALUE
Value outside expected range
STANDARDIZATION_FAILED
FieldStandardizer couldn’t normalize value 3. Generate Stewardship Log Entry
The agent must produce a clear log object for each issue:

{
 "entityId": "12345",
 "field": "email",
 "issueType": "INVALID_FORMAT",
 "value": "john@@mail..com",
 "confidence": 0.20,
 "recommendedAction": "Manual correction required",
 "detectedAt": "2025-01-26T08:42:10Z"
} 4. Determine Required Human Action
Based on the issue, the agent suggests actions such as:
“Verify with customer”
“Correct email format”
“Manually choose between conflicting values”
“Merge duplicates”
“Fill missing required field” 6. Integrate With Other Agents
Validates standardized fields from FieldStandardizer
Uses confidence scores from SurvivorshipResolver
Reads lineage from LineageTracer for debugging
Flags issues before GoldenRecordBuilder finalizes the record
