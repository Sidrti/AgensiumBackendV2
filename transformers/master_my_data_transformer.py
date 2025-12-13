"""
Master My Data Transformer

Consolidates outputs from master data management agents into unified response.
Agents generate their own alerts, issues, recommendations, executive summaries, and AI analysis.
Transformer aggregates these outputs and generates downloads.
"""

import time
import base64
import io
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import UploadFile, HTTPException

from ai.analysis_summary_ai import AnalysisSummaryAI
from downloads.master_my_data_downloads import MasterMyDataDownloads
from agents import key_identifier, contract_enforcer, semantic_mapper, lineage_tracer, golden_record_builder, survivorship_resolver, master_writeback_agent, stewardship_flagger
from transformers.transformers_utils import (
    get_required_files,
    validate_files,
    read_uploaded_files,
    convert_files_to_csv,
    persist_downloads_to_outputs,
)

# Billing imports
from billing.wallet_service import WalletService
from billing.agent_costs_service import AgentCostsService
from billing.exceptions import InsufficientCreditsError, AgentCostNotFoundError, UserWalletNotFoundError
from db.database import SessionLocal


async def run_master_my_data_analysis(
    tool_id: str,
    agents: Optional[str],
    parameters_json: Optional[str],
    primary: Optional[UploadFile],
    baseline: Optional[UploadFile],
    analysis_id: str,
    current_user: Any = None
) -> Dict[str, Any]:
    """
    Execute master-my-data analysis.
    
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
        
        # Initialize billing services if user is authenticated
        billing_enabled = current_user is not None and hasattr(current_user, 'id')
        db_session = None
        wallet_service = None
        
        if billing_enabled:
            try:
                db_session = SessionLocal()
                wallet_service = WalletService(db_session)
            except Exception as e:
                print(f"Warning: Could not initialize billing services: {e}")
                billing_enabled = False
        
        try:
            for agent_id in agents_to_run:
                try:
                    # ========== BILLING: Debit credits before agent execution ==========
                    if billing_enabled and wallet_service:
                        try:
                            wallet_service.consume_for_agent(
                                user_id=current_user.id,
                                agent_id=agent_id,
                                tool_id=tool_id,
                                analysis_id=analysis_id
                            )
                            print(f"[Billing] Debited credits for agent: {agent_id}")
                        except InsufficientCreditsError as e:
                            # Return error response with billing details
                            return {
                                "analysis_id": analysis_id,
                                "tool": tool_id,
                                "status": "error",
                                "error_code": "BILLING_INSUFFICIENT_CREDITS",
                                "error": e.detail,
                                "context": e.context,
                                "execution_time_ms": int((time.time() - start_time) * 1000),
                                "partial_results": agent_results
                            }
                        except AgentCostNotFoundError as e:
                            # Agent cost not configured - log warning but continue
                            print(f"Warning: Agent cost not configured for {agent_id}: {e.detail}")
                        except UserWalletNotFoundError as e:
                            # User doesn't have a wallet - return error
                            return {
                                "analysis_id": analysis_id,
                                "tool": tool_id,
                                "status": "error",
                                "error_code": "BILLING_WALLET_NOT_FOUND",
                                "error": e.detail,
                                "context": e.context,
                                "execution_time_ms": int((time.time() - start_time) * 1000)
                            }
                    # ========== END BILLING ==========
                    
                    # Build agent-specific input
                    agent_input = _build_agent_input(agent_id, files_map, parameters, tool_def)
                    
                    # Execute agent
                    result = _execute_agent(agent_id, agent_input)
                    
                    agent_results[agent_id] = result
                    
                    # Update files map for next agent (chaining)
                    _update_files_from_result(files_map, result)
                    
                except Exception as e:
                    agent_results[agent_id] = {
                        "status": "error",
                        "error": str(e),
                        "execution_time_ms": 0
                    }
        finally:
            # Clean up database session
            if db_session:
                db_session.close()
        
        # Transform results
        return transform_master_my_data_response(
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


def _update_files_from_result(
    files_map: Dict[str, tuple],
    result: Dict[str, Any]
) -> None:
    """Update files map with cleaned file from agent result."""
    agent_id = result.get("agent_id", "unknown_agent")
    
    if result.get("status") == "success" and "cleaned_file" in result:
        cleaned_file = result["cleaned_file"]
        if cleaned_file and "content" in cleaned_file:
            try:
                # Decode base64 content
                new_content = base64.b64decode(cleaned_file["content"])
                new_filename = cleaned_file.get("filename", "cleaned_data.csv")
                
                # Update primary file for next agent
                files_map["primary"] = (new_content, new_filename)
                print(f"[{agent_id}] Successfully updated primary file: {new_filename}. New size: {len(new_content)} bytes")
            except Exception as e:
                print(f"[{agent_id}] Error updating file from result: {str(e)}")
                pass
    else:
        print(f"[{agent_id}] No cleaned file produced. Continuing with previous file.")


def _execute_agent(
    agent_id: str,
    agent_input: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute specific agent."""
    files_map = agent_input.get("files", {})
    parameters = agent_input.get("parameters", {})
    
    if agent_id == "key-identifier":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Key identifier requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return key_identifier.execute_key_identifier(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "contract-enforcer":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Contract enforcer requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return contract_enforcer.execute_contract_enforcer(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "semantic-mapper":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Semantic mapper requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return semantic_mapper.execute_semantic_mapper(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "lineage-tracer":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Lineage tracer requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return lineage_tracer.execute_lineage_tracer(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "golden-record-builder":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Golden record builder requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return golden_record_builder.execute_golden_record_builder(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "survivorship-resolver":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Survivorship resolver requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return survivorship_resolver.execute_survivorship_resolver(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "master-writeback-agent":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Master writeback agent requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return master_writeback_agent.execute_master_writeback_agent(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    elif agent_id == "stewardship-flagger":
        if "primary" not in files_map:
            return {
                "status": "error",
                "error": "Stewardship flagger requires 'primary' file",
                "execution_time_ms": 0
            }
        
        primary_bytes, primary_filename = files_map["primary"]
        
        return stewardship_flagger.execute_stewardship_flagger(
            primary_bytes,
            primary_filename,
            parameters
        )
    
    else:
        return {
            "status": "error",
            "error": f"Unknown agent for master-my-data: {agent_id}",
            "execution_time_ms": 0
        }


def transform_master_my_data_response(
    agent_results: Dict[str, Any],
    execution_time_ms: int,
    analysis_id: str,
    current_user: Any = None
) -> Dict[str, Any]:
    """Consolidate agent outputs into unified response."""
    
    # Print current user data
    if current_user:
        print(f"[Transformer] Master My Data - Current User: ID={current_user.id}, Email={current_user.email}, Active={current_user.is_active}, Verified={current_user.is_verified}")
    
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

    # Persist downloads to disk (best-effort; does not affect API response)
    # try:
    #     if current_user is not None and hasattr(current_user, "id"):
    #         persist_downloads_to_outputs(
    #             downloads=downloads,
    #             user_id=current_user.id,
    #             analysis_id=analysis_id,
    #         )
    # except Exception as e:
    #     print(f"Warning: failed to persist downloads for analysis {analysis_id}: {str(e)}")
    
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
