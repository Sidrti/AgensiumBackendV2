# Agensium Downloads Development Guide

This document provides a comprehensive reference for the **Downloads Module** in the Agensium backend. It details the architecture, shared utilities, and the standard pattern for implementing tool-specific download handlers.

## 1. Architecture Overview

The downloads system uses an **Inheritance + Delegation** pattern to enforce consistency across all tools (Profile, Clean, Master) while allowing for specific report customization.

### Key Components

1.  **`BaseDownloader` (Abstract Base Class)**:
    *   Located in `downloads_utils.py`.
    *   Handles the orchestration of the download generation process.
    *   Manages the lifecycle of the Excel Workbook.
    *   Automatically generates standard sheets (Summary, Alerts, Issues, AI Analysis, etc.).
    *   Automatically generates the JSON report.
    *   Automatically attaches cleaned/mastered CSV files.

2.  **Tool-Specific Downloaders (Concrete Classes)**:
    *   Located in `downloads/`.
    *   Inherit from `BaseDownloader`.
    *   **Responsibility**: Implement *only* the logic for rendering agent-specific data into Excel sheets (e.g., "How to display Drift Analysis").

3.  **`ExcelStyler` & `CommonSheetCreator` (Helpers)**:
    *   Located in `downloads_utils.py`.
    *   `ExcelStyler`: Central repository for all fonts, colors, borders, and alignments.
    *   `CommonSheetCreator`: Generates the universal sheets found in every report.

## 2. The Base Class (`BaseDownloader`)

When you inherit from `BaseDownloader`, you get the following behavior "for free":

### Automatic Workflow (`generate_downloads`)
1.  **Excel Generation**:
    *   Creates a new Workbook.
    *   Generates the **Summary** sheet (Tool name, execution time, agent lineage).
    *   Calls your `create_tool_specific_sheets` method (this is where you work).
    *   Generates **Standard Sheets** (Alerts, Issues, Recommendations, AI Summary, Row-Level Issues, Routing Decisions).
2.  **JSON Generation**:
    *   Builds a standardized hierarchical JSON structure.
    *   Sanitizes data (removes large binary content).
3.  **File Attachment**:
    *   If the transformer passed `cleaned_files`, they are automatically added to the download list.

## 3. Shared Utilities (`downloads_utils.py`)

### `ExcelStyler`
Use these attributes to style your cells. Do **not** create custom styles unless absolutely necessary.

| Attribute | Description | Visual |
| :--- | :--- | :--- |
| `self.header_fill` | Dark Blue background. | Headers |
| `self.header_font` | White, Bold, Size 11. | Headers |
| `self.subheader_fill` | Light Blue background. | Section Titles |
| `self.subheader_font` | Black, Bold, Size 10. | Section Titles |
| `self.border` | Thin border on all sides. | All Table Cells |
| `self.center_alignment` | Centered text. | Headers, Metrics |
| `self.left_alignment` | Left-aligned, Top, Wrapped. | Descriptions, Long Text |

### `CommonSheetCreator`
These methods are called automatically by `BaseDownloader`, but are available if you need to manually invoke them.

*   `create_alerts_sheet(wb, alerts)`
*   `create_issues_sheet(wb, issues)`
*   `create_recommendations_sheet(wb, recommendations)`
*   `create_ai_summary_sheet(wb, analysis_summary)`
*   `create_row_level_issues_sheet(wb, row_level_issues, issue_summary)`
*   `create_routing_decisions_sheet(wb, routing_decisions)`

## 4. Mandatory Return Metadata Standard

The `generate_downloads` method (orchestrated by the Base Class) returns a `List[Dict]`. Every dictionary in this list represents a file available for download. **Consistency here is critical** because the frontend relies on these specific keys to render the download buttons.

| Key | Type | Description |
| :--- | :--- | :--- |
| `download_id` | `str` | A unique string (e.g., `{analysis_id}_excel`). |
| `name` | `str` | User-facing display name (e.g., "Complete Excel Report"). |
| `format` | `str` | The file extension: `xlsx`, `json`, or `csv`. |
| `file_name` | `str` | The actual name of the file when downloaded. |
| `description` | `str` | A detailed tooltip explaining what's in the file. |
| `mimeType` | `str` | Standard MIME type (e.g., `text/csv`, `application/json`). |
| `content_base64`| `str` | **Required.** The file content encoded in Base64. |
| `size_bytes` | `int` | The raw size of the file in bytes. |
| `type` | `str` | Category: `complete_report` or `cleaned_data`. |
| `creation_date` | `str` | ISO 8601 timestamp. |

### Handling Modified Files (Chaining)
For tools that modify data (Clean/Master), the `BaseDownloader` handles the logic of appending these files to the list. Ensure your Transformer passes the `cleaned_files` dictionary to `generate_downloads`.

## 5. Implementation Guide

To create a new downloader (e.g., `AnalyzeMyDataDownloads`), follow these steps:

### Step 1: Inheritance and Init
Pass the `tool_id` (matches `tool.json`) and a display name to `super().__init__`. It is recommended to accept these as arguments for flexibility.

```python
from openpyxl import Workbook
from downloads.downloads_utils import BaseDownloader, load_tool_config

class AnalyzeMyDataDownloads(BaseDownloader):
    def __init__(self, tool_id: str, tool_display_name: str = None):
        # Fallback: Load from config if display name is missing
        if not tool_display_name:
            config = load_tool_config(tool_id)
            tool_display_name = config.get("tool", {}).get("name", tool_id)
            
        super().__init__(tool_id, tool_display_name)
```

### Step 2: Implement `create_tool_specific_sheets`
This is the **only** required method. You must check if an agent ran successfully before creating its sheet.

```python
    def create_tool_specific_sheets(self, wb: Workbook, agent_results: Dict[str, Any]):
        """
        Orchestrate the creation of agent-specific sheets.
        wb: The active openpyxl Workbook object.
        agent_results: Dictionary of agent outputs.
        """
        
        # Example: Customer Segmentation Agent
        segmentation_output = agent_results.get("customer-segmentation-agent", {})
        if segmentation_output.get("status") == "success":
            self._create_segmentation_sheet(wb, segmentation_output)
            
        # Example: Market Basket Agent
        market_output = agent_results.get("market-basket-sequence-agent", {})
        if market_output.get("status") == "success":
            self._create_market_basket_sheet(wb, market_output)
```

### Step 3: Implement Sheet Renderers
Write a private method for each agent. This keeps the logic isolated.

```python
    def _create_segmentation_sheet(self, wb, agent_output):
        ws = wb.create_sheet("Customer Segmentation")
        
        # 1. Set Column Widths (Best Practice: Estimate width based on content)
        self.styler.set_column_widths(ws, [25, 20, 20, 20, 50])
        
        row = 1
        
        # 2. Page Title
        ws[f'A{row}'] = "CUSTOMER SEGMENTATION ANALYSIS"
        ws[f'A{row}'].font = self.header_font  # Use legacy alias or self.styler.header_font
        ws[f'A{row}'].fill = self.header_fill
        row += 2
        
        # 3. Extract Data
        data = agent_output.get("data", {})
        metrics = agent_output.get("summary_metrics", {})
        
        # 4. Metadata Section
        metadata = [
            ["Execution Time", f"{agent_output.get('execution_time_ms', 0)} ms"],
            ["Total Customers", metrics.get("total_customers", 0)]
        ]
        
        for key, value in metadata:
            ws[f'A{row}'] = key
            ws[f'B{row}'] = value
            ws[f'A{row}'].font = Font(bold=True) # Standard bold
            ws[f'A{row}'].fill = self.subheader_fill
            ws[f'A{row}'].border = self.border
            ws[f'B{row}'].border = self.border
            row += 1
            
        row += 1
        
        # 5. Data Table
        headers = ["Segment ID", "Label", "Count", "Value"]
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col_idx, value=header)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = self.center_alignment
            cell.border = self.border
        row += 1
        
        # 6. Iterate and Fill
        for segment in data.get("segment_summary", []):
            ws.cell(row=row, column=1, value=segment.get("segment_id"))
            ws.cell(row=row, column=2, value=segment.get("segment_label"))
            ws.cell(row=row, column=3, value=segment.get("customer_count"))
            ws.cell(row=row, column=4, value=segment.get("total_value"))
            
            # Apply borders to all cells
            for i in range(1, 5):
                ws.cell(row=row, column=i).border = self.border
            row += 1
```

## 5. Advanced Features

### Dynamic Metadata
The system automatically resolves tool and agent names using `main.py` and `tools/*.json` configuration. You do not need to hardcode display names in the summary sheet.

### JSON Structure
The `build_json_report_structure` utility automatically structures the JSON output as:
```json
{
  "metadata": { ... },
  "executive_summary": [ ... ],
  "analysis_summary": { ... },
  "alerts": [ ... ],
  "agent_results": {
      "agent-id": {
          "status": "success",
          "data": { ... } // Raw agent output
      }
  }
}
```

## 6. Checklist for New Downloads

1.  [ ] **Inherit** from `BaseDownloader`.
2.  [ ] **Call** `super().__init__("tool-id", "Display Name")`.
3.  [ ] **Check** `status == "success"` for every agent before creating a sheet.
4.  [ ] **Use** `self.styler` properties for all styling.
5.  [ ] **Export** the class in `downloads/__init__.py`.