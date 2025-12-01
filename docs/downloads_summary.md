Understanding the 4 Output Files from Master My Data
Based on my analysis of all the agent code, here's what each output file is and how it differs from your input:

1. Semantic Mapper Output (semantic_mapped_sample.csv)
   Size: 10.08 KB | Agent: semantic-mapper

What it does:

Renames columns to standardized names (e.g., cust_nm → customer_name, phn → phone)
Standardizes values in columns (e.g., M/F/Male/Female → male/female, USA/US/United States → US)
Transformations applied:

Column names are mapped to a semantic schema based on pattern matching and similarity
Field values are normalized to consistent formats
Mappings are applied with confidence scores
Difference from Input:

Column headers may be renamed to standard names
Cell values in certain columns may be standardized
Same number of rows - no rows are added or removed
File size similar to input (minor changes due to value normalization) 2. Survivorship Resolver Output (resolved_semantic_mapped_sample.csv)
Size: 10.08 KB | Agent: survivorship-resolver

What it does:

Resolves conflicts when duplicate/related records have different values for the same field
Picks the "winning" value based on rules like freshness, quality score, completeness, or source priority
Transformations applied:

Groups records into clusters based on match keys (like email, phone, or ID)
For each conflict in a cluster, applies survivorship rules:
most_complete - picks the longest/most filled value
most_recent - picks based on timestamp
source_priority - picks from most trusted source
quality_score - picks based on data quality metrics
Each resolution gets a confidence score
Difference from Input:

Conflicting values are replaced with the "winner"
Adds resolution metadata (confidence scores, rule applied)
Same number of rows - just field values resolved
File size similar - same structure, different winning values 3. Golden Record Builder Output (golden_resolved_semantic_mapped_sample.csv)
Size: 11.77 KB | Agent: golden-record-builder

What it does:

Merges duplicate records into single "golden" records
Creates the authoritative, deduplicated version of your data
Transformations applied:

Clusters related records using match key columns (auto-detected or specified)
Merges all records in each cluster into ONE golden record
Applies survivorship rules to pick best value for each field
Assigns trust scores to each golden record
Creates **trust_score** column showing record confidence
Difference from Input:

FEWER ROWS - Multiple duplicate rows become one golden record
Each golden record represents merged data from potentially many source records
Compression ratio shown (e.g., 100 records → 50 golden records = 2x compression)
File size larger due to additional metadata columns (**trust_score**, **source_count**)
Contains the "best" value for each field after merging 4. Stewardship Flagger Output (flagged_golden_resolved_semantic_mapped_sample.csv)
Size: 151 Bytes | Agent: stewardship-flagger

What it does:

Extracts ONLY the problematic records that need human review
Identifies issues like missing required fields, invalid formats, low confidence, conflicts
Transformations applied:

Scans all rows for data quality issues:
MISSING_REQUIRED - Required field is null
INVALID_FORMAT - Email/phone/date format wrong
LOW_CONFIDENCE - Resolution confidence too low
CONFLICT_UNRESOLVED - No clear winner in survivorship
OUTLIER_VALUE - Value outside expected range
Filters to keep ONLY flagged rows
Adds **stewardship_issues** column (lists issues like INVALID_FORMAT:email; LOW_CONFIDENCE:phone)
Adds **flagged_at** timestamp
Difference from Input:

MUCH FEWER ROWS - Only records with issues are included
Very small file (151 bytes = likely 0-2 rows with issues)
Contains the original data PLUS issue summary columns
Purpose: Human Review Queue - These are records a Data Steward should manually fix
Visual Summary
Input File (sample.csv)
│
▼
┌─────────────────────────────────────────┐
│ SEMANTIC MAPPER │
│ • Standardize column names │
│ • Normalize field values │
│ • Same row count │
└────────────────────┬────────────────────┘
▼
semantic_mapped_sample.csv (10.08 KB)
│
▼
┌─────────────────────────────────────────┐
│ SURVIVORSHIP RESOLVER │
│ • Resolve conflicting values │
│ • Pick winning values per field │
│ • Same row count │
└────────────────────┬────────────────────┘
▼
resolved_semantic_mapped_sample.csv (10.08 KB)
│
▼
┌─────────────────────────────────────────┐
│ GOLDEN RECORD BUILDER │
│ • Merge duplicates into golden records │
│ • Add trust scores │
│ • REDUCED row count (deduplication) │
└────────────────────┬────────────────────┘
▼
golden_resolved_semantic_mapped_sample.csv (11.77 KB)
│
▼
┌─────────────────────────────────────────┐
│ STEWARDSHIP FLAGGER │
│ • Identify quality issues │
│ • Extract only flagged rows │
│ • Add issue summaries │
└────────────────────┬────────────────────┘
▼
flagged_golden_resolved_semantic_mapped_sample.csv (151 B)
(Only records needing human review)

Why the File Sizes?
File Size Reason
Semantic Mapper 10.08 KB Same as input (just renamed/normalized)
Survivorship Resolver 10.08 KB Same rows, just values resolved
Golden Record Builder 11.77 KB Fewer rows, but added metadata columns
Stewardship Flagger 151 Bytes Only 0-2 rows have issues (great data quality!)
The tiny Stewardship Flagger file means your data is very clean - almost no records need human intervention!

Based on my analysis of all 6 agents, here's the correct execution sequence:

Optimal Sequence for Master My Data

1. key-identifier → Identify keys for record matching
2. contract-enforcer → Enforce schema/contract compliance
3. semantic-mapper → Standardize column names & values
4. survivorship-resolver → Resolve conflicting values
5. golden-record-builder → Merge duplicates into golden records
6. stewardship-flagger → Flag issues for human review

Why This Order?
Order Agent Reason
1 key-identifier Must identify primary/entity keys FIRST - these keys are used by later agents to cluster and match records
2 contract-enforcer Enforce schema compliance BEFORE any transformations - ensures data structure is valid and columns are correctly typed
3 semantic-mapper Standardize names/values AFTER contract compliance - unified terminology needed before conflict resolution
4 survivorship-resolver Resolve conflicts BEFORE building golden records - determines which values should "win"
5 golden-record-builder Build golden records AFTER values are resolved - merges duplicates using already-resolved field values
6 stewardship-flagger Flag issues LAST - reviews the final golden records to identify what needs human attention
Your current [master_my_data_tool.json](c:\Users\VIVEK BANSAL\Desktop\Agensium\Agensium-V2\backend\tools\master_my_data_tool.json#L10-L17) already has the correct sequence:
