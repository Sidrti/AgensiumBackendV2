"""
Downloads Utilities Module

Shared utilities for Excel and JSON report generation across download modules.
Provides common styling, formatting, and sheet creation functions.
"""

from typing import Dict, List, Any
from datetime import datetime
import json
import base64
import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class ExcelStyler:
    """Provides consistent Excel styling across all download modules."""
    
    def __init__(self):
        """Initialize Excel styles."""
        self.header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        self.header_font = Font(color="FFFFFF", bold=True, size=11)
        self.subheader_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        self.subheader_font = Font(bold=True, size=10)
        self.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        self.center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        self.left_alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
    
    def set_column_widths(self, ws, widths: List[int]):
        """Set column widths for worksheet."""
        for col_idx, width in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width


class CommonSheetCreator:
    """Creates common sheets used across different download modules."""
    
    def __init__(self, styler: ExcelStyler):
        """Initialize with an ExcelStyler instance."""
        self.styler = styler
    
    def create_ai_summary_sheet(self, wb: Workbook, analysis_summary: Dict[str, Any]):
        """Create AI-generated analysis summary sheet."""
        ws = wb.create_sheet("AI Analysis Summary")
        self.styler.set_column_widths(ws, [35, 80])
        
        row = 1
        ws[f'A{row}'] = "AI-GENERATED ANALYSIS SUMMARY"
        ws[f'A{row}'].font = Font(bold=True, size=12, color="FFFFFF")
        ws[f'A{row}'].fill = self.styler.header_fill
        ws.merge_cells(f'A{row}:B{row}')
        row += 2
        
        # Metadata
        metadata = [
            ["Status", analysis_summary.get("status", "")],
            ["Model Used", analysis_summary.get("model_used", "")],
            ["Generation Time (ms)", analysis_summary.get("execution_time_ms", 0)]
        ]
        
        for key, value in metadata:
            ws.cell(row=row, column=1, value=key).font = Font(bold=True)
            ws.cell(row=row, column=2, value=value)
            row += 1
        
        row += 1
        
        # Summary text
        ws[f'A{row}'] = "SUMMARY"
        ws[f'A{row}'].font = Font(bold=True, size=10)
        ws[f'A{row}'].fill = self.styler.subheader_fill
        ws.merge_cells(f'A{row}:B{row}')
        row += 1
        
        summary_text = analysis_summary.get("summary", "")
        ws.cell(row=row, column=1, value=summary_text)
        ws.merge_cells(f'A{row}:B{row}')
        ws.cell(row=row, column=1).alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
        
        # Set row height for wrapped text
        ws.row_dimensions[row].height = max(15 * (len(summary_text) // 100 + 1), 30)
    
    def create_row_level_issues_sheet(self, wb: Workbook, row_level_issues: List[Dict], issue_summary: Dict[str, Any]):
        """Create row-level issues sheet."""
        ws = wb.create_sheet("Row-Level Issues")
        self.styler.set_column_widths(ws, [15, 25, 20, 15, 15, 50, 30])
        
        row = 1
        ws[f'A{row}'] = "ROW-LEVEL ISSUES"
        ws[f'A{row}'].font = Font(bold=True, size=12, color="FFFFFF")
        ws[f'A{row}'].fill = self.styler.header_fill
        ws.merge_cells(f'A{row}:G{row}')
        row += 2
        
        # Issue summary statistics
        ws[f'A{row}'] = "ISSUE SUMMARY STATISTICS"
        ws[f'A{row}'].font = Font(bold=True, size=10)
        ws[f'A{row}'].fill = self.styler.subheader_fill
        ws.merge_cells(f'A{row}:B{row}')
        row += 1
        
        summary_stats = [
            ["Total Issues", issue_summary.get("total_issues", 0)],
            ["Affected Rows", issue_summary.get("affected_rows", 0)],
            ["Affected Columns", len(issue_summary.get("affected_columns", []))],
            ["Critical Severity", issue_summary.get("by_severity", {}).get("critical", 0)],
            ["Warning Severity", issue_summary.get("by_severity", {}).get("warning", 0)],
            ["Info Severity", issue_summary.get("by_severity", {}).get("info", 0)]
        ]
        
        for key, value in summary_stats:
            ws.cell(row=row, column=1, value=key).font = Font(bold=True)
            ws.cell(row=row, column=2, value=value)
            row += 1
        
        row += 1
        
        # Issues by type
        ws[f'A{row}'] = "ISSUES BY TYPE"
        ws[f'A{row}'].font = Font(bold=True, size=10)
        ws[f'A{row}'].fill = self.styler.subheader_fill
        ws.merge_cells(f'A{row}:B{row}')
        row += 1
        
        for issue_type, count in issue_summary.get("by_type", {}).items():
            ws.cell(row=row, column=1, value=issue_type)
            ws.cell(row=row, column=2, value=count)
            row += 1
        
        row += 2
        
        # Row-level issues table
        ws[f'A{row}'] = "DETAILED ROW-LEVEL ISSUES"
        ws[f'A{row}'].font = Font(bold=True, size=10)
        ws[f'A{row}'].fill = self.styler.subheader_fill
        ws.merge_cells(f'A{row}:G{row}')
        row += 1
        
        headers = ["Row Index", "Column", "Issue Type", "Severity", "Agent ID", "Description", "Suggested Action"]
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col_idx, value=header)
            cell.fill = self.styler.header_fill
            cell.font = self.styler.header_font
            cell.border = self.styler.border
            cell.alignment = self.styler.center_alignment
        row += 1
        
        # Add issues (limit to first 1000 as mentioned in transformer)
        for issue in row_level_issues[:1000]:
            ws.cell(row=row, column=1, value=issue.get("row_index", ""))
            ws.cell(row=row, column=2, value=issue.get("column", ""))
            ws.cell(row=row, column=3, value=issue.get("issue_type", ""))
            ws.cell(row=row, column=4, value=issue.get("severity", ""))
            ws.cell(row=row, column=5, value=issue.get("agent_id", ""))
            ws.cell(row=row, column=6, value=issue.get("description", ""))
            ws.cell(row=row, column=7, value=issue.get("suggested_action", ""))
            
            for col_idx in range(1, 8):
                ws.cell(row=row, column=col_idx).border = self.styler.border
                ws.cell(row=row, column=col_idx).alignment = self.styler.left_alignment
            row += 1
    
    def create_routing_decisions_sheet(self, wb: Workbook, routing_decisions: List[Dict]):
        """Create routing decisions sheet."""
        ws = wb.create_sheet("Routing Decisions")
        self.styler.set_column_widths(ws, [20, 15, 20, 50, 30, 15])
        
        row = 1
        ws[f'A{row}'] = "ROUTING DECISIONS"
        ws[f'A{row}'].font = Font(bold=True, size=12, color="FFFFFF")
        ws[f'A{row}'].fill = self.styler.header_fill
        ws.merge_cells(f'A{row}:F{row}')
        row += 2
        
        ws[f'A{row}'] = f"Total Routing Recommendations: {len(routing_decisions)}"
        ws[f'A{row}'].font = Font(bold=True, size=10)
        ws.merge_cells(f'A{row}:B{row}')
        row += 2
        
        headers = ["Tool ID", "Priority", "Trigger Reason", "Rationale", "Expected Benefit", "Confidence"]
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col_idx, value=header)
            cell.fill = self.styler.header_fill
            cell.font = self.styler.header_font
            cell.border = self.styler.border
            cell.alignment = self.styler.center_alignment
        row += 1
        
        for decision in routing_decisions:
            ws.cell(row=row, column=1, value=decision.get("tool_id", ""))
            ws.cell(row=row, column=2, value=decision.get("priority", ""))
            ws.cell(row=row, column=3, value=decision.get("trigger_reason", ""))
            ws.cell(row=row, column=4, value=decision.get("rationale", ""))
            ws.cell(row=row, column=5, value=decision.get("expected_benefit", ""))
            ws.cell(row=row, column=6, value=decision.get("confidence", ""))
            
            for col_idx in range(1, 7):
                ws.cell(row=row, column=col_idx).border = self.styler.border
                ws.cell(row=row, column=col_idx).alignment = self.styler.left_alignment
            row += 1
    
    def create_alerts_sheet(self, wb: Workbook, alerts: List[Dict]):
        """Create alerts sheet."""
        ws = wb.create_sheet("Alerts")
        self.styler.set_column_widths(ws, [20, 15, 20, 50, 20, 30])
        
        row = 1
        headers = ["Alert ID", "Severity", "Category", "Message", "Affected Fields", "Recommendation"]
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col_idx, value=header)
            cell.fill = self.styler.header_fill
            cell.font = self.styler.header_font
            cell.border = self.styler.border
            cell.alignment = self.styler.center_alignment
        row += 1
        
        for alert in alerts:
            ws.cell(row=row, column=1, value=alert.get("alert_id", ""))
            ws.cell(row=row, column=2, value=alert.get("severity", ""))
            ws.cell(row=row, column=3, value=alert.get("category", ""))
            ws.cell(row=row, column=4, value=alert.get("message", ""))
            ws.cell(row=row, column=5, value=", ".join(alert.get("affected_fields", [])))
            ws.cell(row=row, column=6, value=alert.get("recommendation", ""))
            
            for col_idx in range(1, 7):
                ws.cell(row=row, column=col_idx).border = self.styler.border
                ws.cell(row=row, column=col_idx).alignment = self.styler.left_alignment
            row += 1
    
    def create_issues_sheet(self, wb: Workbook, issues: List[Dict]):
        """Create issues sheet."""
        ws = wb.create_sheet("Issues")
        self.styler.set_column_widths(ws, [20, 20, 20, 20, 15, 50])
        
        row = 1
        headers = ["Issue ID", "Agent", "Field", "Issue Type", "Severity", "Message"]
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col_idx, value=header)
            cell.fill = self.styler.header_fill
            cell.font = self.styler.header_font
            cell.border = self.styler.border
            cell.alignment = self.styler.center_alignment
        row += 1
        
        for issue in issues:
            ws.cell(row=row, column=1, value=issue.get("issue_id", ""))
            ws.cell(row=row, column=2, value=issue.get("agent_id", ""))
            ws.cell(row=row, column=3, value=issue.get("field_name", ""))
            ws.cell(row=row, column=4, value=issue.get("issue_type", ""))
            ws.cell(row=row, column=5, value=issue.get("severity", ""))
            ws.cell(row=row, column=6, value=issue.get("message", ""))
            
            for col_idx in range(1, 7):
                ws.cell(row=row, column=col_idx).border = self.styler.border
                ws.cell(row=row, column=col_idx).alignment = self.styler.left_alignment
            row += 1
    
    def create_recommendations_sheet(self, wb: Workbook, recommendations: List[Dict]):
        """Create recommendations sheet."""
        ws = wb.create_sheet("Recommendations")
        self.styler.set_column_widths(ws, [25, 20, 20, 15, 50, 15])
        
        row = 1
        headers = ["Recommendation ID", "Agent", "Field", "Priority", "Recommendation", "Timeline"]
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col_idx, value=header)
            cell.fill = self.styler.header_fill
            cell.font = self.styler.header_font
            cell.border = self.styler.border
            cell.alignment = self.styler.center_alignment
        row += 1
        
        for rec in recommendations:
            ws.cell(row=row, column=1, value=rec.get("recommendation_id", ""))
            ws.cell(row=row, column=2, value=rec.get("agent_id", ""))
            ws.cell(row=row, column=3, value=rec.get("field_name", ""))
            ws.cell(row=row, column=4, value=rec.get("priority", ""))
            ws.cell(row=row, column=5, value=rec.get("recommendation", ""))
            ws.cell(row=row, column=6, value=rec.get("timeline", ""))
            
            for col_idx in range(1, 7):
                ws.cell(row=row, column=col_idx).border = self.styler.border
                ws.cell(row=row, column=col_idx).alignment = self.styler.left_alignment
            row += 1


def load_tool_config(tool_id: str) -> Dict[str, Any]:
    """
    Load tool configuration from JSON file.
    
    Args:
        tool_id: Tool identifier (e.g., 'profile-my-data', 'clean-my-data')
    
    Returns:
        Tool configuration dictionary
    """
    try:
        # Get the tools directory path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        tools_dir = os.path.join(project_root, 'tools')
        
        # Construct the tool JSON file path
        tool_file = os.path.join(tools_dir, f"{tool_id.replace('-', '_')}_tool.json")
        
        # Load and return the configuration
        with open(tool_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config
    except Exception as e:
        print(f"Error loading tool config for {tool_id}: {str(e)}")
        return {}


def get_agents_metadata(tool_id: str, agent_results: Dict[str, Any]) -> tuple:
    """
    Extract agent names and lineage from tool config and agent results.
    
    Args:
        tool_id: Tool identifier
        agent_results: Dictionary of agent execution results
    
    Returns:
        Tuple of (agents_names: List[str], agents_ids: List[str])
    """
    # Load tool configuration
    tool_config = load_tool_config(tool_id)
    
    if not tool_config:
        # Fallback: extract from agent_results
        agents_ids = [aid for aid, result in agent_results.items() if result.get("status") == "success"]
        agents_names = [result.get("agent_name", aid) for aid, result in agent_results.items() if result.get("status") == "success"]
        return agents_names, agents_ids
    
    # Get the ordered list of available agents from tool config
    available_agents = tool_config.get('tool', {}).get('available_agents', [])
    
    # Get agent configurations to extract names
    agents_config = tool_config.get('agents', {})
    
    # Filter to only include agents that were successfully executed
    agents_ids = [aid for aid in available_agents if aid in agent_results and agent_results[aid].get("status") == "success"]
    
    # Extract agent names from config or results
    agents_names = []
    for aid in agents_ids:
        # Try to get name from tool config first
        agent_name = agents_config.get(aid, {}).get('name')
        
        # If not in config, try to get from agent results
        if not agent_name:
            agent_name = agent_results[aid].get('agent_name', aid)
        
        agents_names.append(agent_name)
    
    return agents_names, agents_ids


def build_json_report_structure(
    analysis_id: str,
    tool: str,
    execution_time_ms: int,
    alerts: List[Dict],
    issues: List[Dict],
    recommendations: List[Dict],
    executive_summary: List[Dict],
    analysis_summary: Dict[str, Any],
    row_level_issues: List[Dict],
    issue_summary: Dict[str, Any],
    routing_decisions: List[Dict],
    agent_results: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build standardized JSON report structure.
    
    Args:
        analysis_id: Unique analysis identifier
        tool: Tool name (e.g., "profile-my-data", "clean-my-data")
        execution_time_ms: Total execution time
        alerts: List of alerts
        issues: List of issues
        recommendations: List of recommendations
        executive_summary: Executive summary items
        analysis_summary: AI-generated analysis summary
        row_level_issues: List of row-level issues
        issue_summary: Summary of issues by type and severity
        routing_decisions: List of routing recommendations
        agent_results: Dictionary of agent outputs
    
    Returns:
        Dictionary containing complete JSON report structure
    """
    # Get agents metadata dynamically from tool config and agent results
    agents_names, agents_ids = get_agents_metadata(tool, agent_results)
    
    report_data = {
        "metadata": {
            "analysis_id": analysis_id,
            "tool": tool,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "execution_time_ms": execution_time_ms,
            "report_version": "1.0",
            "agents_name": agents_names,
            "lineage": agents_names
        },
        "executive_summary": executive_summary,
        "analysis_summary": analysis_summary,
        "summary": {
            "total_alerts": len(alerts),
            "total_issues": len(issues),
            "total_recommendations": len(recommendations),
            "critical_alerts": len([a for a in alerts if a.get('severity') == 'critical']),
            "high_severity_alerts": len([a for a in alerts if a.get('severity') == 'high']),
            "medium_severity_alerts": len([a for a in alerts if a.get('severity') == 'medium'])
        },
        "alerts": alerts,
        "issues": issues,
        "recommendations": recommendations,
        "row_level_issues": row_level_issues,
        "issue_summary": issue_summary,
        "routing_decisions": routing_decisions,
        "agent_results": {}
    }
    
    # Add complete agent outputs
    for agent_id, agent_output in agent_results.items():
        if agent_output.get("status") == "success":
            report_data["agent_results"][agent_id] = {
                "status": agent_output.get("status"),
                "execution_time_ms": agent_output.get("execution_time_ms", 0),
                "summary_metrics": agent_output.get("summary_metrics", {}),
                "data": agent_output.get("data", {}),
                "timestamp": agent_output.get("timestamp", "")
            }
    
    return report_data


def generate_json_download(
    analysis_id: str,
    tool: str,
    file_name: str,
    description: str,
    report_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate JSON download metadata with base64 encoded content.
    
    Args:
        analysis_id: Unique analysis identifier
        tool: Tool name
        file_name: Output file name
        description: Download description
        report_data: Complete report data dictionary
    
    Returns:
        Dictionary containing download metadata
    """
    try:
        # Convert to JSON string
        json_str = json.dumps(report_data, indent=2, default=str)
        json_bytes = json_str.encode('utf-8')
        
        return {
            "download_id": f"{analysis_id}_{tool}_json",
            "name": f"{tool.replace('-', ' ').title()} - Complete Analysis JSON",
            "format": "json",
            "file_name": file_name,
            "description": description,
            "mimeType": "application/json",
            "content_base64": base64.b64encode(json_bytes).decode('utf-8'),
            "size_bytes": len(json_bytes),
            "creation_date": datetime.utcnow().isoformat() + "Z",
            "type": "complete_report"
        }
    except Exception as e:
        print(f"Error generating JSON download: {str(e)}")
        return {
            "download_id": f"{analysis_id}_{tool}_json_error",
            "status": "error",
            "error": str(e)
        }
