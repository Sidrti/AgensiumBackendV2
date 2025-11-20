# Agent Reference

Agents are the atomic units of work in Agensium. They are grouped into Tools.

## Profile Agents

_Used in `profile-my-data`_

| Agent ID                | Description                                                             | Input              |
| :---------------------- | :---------------------------------------------------------------------- | :----------------- |
| **unified-profiler**    | Calculates statistics, quality scores, and distributions.               | Primary File       |
| **drift-detector**      | Detects statistical drift between a primary and baseline dataset.       | Primary + Baseline |
| **score-risk**          | Identifies PII, sensitive data, and calculates compliance risk scores.  | Primary File       |
| **readiness-rater**     | Evaluates if data is ready for production use based on quality metrics. | Primary File       |
| **governance-checker**  | Checks for compliance with governance rules (also used in Clean).       | Primary File       |
| **test-coverage-agent** | Assesses data against defined validation rules (also used in Clean).    | Primary File       |

## Clean Agents

_Used in `clean-my-data`_

| Agent ID                  | Description                                                                | Input                  |
| :------------------------ | :------------------------------------------------------------------------- | :--------------------- |
| **cleanse-previewer**     | Simulates cleaning operations to show "what-if" impact before execution.   | Primary File           |
| **quarantine-agent**      | Isolates invalid or bad records based on strict rules.                     | Primary File           |
| **null-handler**          | Detects and fills/removes missing values using various strategies.         | Primary File           |
| **outlier-remover**       | Identifies and handles statistical outliers.                               | Primary File           |
| **type-fixer**            | Detects and fixes data type inconsistencies (e.g., string numbers to int). | Primary File           |
| **duplicate-resolver**    | Identifies and merges or removes duplicate records.                        | Primary File           |
| **field-standardization** | Standardizes formats (case, whitespace, units) across fields.              | Primary File           |
| **cleanse-writeback**     | Finalizes the cleaning process and prepares the dataset for export.        | Primary File (Cleaned) |

## Common Agents

- **governance-checker**: Validates lineage, consent, and classification.
- **test-coverage-agent**: Validates uniqueness, range, and format constraints.
