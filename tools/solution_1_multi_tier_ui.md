# Comprehensive Frontend Implementation Guide: Multi-Tier Parameter UI

## 1. Architecture Overview

This document provides a detailed implementation guide for the "Multi-Tier UI Approach" for Agensium V2. The goal is to abstract the complex JSON parameter structures defined in `temp copy.json` into user-friendly interfaces.

### 1.1. The Three Modes

The frontend must support switching between these modes for _every_ parameter configuration screen.

1.  **Beginner (Wizard/Guided)**:
    - **Focus**: Task-completion, education, simplicity.
    - **UI Pattern**: Steppers, natural language questions, limited options, smart defaults.
    - **State**: Manages a simplified local state that transforms to JSON on completion.
2.  **Intermediate (Form Builder)**:
    - **Focus**: Efficiency, visibility, standard configuration.
    - **UI Pattern**: Tables, lists, cards, modals, drag-and-drop.
    - **State**: Maps 1:1 with the JSON structure but uses UI controls (dropdowns, inputs) instead of text.
3.  **Advanced (JSON Editor)**:
    - **Focus**: Flexibility, bulk editing, debugging.
    - **UI Pattern**: Monaco Editor with schema validation.
    - **State**: Direct string manipulation of the JSON.

### 1.2. Component Strategy

Create a generic `ParameterConfigurator` component that takes `agentName`, `parameterName`, and `schema` as props.

```jsx
<ParameterConfigurator
  agent="Stewardship Flagger"
  parameter="business_rules"
  mode={userMode} // 'beginner' | 'intermediate' | 'advanced'
  data={currentJson}
  onChange={handleJsonChange}
/>
```

---

## 2. Shared UI Components Library

Before building agent-specific screens, implement these reusable "Smart Inputs" to handle common data types found in `temp copy.json`.

### 2.1. `ColumnSelector`

- **Usage**: Everywhere a column name is required.
- **Props**: `value`, `onChange`, `availableColumns` (from uploaded file).
- **Behavior**: Autocomplete dropdown.

### 2.2. `OperatorDropdown`

- **Usage**: Business rules, filters.
- **Options**: `eq` (=), `gt` (>), `lt` (<), `gte` (>=), `lte` (<=), `ne` (!=), `in`, `contains`.
- **Visual**: Show symbol and text (e.g., "> Greater Than").

### 2.3. `RangeSliderInput`

- **Usage**: `range_constraints`, `outlier_thresholds`.
- **Props**: `min`, `max`, `value` ({min, max}).
- **UI**: Dual-handle slider with manual number inputs on ends.

### 2.4. `MappingTable`

- **Usage**: `custom_column_mappings`, `synonym_mappings`.
- **UI**: Two columns. Left side fixed (or source selector), Right side input/selector. "Add Row" button.

### 2.5. `RegexBuilder`

- **Usage**: `format_constraints`, `field_validation_rules`.
- **UI**:
  - **Simple**: Dropdown of common patterns (Email, Phone, ZIP, SSN).
  - **Custom**: Text input for raw regex with a "Test" field to validate against sample text.

---

## 3. Agent-Specific Implementation Guide

This section analyzes every agent and parameter from `temp copy.json` and defines the specific UI requirements.

### 3.1. Agent: Stewardship Flagger

#### Parameter: `business_rules`

- **Type**: Array of Objects
- **Complexity**: High
- **JSON Structure**: `[{name, condition: {column, operator, value}, severity, action}]`

**Beginner Mode (Wizard):**

1.  **Step 1: Trigger**: "Which column do you want to monitor?" (ColumnSelector)
2.  **Step 2: Condition**: "When the value is..." (OperatorDropdown + Value Input)
3.  **Step 3: Consequence**: "What should happen?" (Severity Radio Group: High/Med/Low + Action Input)
4.  **Step 4: Name**: "Name this rule" (Auto-generate default, allow edit)

**Intermediate Mode (Rule Builder):**

- **List View**: Card list showing summary: `IF amount > 10000 THEN High Severity`.
- **Edit View**: A form with 4 distinct sections (Name, Condition, Severity, Action).
- **Validation**: Ensure `value` type matches `column` type (number vs string).

#### Parameter: `field_validation_rules`

- **Type**: Object
- **Structure**: `column -> {pattern, min_length, allowed_values}`

**Intermediate Mode:**

- **Layout**: Accordion list of columns.
- **Content**: Inside each column's accordion:
  - Checkbox: "Enforce Pattern" -> Shows `RegexBuilder`.
  - Checkbox: "Minimum Length" -> Shows Number Input.
  - Checkbox: "Restrict Values" -> Shows Tag/Chip Input for `allowed_values`.

#### Parameter: `outlier_thresholds`

- **Type**: Object
- **Structure**: `column -> {min, max}`

**Intermediate Mode:**

- **Layout**: Table. Rows = Numeric Columns.
- **Columns**: Column Name | Min Input | Max Input | Visual Range Bar.

---

### 3.2. Agent: Cleanse Previewer

#### Parameter: `preview_rules`

- **Type**: Array of Objects
- **Complexity**: Medium
- **JSON Structure**: `[{type, target_columns, description, ...args}]`

**Beginner Mode (Task Based):**

- **Prompt**: "What would you like to clean?"
- **Options (Cards)**: "Remove Nulls", "Fix Outliers", "Remove Duplicates".
- **Follow-up**: Based on selection, ask for `target_columns`.

**Intermediate Mode (Action List):**

- **UI**: A list of "Cleaning Steps".
- **Add Step**: Dropdown to select `type` (`drop_nulls`, `impute_nulls`, etc.).
- **Dynamic Form**:
  - If `impute_nulls`: Show `strategy` dropdown (mean, median, mode).
  - If `remove_outliers`: Show `method` (iqr, z-score) and `threshold`.

---

### 3.3. Agent: Contract Enforcer

#### Parameter: `contract`

- **Type**: Object (Complex Nested)
- **Complexity**: Very High
- **JSON Structure**: `{required_columns, optional_columns, column_types, value_constraints, uniqueness_constraints}`

**Intermediate Mode (Tabbed Interface):**

- **Tab 1: Structure**:
  - Two lists: "Required Columns" and "Optional Columns". Drag and drop columns from "Available" to these lists.
- **Tab 2: Data Types**:
  - Table: Column Name | Type Dropdown (String, Integer, Float, Boolean, Date).
- **Tab 3: Constraints**:
  - Table: Column Name | Unique (Checkbox) | Pattern (RegexBuilder).

**Beginner Mode**:

- Focus only on **Required Columns** and **Data Types**. Hide complex constraints.

---

### 3.4. Agent: Semantic Mapper

#### Parameter: `custom_column_mappings`

- **Type**: Object (Key-Value)
- **Structure**: `SourceColumn -> TargetColumn`

**Intermediate Mode (Mapper):**

- **UI**: Two-column layout.
- **Left**: Source Columns (Read-only or Dropdown from file).
- **Right**: Target Columns (Input for standard name).
- **Features**: "Auto-Map" button (using fuzzy logic), "Clear All".

#### Parameter: `custom_value_mappings`

- **Type**: Object (Nested Key-Value)
- **Structure**: `Column -> { RawValue -> StandardValue }`

**Intermediate Mode:**

- **Level 1**: Select Column (Dropdown).
- **Level 2**: Mapping Table for that column.
  - **Row**: Raw Value (Input) -> Standard Value (Input).
  - **Bulk Add**: Paste CSV text to generate rows.

---

### 3.5. Agent: Survivorship Resolver & Golden Record Builder

These agents share similar parameters.

#### Parameter: `source_priority`

- **Type**: Object
- **Structure**: `Source -> Priority (int)`

**Intermediate Mode (Sortable List):**

- **UI**: List of Sources (Salesforce, HubSpot, etc.).
- **Interaction**: Drag and drop to reorder.
- **Output Generation**: Top item = 1, Second = 2, etc.

#### Parameter: `survivorship_rules`

- **Type**: Object
- **Structure**: `Column -> Rule String`

**Intermediate Mode (Rules Table):**

- **Layout**: Table.
- **Rows**: All Columns.
- **Cell**: Rule Dropdown (`most_recent`, `most_complete`, `source_priority`, `most_frequent`, `max`, `min`).
- **Global Apply**: "Set all to..." dropdown at top.

#### Parameter: `fuzzy_config` (Golden Record Builder only)

- **Type**: Object
- **Structure**: `Column -> {type, weight}`

**Intermediate Mode:**

- **Layout**: Table.
- **Rows**: Columns used for matching.
- **Controls**:
  - **Match Type**: Dropdown (Exact, Fuzzy Name, Fuzzy Address).
  - **Importance**: Slider (1.0 to 5.0) for `weight`.

---

### 3.6. Agent: Quarantine Agent & Test Coverage Agent

#### Parameter: `range_constraints` / `range_tests`

- **Type**: Object
- **Structure**: `Column -> {min, max}`

**Intermediate Mode:**

- Same as `outlier_thresholds`. Table with Min/Max inputs.

#### Parameter: `format_constraints` / `format_tests`

- **Type**: Object
- **Structure**: `Column -> Regex` OR `Column -> {pattern, description}`

**Intermediate Mode:**

- **Layout**: Table.
- **Rows**: String Columns.
- **Cell**: Format Selector (Email, URL, UUID, Custom Regex).

---

### 3.7. Agent: Key Identifier

#### Parameter: `reference_tables`

- **Type**: Object
- **Structure**: `TableName -> { Column -> [Values] }`

**Intermediate Mode:**

- **UI**: Master-Detail.
- **Master**: List of Reference Tables (e.g., "Countries", "ProductCodes").
- **Detail**:
  - Select Key Column.
  - **Values Input**: Textarea (one per line) or CSV Upload button to populate the array.

---

### 3.8. Agent: Field Standardization

#### Parameter: `synonym_mappings`

- **Type**: Object (Nested)
- **Structure**: `Column -> { Synonym -> Standard }`

**Intermediate Mode:**

- Identical to `custom_value_mappings`.

#### Parameter: `unit_mappings`

- **Type**: Object (Nested)
- **Structure**: `Column -> { Unit -> { factor, target_unit } }`

**Intermediate Mode (Conversion Builder):**

- **Select Column**: e.g., "weight".
- **Target Unit**: Input e.g., "lbs".
- **Conversions List**:
  - Row: "If unit is [kg] multiply by [2.204]".
  - Row: "If unit is [g] multiply by [0.0022]".

---

## 4. Data Structure Transformation Logic

The frontend must robustly handle the transformation between UI state and JSON.

### 4.1. Parsing (JSON -> UI)

- **Validation**: When loading JSON into Intermediate/Beginner mode, validate it against the expected schema.
- **Fallback**: If the JSON structure is too complex or custom (e.g., uses advanced regex features not supported by the UI builder), force the user into **Advanced Mode** with a warning.
- **Defaults**: If JSON is empty, pre-fill UI with columns detected from the uploaded file.

### 4.2. Serialization (UI -> JSON)

- **Clean Up**: Remove empty rules or incomplete mappings before generating JSON.
- **Type Safety**: Ensure numbers are numbers, not strings (common JS issue).
- **Formatting**: Pretty-print the JSON output for the Advanced tab.

## 5. Implementation Roadmap

1.  **Phase 1: Core Components**: Build `ColumnSelector`, `OperatorDropdown`, and the generic `ParameterConfigurator` shell.
2.  **Phase 2: High-Value Agents**: Implement `Stewardship Flagger` (Business Rules) and `Semantic Mapper` (Mappings). These are the most used.
3.  **Phase 3: Validation & Cleaning**: Implement `Cleanse Previewer` and `Contract Enforcer`.
4.  **Phase 4: Advanced Logic**: Implement `Survivorship` and `Fuzzy Config` screens.
5.  **Phase 5**: Integrate "Beginner Mode" wizards for the most complex tasks (Business Rules).
