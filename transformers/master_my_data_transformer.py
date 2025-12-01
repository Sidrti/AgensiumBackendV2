"""
Master My Data Transformer

Consolidates outputs from master data management agents into unified response.
Agents generate their own alerts, issues, recommendations, executive summaries, and AI analysis.
Transformer aggregates these outputs and generates downloads.
"""

from typing import Dict, List, Any
from datetime import datetime
from ai.analysis_summary_ai import AnalysisSummaryAI
from downloads.master_my_data_downloads import MasterMyDataDownloads


def transform_master_my_data_response(
    agent_results: Dict[str, Any],
    execution_time_ms: int,
    analysis_id: str
) -> Dict[str, Any]:
    """Consolidate agent outputs into unified response."""
    
    # ==================== CONSOLIDATE AGENT OUTPUTS ====================
    
    all_alerts = []
    all_issues = []
    all_recommendations = []
    all_row_level_issues = []
    agent_executive_summaries = []
    agent_ai_analysis_texts = []
    
    for agent_id, agent_output in agent_results.items():
        if agent_output.get("status") == "success":
            all_alerts.extend(agent_output.get("alerts", []))
            all_issues.extend(agent_output.get("issues", []))
            all_recommendations.extend(agent_output.get("recommendations", []))
            all_row_level_issues.extend(agent_output.get("row_level_issues", []))
            agent_executive_summaries.extend(agent_output.get("executive_summary", []))
            
            agent_ai_text = agent_output.get("ai_analysis_text", "")
            if agent_ai_text:
                agent_ai_analysis_texts.append(agent_ai_text)
    
    # ==================== BUILD EXECUTIVE SUMMARY ====================
    executive_summary = []
    active_agents = sum(1 for agent_output in agent_results.values() if agent_output.get("status") == "success")
    total_possible_agents = len(agent_results)
    
    # Always-present summary items
    
    # Agents Executed
    executive_summary.append({
        "summary_id": "exec_agents_used",
        "title": "Agents Executed",
        "value": f"{active_agents}/{total_possible_agents}",
        "status": "success" if active_agents > 0 else "warning",
        "description": f"{active_agents} of {total_possible_agents} agents executed successfully"
    })
    
    # Execution Time
    execution_time_seconds = execution_time_ms / 1000
    executive_summary.append({
        "summary_id": "exec_execution_time",
        "title": "Total Execution Time",
        "value": f"{execution_time_seconds:.2f}s",
        "status": "excellent" if execution_time_seconds < 30 else "good" if execution_time_seconds < 60 else "fair",
        "description": f"Analysis completed in {execution_time_seconds:.2f} seconds"
    })
    
    # Total Alerts
    executive_summary.append({
        "summary_id": "exec_total_alerts",
        "title": "Total Alerts",
        "value": f"{len(all_alerts)}",
        "status": "success" if len(all_alerts) == 0 else "warning" if len(all_alerts) < 5 else "critical",
        "description": f"{len(all_alerts)} alert(s) requiring attention"
    })
    
    # Total Issues
    executive_summary.append({
        "summary_id": "exec_total_issues",
        "title": "Total Issues",
        "value": f"{len(all_issues)}",
        "status": "success" if len(all_issues) == 0 else "warning" if len(all_issues) < 10 else "critical",
        "description": f"{len(all_issues)} issue(s) detected across all fields"
    })
    
    # Total Recommendations
    executive_summary.append({
        "summary_id": "exec_total_recommendations",
        "title": "Total Recommendations",
        "value": f"{len(all_recommendations)}",
        "status": "info",
        "description": f"{len(all_recommendations)} actionable recommendation(s) generated"
    })
    
    # Add agent-specific summary items
    executive_summary.extend(agent_executive_summaries)
    
    # ==================== GENERATE AI SUMMARY ====================
    analysis_text_parts = ["EXECUTIVE SUMMARY:"]
    
    for item in executive_summary:
        analysis_text_parts.append(f"- {item.get('title', '')}: {item.get('description', '')}")
    
    analysis_text_parts.append("")
    
    for agent_text in agent_ai_analysis_texts:
        analysis_text_parts.append(agent_text)
    
    # Top alerts
    if all_alerts:
        analysis_text_parts.append(f"\nCRITICAL ALERTS ({len(all_alerts)} total):")
        for alert in all_alerts[:3]:
            analysis_text_parts.append(f"- {alert.get('severity', '').upper()}: {alert.get('message', '')}")
    
    complete_analysis_text = "\n".join(analysis_text_parts)
    
    analysis_summary = {"status": "pending", "summary": "", "execution_time_ms": 0, "model_used": None}
    
    try:
        ai_generator = AnalysisSummaryAI()
        summary_result = ai_generator.generate_summary(
            analysis_text=complete_analysis_text,
            dataset_name="Master Data Management Analysis"
        )
        analysis_summary = summary_result
    except Exception as e:
        print(f"Warning: OpenAI summary generation failed: {str(e)}. Using fallback summary.")
        analysis_summary = {
            "status": "success",
            "summary": f"Master data management analysis completed with {len(all_alerts)} alerts and {len(all_recommendations)} recommendations. " +
                      f"Key actions: {', '.join([rec.get('recommendation', '')[:50] for rec in all_recommendations[:2]])}.",
            "execution_time_ms": 0,
            "model_used": "fallback-rule-based"
        }
    
    # ==================== ROUTING RECOMMENDATIONS ====================
    routing_decisions = []
    try:
        from ai.routing_decision_ai import RoutingDecisionAI
        
        routing_ai = RoutingDecisionAI()
        routing_decisions = routing_ai.get_routing_decisions(
            current_tool="master-my-data",
            agent_results=agent_results,
            primary_filename="data.csv",
            baseline_filename=None,
            current_parameters=None
        )
        
        print(f"Generated {len(routing_decisions)} routing recommendations")
    except Exception as e:
        print(f"Warning: Routing AI agent failed: {str(e)}")
        routing_decisions = []
    
    # ==================== CALCULATE ISSUE SUMMARY ====================
    issue_summary = {
        "total_issues": len(all_row_level_issues),
        "by_type": {},
        "by_severity": {
            "critical": 0,
            "warning": 0,
            "info": 0
        },
        "affected_rows": len(set(issue.get("row_index") for issue in all_row_level_issues if issue.get("row_index") is not None)),
        "affected_columns": list(set(issue.get("column") for issue in all_row_level_issues if issue.get("column") and issue.get("column") != "global"))
    }
    
    for issue in all_row_level_issues:
        issue_type = issue.get("issue_type", "unknown")
        severity = issue.get("severity", "info")
        
        if issue_type not in issue_summary["by_type"]:
            issue_summary["by_type"][issue_type] = 0
        issue_summary["by_type"][issue_type] += 1
        
        if severity in issue_summary["by_severity"]:
            issue_summary["by_severity"][severity] += 1
    
    # Cap row_level_issues at 1000 to prevent memory issues
    all_row_level_issues = all_row_level_issues[:1000]
    
    # ==================== DOWNLOADS ====================
    # Collect mastered files from agents
    mastered_files_list = []
    for agent_id in ["key-identifier", "contract-enforcer", "semantic-mapper", "survivorship-resolver", "golden-record-builder", "stewardship-flagger"]:
        agent_output = agent_results.get(agent_id, {})
        if agent_output.get("status") == "success":
            if "cleaned_file" in agent_output:
                cleaned_file = agent_output["cleaned_file"]
                filename = cleaned_file.get("filename", "unknown.csv")
                
                # Count number of "mastered_" prefixes in filename
                mastered_count = filename.count("mastered_")
                
                mastered_files_list.append({
                    "agent_id": agent_id,
                    "cleaned_file": cleaned_file,
                    "filename": filename,
                    "mastered_count": mastered_count
                })
                print(f"[{agent_id}] Collected mastered file: {filename} (mastered count: {mastered_count})")
    
    # Sort by mastered_count in ascending order (least processed to most processed)
    mastered_files_list.sort(key=lambda x: x["mastered_count"])
    
    # Only use the file with the maximum mastered count (most processed)
    cleaned_files = {}
    if mastered_files_list:
        most_mastered_item = mastered_files_list[-1]  # Last item after sorting (highest count)
        mastered_file_data = most_mastered_item["cleaned_file"]
        
        # Extract base filename and remove all "mastered_" prefixes
        original_filename = most_mastered_item["filename"]
        # Remove all "mastered_" occurrences from the filename
        base_filename = original_filename.replace("mastered_", "")
        
        # Add datetime suffix to the filename
        from datetime import datetime as dt
        datetime_suffix = dt.utcnow().strftime("%Y%m%d_%H%M%S")
        name_parts = base_filename.rsplit('.', 1)
        if len(name_parts) == 2:
            mastered_filename = f"{name_parts[0]}_mastered_{datetime_suffix}.{name_parts[1]}"
        else:
            mastered_filename = f"{base_filename}_mastered_{datetime_suffix}"
        
        # Update the filename in the mastered file metadata
        mastered_file_data["filename"] = mastered_filename
        
        cleaned_files[most_mastered_item["agent_id"]] = mastered_file_data
        print(f"Using most processed file from [{most_mastered_item['agent_id']}]: {most_mastered_item['filename']} -> {mastered_filename}")
    
    downloader = MasterMyDataDownloads()

    # Sanitize agent_results for downloads: remove potentially large mastered/cleaned file contents
    # The chosen mastered file(s) are already passed via cleaned_files, so we avoid duplicating
    # potentially large payloads in the agent_results used by downloads.
    sanitized_agent_results_for_downloads = {}
    for aid, out in agent_results.items():
        if isinstance(out, dict):
            filtered = {k: v for k, v in out.items() if k != 'cleaned_file'}
        else:
            filtered = out
        sanitized_agent_results_for_downloads[aid] = filtered

    downloads = downloader.generate_downloads(
        agent_results=sanitized_agent_results_for_downloads,
        analysis_id=analysis_id,
        execution_time_ms=execution_time_ms,
        alerts=all_alerts,
        issues=all_issues,
        recommendations=all_recommendations,
        cleaned_files=cleaned_files,
        executive_summary=executive_summary,
        analysis_summary=analysis_summary,
        row_level_issues=all_row_level_issues,
        issue_summary=issue_summary,
        routing_decisions=routing_decisions
    )
    
    # ==================== BUILD FINAL RESPONSE ====================
    
    # Include all agent results (both success and error) in the report
    # This provides complete visibility into agent execution
    # Build agent_outputs for final response but exclude raw cleaned_file/mastered file payloads
    agent_outputs = {}
    for agent_id, output in agent_results.items():
        if isinstance(output, dict):
            agent_outputs[agent_id] = {k: v for k, v in output.items() if k != 'cleaned_file'}
        else:
            agent_outputs[agent_id] = output
    
    return {
        "analysis_id": analysis_id,
        "tool": "master-my-data",
        "status": "success",
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "execution_time_ms": execution_time_ms,
        "report": {
            "alerts": all_alerts,
            "issues": all_issues,
            "recommendations": all_recommendations,
            "executiveSummary": executive_summary,
            "analysisSummary": analysis_summary,
            "rowLevelIssues": all_row_level_issues,
            "issueSummary": issue_summary,
            "routing_decisions": routing_decisions,
            "downloads": downloads,
            **agent_outputs,
        }
    }
