"""
Profile My Data Transformer

Consolidates outputs from profiling agents into unified response.
Agents generate their own alerts, issues, recommendations, executive summaries, and AI analysis.
Transformer aggregates these outputs and generates downloads.
"""

import time
import json
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from datetime import datetime
from fastapi import UploadFile, HTTPException

from ai.analysis_summary_ai import AnalysisSummaryAI
from downloads.profile_my_data_downloads import ProfileMyDataDownloads
from agents import readiness_rater, unified_profiler, drift_detector, score_risk, governance_checker, test_coverage_agent
from transformers.transformers_utils import (
    get_required_files,
    validate_files,
    read_uploaded_files,
    convert_files_to_csv,
)
from billing import BillingContext, InsufficientCreditsError, UserWalletNotFoundError, AgentCostNotFoundError
from services.s3_service import s3_service

if TYPE_CHECKING:
    from db import models


async def run_profile_my_data_analysis(
    tool_id: str,
    agents: Optional[str],
    parameters_json: Optional[str],
    primary: Optional[UploadFile],
    baseline: Optional[UploadFile],
    analysis_id: str,
    current_user: Any = None
) -> Dict[str, Any]:
    """
    Execute profile-my-data analysis.
    
    Args:
        tool_id: Tool identifier
        agents: Comma-separated agent IDs
        parameters_json: JSON string with agent-specific parameters
        primary: Primary data file
        baseline: Optional baseline/reference file
        analysis_id: Unique analysis ID
        current_user: Current user object
        
    Returns:
        Final analysis response
    """
    start_time = time.time()
    
    try:
        from main import TOOL_DEFINITIONS
        
        # Validate tool
        if tool_id not in TOOL_DEFINITIONS:
            raise HTTPException(status_code=400, detail=f"Tool '{tool_id}' not found")
        
        tool_def = TOOL_DEFINITIONS[tool_id]
        
        # Determine which agents to run
        agents_to_run = tool_def["tool"]["available_agents"]
        if agents:
            agents_to_run = [a.strip() for a in agents.split(",")]
        
        # Get required files for tool and agents
        required_files = get_required_files(tool_id, agents_to_run)
        
        # Build uploaded files dictionary
        uploaded_files = {
            "primary": primary,
            "baseline": baseline
        }
        uploaded_files = {k: v for k, v in uploaded_files.items() if v is not None}
        
        # Validate files against requirements
        validation_errors = validate_files(uploaded_files, required_files)
        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail=f"File validation failed: {validation_errors}"
            )
        
        # Read uploaded files into memory
        files_map = await read_uploaded_files(uploaded_files)
        
        # Convert files to CSV format
        files_map = convert_files_to_csv(files_map)
        
        # Parse parameters
        parameters = {}
        if parameters_json:
            try:
                parameters = json.loads(parameters_json)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid parameters JSON")
        
        agent_results = {}
        
        # ========== UPFRONT BILLING: Check and consume ALL credits before execution ==========
        with BillingContext(current_user) as billing:
            try:
                billing_result = billing.validate_and_consume_all(
                    agents=agents_to_run,
                    tool_id=tool_id,
                    task_id=analysis_id
                )
                print(f"[Billing] Consumed {billing_result.get('total_consumed', 0)} credits upfront for {len(agents_to_run)} agents")
            except (InsufficientCreditsError, UserWalletNotFoundError, AgentCostNotFoundError) as e:
                return billing.get_billing_error_response(
                    error=e,
                    task_id=analysis_id,
                    tool_id=tool_id,
                    start_time=start_time
                )
        # ========== END UPFRONT BILLING ==========
        
        # Execute agents (billing already handled)
        for agent_id in agents_to_run:
            try:
                # Build agent-specific input
                agent_input = _build_agent_input(agent_id, files_map, parameters, tool_def)
                
                # Execute agent
                result = _execute_agent(agent_id, agent_input)
                
                agent_results[agent_id] = result
                
            except Exception as e:
                agent_results[agent_id] = {
                    "status": "error",
                    "error": str(e),
                    "execution_time_ms": 0
                }
        
        # Transform results
        return transform_profile_my_data_response(
            agent_results,
            int((time.time() - start_time) * 1000),
            analysis_id,
            current_user
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "analysis_id": analysis_id,
            "status": "error",
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


# ============================================================================
# V2.1 FUNCTION - Read files and parameters from S3
# ============================================================================

async def run_profile_my_data_analysis_v2_1(
    task: "models.Task",
    current_user: Any,
    db: Any
) -> Dict[str, Any]:
    """
    Execute profile-my-data analysis using S3 files (V2.1).
    
    This function reads files AND parameters from Backblaze B2 storage
    instead of receiving them in the request body.
    
    Args:
        task: Task model with task_id, user_id, tool_id, agents
        current_user: Current user object
        db: Database session for updating task progress
        
    Returns:
        Result dict with status and optional error info
    """
    from main import TOOL_DEFINITIONS
    from db.models import TaskStatus
    import base64
    
    start_time = time.time()
    
    try:
        tool_def = TOOL_DEFINITIONS[task.tool_id]
        
        # Read input files from S3
        print(f"[V2.1] Reading input files from S3 for task {task.task_id}")
        input_files = s3_service.list_input_files(task.user_id, task.task_id)
        
        if not input_files:
            return {
                "status": "error",
                "error": "No input files found in S3",
                "error_code": "NO_INPUT_FILES"
            }
        
        # Build files_map from S3 files
        files_map = {}
        for file_info in input_files:
            filename = file_info['filename']
            
            # Determine file key (primary, baseline)
            file_key = _determine_file_key_v2_1(filename)
            
            # Download file content
            content = s3_service.get_file_bytes(file_info['key'])
            files_map[file_key] = (content, filename)
            print(f"[V2.1] Loaded {file_key}: {filename} ({len(content)} bytes)")
        
        # Convert files to CSV if needed
        files_map = convert_files_to_csv(files_map)
        
        # Read parameters from S3
        parameters = s3_service.get_parameters(task.user_id, task.task_id) or {}
        print(f"[V2.1] Parameters loaded: {list(parameters.keys())}")
        
        agent_results = {}
        agents_completed = 0
        total_agents = len(task.agents)
        
        # ========== UPFRONT BILLING: Check and consume ALL credits before execution ==========
        with BillingContext(current_user) as billing:
            try:
                billing_result = billing.validate_and_consume_all(
                    agents=task.agents,
                    tool_id=task.tool_id,
                    task_id=task.task_id
                )
                print(f"[V2.1] Billing: Consumed {billing_result.get('total_consumed', 0)} credits upfront for {len(task.agents)} agents")
            except (InsufficientCreditsError, UserWalletNotFoundError, AgentCostNotFoundError) as e:
                return billing.get_billing_error_response(
                    error=e,
                    task_id=task.task_id,
                    tool_id=task.tool_id,
                    start_time=start_time
                )
        # ========== END UPFRONT BILLING ==========
        
        # Execute agents (billing already handled)
        for agent_id in task.agents:
            try:
                # Update task progress
                task.current_agent = agent_id
                task.progress = 15 + int((agents_completed / total_agents) * 80)
                db.commit()
                
                # Build agent input
                agent_input = _build_agent_input(agent_id, files_map, parameters, tool_def)
                
                # Execute agent
                result = _execute_agent(agent_id, agent_input)
                agent_results[agent_id] = result
                
                agents_completed += 1
                print(f"[V2.1] Agent {agent_id} completed ({agents_completed}/{total_agents})")
                
            except Exception as e:
                agent_results[agent_id] = {
                    "status": "error",
                    "error": str(e),
                    "execution_time_ms": 0
                }
        
        # Transform results
        final_result = transform_profile_my_data_response(
            agent_results,
            int((time.time() - start_time) * 1000),
            task.task_id,
            current_user
        )
        
        # Upload outputs to S3
        await _upload_outputs_to_s3_v2_1(
            task=task,
            downloads=final_result.get("report", {}).get("downloads", [])
        )
        
        return {"status": "success"}
        
    except Exception as e:
        print(f"[V2.1] Error in profile analysis: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "error_code": "PROCESSING_ERROR"
        }


def _determine_file_key_v2_1(filename: str) -> str:
    """Determine file key from filename."""
    lower = filename.lower()
    if 'baseline' in lower:
        return 'baseline'
    return 'primary'


async def _upload_outputs_to_s3_v2_1(
    task: "models.Task",
    downloads: List[Dict]
) -> int:
    """
    Upload download files to S3.
    
    Args:
        task: Task model
        downloads: List of download dicts with content_base64 and file_name
        
    Returns:
        Number of files uploaded
    """
    import base64
    
    uploaded_count = 0
    
    for download in downloads:
        content_b64 = download.get("content_base64")
        filename = download.get("file_name")
        
        if not content_b64 or not filename:
            continue
        
        try:
            # Decode content
            content = base64.b64decode(content_b64)
            
            # Determine content type
            if filename.endswith('.xlsx'):
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif filename.endswith('.json'):
                content_type = "application/json"
            else:
                content_type = "text/csv"
            
            # Build S3 key
            key = f"{task.get_output_prefix()}{filename}"
            
            # Upload
            s3_service.upload_file(key, content, content_type)
            uploaded_count += 1
            print(f"[V2.1] Uploaded output: {filename} ({len(content)} bytes)")
            
        except Exception as e:
            print(f"[V2.1] Error uploading {filename}: {str(e)}")
    
    return uploaded_count


def _build_agent_input(
    agent_id: str,
    files_map: Dict[str, tuple],
    parameters: Dict[str, Any],
    tool_def: Dict[str, Any]
) -> Dict[str, Any]:
    """Build agent-specific input based on tool definition."""
    agent_def = tool_def.get("agents", {}).get(agent_id, {})
    required_files = agent_def.get("required_files", [])
    
    # Build files dictionary for agent
    agent_files = {}
    for file_key in required_files:
        if file_key in files_map:
            agent_files[file_key] = files_map[file_key]
    
    # Get agent parameters
    agent_params = parameters.get(agent_id, {})
    
    return {
        "agent_id": agent_id,
        "files": agent_files,
        "parameters": agent_params
    }


def _execute_agent(
    agent_id: str,
    agent_input: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute specific agent."""
    files_map = agent_input.get("files", {})
    parameters = agent_input.get("parameters", {})
    
    if agent_id == "drift-detector":
        if "primary" not in files_map or "baseline" not in files_map:
            return {
                "status": "error",
                "error": "Drift detector requires 'primary' and 'baseline' files",
                "execution_time_ms": 0
            }
        
        baseline_bytes, baseline_filename = files_map["baseline"]
        primary_bytes, primary_filename = files_map["primary"]
        
        return drift_detector.detect_drift(
            baseline_bytes,
            baseline_filename,
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "readiness-rater":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Readiness rater requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return readiness_rater.rate_readiness(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "unified-profiler":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Unified profiler requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return unified_profiler.profile_data(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "score-risk":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Risk scorer requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return score_risk.score_risk(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "governance-checker":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Governance checker requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return governance_checker.execute_governance(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "test-coverage-agent":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Test coverage agent requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return test_coverage_agent.execute_test_coverage(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    else:
        return {
            "status": "error",
            "error": f"Unknown agent for profile-my-data: {agent_id}",
            "execution_time_ms": 0
        }


def transform_profile_my_data_response(
    agent_results: Dict[str, Any],
    execution_time_ms: int,
    analysis_id: str,
    current_user: Any = None
) -> Dict[str, Any]:
    """Consolidate agent outputs into unified response."""
    
    # Print current user data
    if current_user:
        print(f"[Transformer] Profile My Data - Current User: ID={current_user.id}, Email={current_user.email}, Active={current_user.is_active}, Verified={current_user.is_verified}")
    
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
            dataset_name="Data Profile Analysis"
        )
        analysis_summary = summary_result
    except Exception as e:
        print(f"Warning: OpenAI summary generation failed: {str(e)}. Using fallback summary.")
        analysis_summary = {
            "status": "success",
            "summary": f"Data profile analysis completed. {len(all_alerts)} alerts detected, {len(all_issues)} issues identified.",
            "execution_time_ms": 0,
            "model_used": "fallback-rule-based"
        }
    
    # ==================== ROUTING RECOMMENDATIONS ====================
    routing_decisions = []
    try:
        from ai.routing_decision_ai import RoutingDecisionAI
        routing_ai = RoutingDecisionAI()
        routing_decisions = routing_ai.get_routing_decisions(
            current_tool="profile-my-data",
            agent_results=agent_results,
            primary_filename="data.csv",
            baseline_filename=None,
            current_parameters=None
        )
        print(f"Generated {len(routing_decisions)} routing recommendations")
    except Exception as e:
        print(f"Warning: Routing AI agent failed: {str(e)}")
    
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
    downloader = ProfileMyDataDownloads()
    downloads = downloader.generate_downloads(
        agent_results=agent_results,
        analysis_id=analysis_id,
        execution_time_ms=execution_time_ms,
        alerts=all_alerts,
        issues=all_issues,
        recommendations=all_recommendations,
        executive_summary=executive_summary,
        analysis_summary=analysis_summary,
        row_level_issues=all_row_level_issues,
        issue_summary=issue_summary,
        routing_decisions=routing_decisions
    )

    
    # ==================== BUILD FINAL RESPONSE ====================

    # Include all agent results (both success and error) in the report
    # This provides complete visibility into agent execution
    agent_outputs = {}
    for agent_id, output in agent_results.items():
        agent_outputs[agent_id] = output
    
    return {
        "status": "success" if all(r.get("status") == "success" for r in agent_results.values() if r.get("status")) else "partial",
        "timestamp": datetime.utcnow().isoformat() + "Z",
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
