"""
Profile My Data Transformer

Combines outputs from all profiling agents into a final unified response.

Agents:
- unified-profiler: Field-level quality metrics
- drift-detector: Distribution changes from baseline
- score-risk: PII and compliance risk assessment
- readiness-rater: Overall data readiness scores
- governance-checker: Governance compliance validation
- test-coverage-agent: Test coverage validation

This transformer:
1. Takes individual agent outputs
2. Aggregates findings across agents
3. Creates cross-agent alerts and recommendations
4. Generates executive summary
5. Delegates download generation to dedicated download module
6. Creates structured final response
"""

from typing import Dict, List, Any
from datetime import datetime
from ai.analysis_summary_ai import AnalysisSummaryAI
from downloads.profile_my_data_downloads import ProfileMyDataDownloads


def transform_profile_my_data_response(
    agent_results: Dict[str, Any],
    execution_time_ms: int,
    analysis_id: str
) -> Dict[str, Any]:
    """
    Transform individual agent outputs into final unified response.
    
    Args:
        agent_results: Dictionary of agent_id -> agent output
        execution_time_ms: Total execution time
        analysis_id: Unique analysis identifier
        
    Returns:
        Final unified response matching profile-my-data response format
    """
    
    # Extract individual agent outputs
    profiler_output = agent_results.get("unified-profiler", {})
    drift_output = agent_results.get("drift-detector", {})
    risk_output = agent_results.get("score-risk", {})
    readiness_output = agent_results.get("readiness-rater", {})
    governance_output = agent_results.get("governance-checker", {})
    test_output = agent_results.get("test-coverage-agent", {})
    
    # Aggregate findings
    all_alerts = []
    all_issues = []
    all_recommendations = []
    executive_summary = []
    
    # ==================== PROFILER ALERTS & ISSUES ====================
    if profiler_output.get("status") == "success":
        profiler_data = profiler_output.get("data", {})
        quality_summary = profiler_data.get("quality_summary", {})
        quality_score = quality_summary.get("overall_quality_score", 0)
        
        if quality_score < 80:
            quality_grade = "A" if quality_score >= 90 else "B" if quality_score >= 80 else "C" if quality_score >= 70 else "D" if quality_score >= 60 else "F"
            fields_with_issues = len([f for f in profiler_data.get('fields', []) if f.get('quality_score', 0) < 80])
            
            all_alerts.append({
                "alert_id": "alert_quality_001",
                "severity": "high" if quality_score < 60 else "medium",
                "category": "data_quality",
                "message": f"Data quality score is {quality_score:.1f}/100 (Grade {quality_grade})",
                "affected_fields_count": fields_with_issues,
                "recommendation": f"Quality grade: {quality_grade}. {fields_with_issues} field(s) need improvement."
            })
        
        # Add field-level quality issues
        for field in profiler_data.get("fields", []):
            field_quality = field.get("quality_score", 0)
            if field_quality < 80:
                all_issues.append({
                    "issue_id": f"issue_quality_{field.get('field_id')}",
                    "agent_id": "unified-profiler",
                    "field_name": field.get("field_name"),
                    "issue_type": "low_quality_score",
                    "severity": "high" if field_quality < 60 else "medium",
                    "message": f"Field quality score: {field_quality:.1f}/100"
                })
    
    # ==================== DRIFT ALERTS & ISSUES ====================
    if drift_output.get("status") == "success":
        drift_data = drift_output.get("data", {})
        drift_summary = drift_data.get("drift_summary", {})
        
        if drift_summary.get("dataset_stability") == "warning":
            drift_count = drift_summary.get("fields_with_drift", 0)
            drift_percentage = drift_summary.get("drift_percentage", 0)
            
            all_alerts.append({
                "alert_id": "alert_drift_001",
                "severity": "high",
                "category": "drift",
                "message": f"Distribution drift in {drift_count}/{drift_summary.get('fields_analyzed', 0)} fields ({drift_percentage:.1f}% affected)",
                "affected_fields_count": drift_count,
                "recommendation": f"{drift_count} field(s) showing drift. Retrain ML models with current data."
            })
        
        # Add field drift issues
        for field in drift_data.get("fields", []):
            if field.get("drift_analysis", {}).get("drift_detected", False):
                all_issues.append({
                    "issue_id": f"issue_drift_{field.get('field_id')}",
                    "agent_id": "drift-detector",
                    "field_name": field.get("field_name"),
                    "issue_type": "distribution_drift",
                    "severity": "high",
                    "message": f"Significant distribution drift detected (PSI: {field.get('drift_analysis', {}).get('psi_score', 0):.4f})"
                })
    
    # ==================== RISK ALERTS & ISSUES ====================
    if risk_output.get("status") == "success":
        risk_data = risk_output.get("data", {})
        risk_summary = risk_data.get("risk_summary", {})
        summary_metrics = risk_output.get("summary_metrics", {})
        
        overall_risk_level = risk_summary.get("overall_risk_level", "low")
        if overall_risk_level in ["high", "medium"]:
            overall_risk_score = risk_summary.get("overall_risk_score", 0)
            high_risk_count = summary_metrics.get("fields_with_high_risk", 0)
            
            all_alerts.append({
                "alert_id": "alert_risk_001",
                "severity": "critical" if overall_risk_level == "high" else "high",
                "category": "risk_compliance",
                "message": f"Overall risk level: {overall_risk_level.upper()} ({overall_risk_score:.1f}/100)",
                "affected_fields_count": high_risk_count,
                "recommendation": f"Address {high_risk_count} high-risk field(s). Implement encryption, access controls, audit logging."
            })
        
        # Add PII detection alerts
        pii_fields = summary_metrics.get("pii_fields_detected", 0)
        if pii_fields > 0:
            all_alerts.append({
                "alert_id": "alert_pii_001",
                "severity": "critical",
                "category": "pii_detected",
                "message": f"{pii_fields} PII field(s) detected",
                "affected_fields_count": pii_fields,
                "recommendation": f"Implement encryption at rest/transit, restrict access, audit logging, data retention policies."
            })
        
        # Add field risk issues
        for field in risk_data.get("fields", []):
            if field.get("risk_level") in ["high", "medium"]:
                risk_score = field.get("risk_score", 0)
                all_issues.append({
                    "issue_id": f"issue_risk_{field.get('field_id')}",
                    "agent_id": "score-risk",
                    "field_name": field.get("field_name"),
                    "issue_type": "pii_or_sensitive_data",
                    "severity": "critical" if field.get("risk_level") == "high" else "warning",
                    "message": f"{field.get('field_name')} - Risk {risk_score}/100 ({field.get('risk_level').upper()})"
                })
    
    # ==================== READINESS ALERTS & ISSUES ====================
    if readiness_output.get("status") == "success":
        readiness_data = readiness_output.get("data", {})
        assessment = readiness_data.get("readiness_assessment", {})
        readiness_score = assessment.get("overall_score", 0)
        readiness_status = assessment.get("overall_status", "not_ready")
        
        if readiness_status != "ready":
            issues_count = len(readiness_data.get("deductions", []))
            
            all_alerts.append({
                "alert_id": "alert_readiness_001",
                "severity": "critical" if readiness_status == "not_ready" else "high",
                "category": "data_readiness",
                "message": f"Data readiness: {readiness_score:.1f}/100 ({readiness_status.upper().replace('_', ' ')})",
                "affected_fields_count": issues_count,
                "recommendation": f"Fix {issues_count} issue(s) before production use."
            })
        
        # Add deductions as issues
        for deduction in readiness_data.get("deductions", []):
            for field in deduction.get("fields_affected", []):
                all_issues.append({
                    "issue_id": f"issue_readiness_{field}_{deduction.get('deduction_reason')}",
                    "agent_id": "readiness-rater",
                    "field_name": field,
                    "issue_type": deduction.get("deduction_reason"),
                    "severity": deduction.get("severity", "medium"),
                    "message": deduction.get("deduction_reason").replace("_", " ").title()
                })
    
    # ==================== GOVERNANCE ALERTS & ISSUES ====================
    if governance_output.get("status") == "success":
        governance_data = governance_output.get("data", {})
        governance_scores = governance_data.get("governance_scores", {})
        compliance_status = governance_data.get("compliance_status", "non_compliant")
        overall_gov_score = governance_scores.get("overall", 0)
        issues_found = len(governance_data.get("governance_issues", []))
        
        if compliance_status != "compliant":
            all_alerts.append({
                "alert_id": "alert_governance_001",
                "severity": "critical" if compliance_status == "non_compliant" else "high",
                "category": "governance_compliance",
                "message": f"Governance compliance: {overall_gov_score:.1f}/100 ({compliance_status.upper().replace('_', ' ')})",
                "affected_fields_count": issues_found,
                "recommendation": f"Address {issues_found} governance issue(s) to meet compliance requirements."
            })
        
        # Add governance issues
        for issue in governance_data.get("governance_issues", []):
            all_issues.append({
                "issue_id": f"issue_governance_{issue.get('type')}_{issue.get('field', 'general')}",
                "agent_id": "governance-checker",
                "field_name": issue.get("field", "N/A"),
                "issue_type": issue.get("type", "governance_issue"),
                "severity": issue.get("severity", "medium"),
                "message": issue.get("message", "Governance issue detected")
            })
    
    # ==================== TEST COVERAGE ALERTS & ISSUES ====================
    if test_output.get("status") == "success":
        test_coverage_data = test_output.get("data", {})
        test_scores = test_coverage_data.get("test_coverage_scores", {})
        coverage_status = test_coverage_data.get("coverage_status", "needs_improvement")
        overall_test_score = test_scores.get("overall", 0)
        issues_found = len(test_coverage_data.get("test_coverage_issues", []))
        
        if coverage_status != "excellent":
            all_alerts.append({
                "alert_id": "alert_test_coverage_001",
                "severity": "high" if coverage_status == "needs_improvement" else "medium",
                "category": "test_coverage",
                "message": f"Test coverage: {overall_test_score:.1f}/100 ({coverage_status.upper().replace('_', ' ')})",
                "affected_fields_count": issues_found,
                "recommendation": f"Improve test coverage. {issues_found} test(s) failing or missing."
            })
    
    # ==================== GENERATE RECOMMENDATIONS ====================
    
    # Quality recommendations
    if profiler_output.get("status") == "success":
        for field in profiler_output.get("data", {}).get("fields", [])[:5]:
            if field.get("quality_score", 0) < 80:
                all_recommendations.append({
                    "recommendation_id": f"rec_quality_{field.get('field_id')}",
                    "agent_id": "unified-profiler",
                    "field_name": field.get("field_name"),
                    "priority": "high" if field.get("quality_score", 0) < 60 else "medium",
                    "recommendation": f"Improve data quality for {field.get('field_name')}",
                    "timeline": "1-2 weeks"
                })
    
    # Drift recommendations
    if drift_output.get("status") == "success" and drift_output.get("data", {}).get("drift_summary", {}).get("dataset_stability") == "warning":
        drifted_fields = [f for f in drift_output.get("data", {}).get("fields", []) if f.get("drift_analysis", {}).get("drift_detected", False)]
        all_recommendations.append({
            "recommendation_id": "rec_drift_001",
            "agent_id": "drift-detector",
            "field_name": f"{len(drifted_fields)} fields",
            "priority": "high",
            "recommendation": f"Retrain ML models. {len(drifted_fields)} field(s) show significant distribution drift.",
            "timeline": "1 week"
        })
    
    # Risk recommendations
    if risk_output.get("status") == "success":
        high_risk_fields = [f for f in risk_output.get("data", {}).get("fields", []) if f.get("risk_level") == "high"][:3]
        for field in high_risk_fields:
            all_recommendations.append({
                "recommendation_id": f"rec_risk_{field.get('field_id')}",
                "agent_id": "score-risk",
                "field_name": field.get("field_name"),
                "priority": "critical",
                "recommendation": f"Implement security measures for {field.get('field_name')} - High risk detected",
                "timeline": "immediate"
            })
    
    # ==================== GENERATE EXECUTIVE SUMMARY ====================
    
    if profiler_output.get("status") == "success":
        quality_score = profiler_output.get("data", {}).get("quality_summary", {}).get("overall_quality_score", 0)
        grade = "A" if quality_score >= 90 else "B" if quality_score >= 80 else "C" if quality_score >= 70 else "D" if quality_score >= 60 else "F"
        
        executive_summary.append({
            "summary_id": "exec_quality",
            "title": "Overall Data Quality Score",
            "value": str(round(quality_score, 1)),
            "status": "excellent" if quality_score >= 90 else "good" if quality_score >= 80 else "fair",
            "description": f"Grade {grade}: {quality_score:.1f}/100"
        })
    
    if readiness_output.get("status") == "success":
        readiness_score = readiness_output.get("data", {}).get("readiness_assessment", {}).get("overall_score", 0)
        readiness_status = readiness_output.get("data", {}).get("readiness_assessment", {}).get("overall_status", "not_ready")
        
        executive_summary.append({
            "summary_id": "exec_readiness",
            "title": "Data Readiness Status",
            "value": str(round(readiness_score, 1)),
            "status": "ready" if readiness_status == "ready" else "needs_review" if readiness_status == "needs_review" else "not_ready",
            "description": f"{readiness_score:.1f}/100 - {'Production ready' if readiness_status == 'ready' else 'Needs improvement'}"
        })
    
    if governance_output.get("status") == "success":
        governance_scores = governance_output.get("data", {}).get("governance_scores", {})
        overall_gov_score = governance_scores.get("overall", 0)
        compliance_status = governance_output.get("data", {}).get("compliance_status", "non_compliant")
        
        executive_summary.append({
            "summary_id": "exec_governance",
            "title": "Governance Compliance",
            "value": str(round(overall_gov_score, 1)),
            "status": "compliant" if compliance_status == "compliant" else "needs_review" if compliance_status == "needs_review" else "non_compliant",
            "description": f"{overall_gov_score:.1f}/100 - {compliance_status.upper().replace('_', ' ')}"
        })
    
    if risk_output.get("status") == "success":
        risk_summary = risk_output.get("data", {}).get("risk_summary", {})
        risk_score = risk_summary.get("overall_risk_score", 0)
        
        executive_summary.append({
            "summary_id": "exec_risk",
            "title": "Risk Level",
            "value": str(round(risk_score, 1)),
            "status": "high" if risk_score >= 70 else "medium" if risk_score >= 40 else "low",
            "description": f"{risk_score:.1f}/100 - {risk_summary.get('overall_risk_level', 'unknown').upper()}"
        })
    
    # ==================== GENERATE AI ANALYSIS SUMMARY ====================
    analysis_text_parts = ["EXECUTIVE SUMMARY:"]
    for item in executive_summary:
        analysis_text_parts.append(f"- {item.get('title', '')}: {item.get('description', '')}")
    
    if all_alerts:
        analysis_text_parts.append(f"\nCRITICAL ALERTS ({len(all_alerts)} total):")
        for alert in all_alerts[:3]:
            analysis_text_parts.append(f"- {alert.get('severity', '').upper()}: {alert.get('message', '')}")
    
    complete_analysis_text = "\n".join(analysis_text_parts)
    
    # Generate summary using AI
    # analysis_summary = {
    #     "status": "pending",
    #     "summary": "",
    #     "execution_time_ms": 0,
    #     "model_used": None
    # }
    
    # try:
    #     ai_generator = AnalysisSummaryAI()
    #     summary_result = ai_generator.generate_summary(
    #         analysis_text=complete_analysis_text,
    #         dataset_name="Data Profile Analysis"
    #     )
    #     analysis_summary = summary_result
    # except Exception as e:
    #     print(f"Warning: OpenAI summary generation failed: {str(e)}. Using fallback summary.")
    #     analysis_summary = {
    #         "status": "success",
    #         "summary": f"Data profile analysis completed. {len(all_alerts)} alerts detected, {len(all_issues)} issues identified. " +
    #                   f"Quality score: {profiler_output.get('data', {}).get('quality_summary', {}).get('overall_quality_score', 0):.1f}/100.",
    #         "execution_time_ms": 0,
    #         "model_used": "fallback-rule-based"
    #     }
    
    # ==================== GENERATE ROUTING RECOMMENDATIONS ====================
    # routing_decisions = []
    # try:
    #     from ai.routing_decision_ai import RoutingDecisionAI
    #     routing_ai = RoutingDecisionAI()
    #     routing_decisions = routing_ai.get_routing_decisions(
    #         current_tool="profile-my-data",
    #         agent_results=agent_results,
    #         primary_filename="data.csv",
    #         baseline_filename=None,
    #         current_parameters=None
    #     )
    #     print(f"Generated {len(routing_decisions)} routing recommendations")
    # except Exception as e:
    #     print(f"Warning: Routing AI agent failed: {str(e)}")
    
    # ==================== GENERATE DOWNLOADS ====================
    # Use dedicated download module for comprehensive Excel and JSON exports
    downloader = ProfileMyDataDownloads()
    downloads = downloader.generate_downloads(
        agent_results=agent_results,
        analysis_id=analysis_id,
        execution_time_ms=execution_time_ms,
        alerts=all_alerts,
        issues=all_issues,
        recommendations=all_recommendations,
        executive_summary=executive_summary
    )
    
    # ==================== BUILD FINAL RESPONSE ====================
    
    return {
        "status": "success" if all(r.get("status") == "success" for r in agent_results.values() if r.get("status")) else "partial",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "execution_time_ms": execution_time_ms,
        "report": {
            "alerts": all_alerts,
            "issues": all_issues,
            "recommendations": all_recommendations,
            "executiveSummary": executive_summary,
            # "analysisSummary": analysis_summary,
            "visualizations": [],
            # "routing_decisions": routing_decisions,
            # Individual agent outputs (for detailed inspection)
            **{agent_id: output for agent_id, output in agent_results.items() if output.get("status") == "success"},
            # Downloads with Excel and JSON exports
            "downloads": downloads
        }
    }
