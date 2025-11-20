"""
Routing Decision AI Agent - Intelligent Tool Recommendation Engine

Purpose:
    Takes analysis results from one tool and intelligently recommends the next best tool
    the user should run to get maximum value from their data.

Logic:
    1. Analyzes current tool's findings (quality issues, data characteristics, scores)
    2. Evaluates all available tools based on findings
    3. Uses AI to determine which tool would be most beneficial next
    4. Returns routing decision with tool path, required files, and parameters

Current Tools:
    - profile-my-data: Data profiling, quality assessment, drift detection, risk scoring, readiness rating
    - clean-my-data: Null handling, outlier removal, type fixing, governance validation, test coverage
"""

import json
import time
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False


class RoutingDecisionAI:
    """Intelligent AI agent for tool routing and recommendations"""

    def __init__(
            self, 
            api_key: Optional[str] = None,
                 ):
        """Initialize routing AI agent and configure OpenAI API key from environment or provided key"""
        self.available_tools = {
            "profile-my-data": {
                "name": "Profile My Data",
                "description": "Comprehensive data profiling, quality assessment, drift detection, risk scoring, and readiness evaluation",
                "agents": ["unified-profiler", "drift-detector", "score-risk", "readiness-rater", "governance-checker", "test-coverage-agent"],
                "requires_files": ["primary"],
                "optional_files": ["baseline"],
                "use_cases": [
                    "First-time data exploration",
                    "Data quality baseline establishment",
                    "Compare datasets for drift",
                    "Risk assessment before processing",
                    "Data readiness evaluation",
                    "Governance compliance check"
                ]
            },
            "clean-my-data": {
                "name": "Clean My Data",
                "description": "Data cleaning and validation - null handling, outlier removal, type fixing, duplicate resolution, governance validation, test coverage",
                "agents": ["cleanse-previewer", "quarantine-agent", "type-fixer", "field-standardization", "duplicate-resolver", "null-handler", "outlier-remover", "governance-checker", "test-coverage-agent", "cleanse-writeback"],
                "requires_files": ["primary"],
                "optional_files": [],
                "use_cases": [
                    "Remove null/missing values",
                    "Detect and handle outliers",
                    "Fix data type inconsistencies",
                    "Detect and resolve duplicate records",
                    "Validate data governance rules",
                    "Assess test coverage requirements",
                    "Improve data quality scores",
                    "Prepare data for ML/analytics"
                ]
            }
        }
        # Configure OpenAI API key from provided value or environment variable
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.openai_client = None
        self.use_ai = False
        
        if not self.api_key:
            print("Warning: OPENAI_API_KEY not set - AI-based routing will use fallback recommendations")
        elif not OPENAI_AVAILABLE:
            print("Warning: OpenAI package not installed. To enable AI routing, install 'openai' and set OPENAI_API_KEY.")
        else:
            try:
                self.openai_client = OpenAI(api_key=self.api_key)
                self.use_ai = True
                print("Info: OpenAI client initialized successfully for routing decisions.")
            except Exception as e:
                print(f"Warning: Failed to initialize OpenAI client: {str(e)}. Using fallback routing.")
                self.openai_client = None
                self.use_ai = False

    def get_routing_decisions(
        self,
        current_tool: str,
        agent_results: Dict[str, Any],
        primary_filename: Optional[str] = None,
        baseline_filename: Optional[str] = None,
        current_parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze current tool results and generate routing recommendations.

        Args:
            current_tool: Current tool identifier (e.g., "profile-my-data")
            agent_results: Results from current tool's agents
            primary_filename: Name of primary file
            baseline_filename: Name of baseline file (if applicable)
            current_parameters: Current tool's parameters

        Returns:
            List of routing decisions, each containing:
            {
                "recommendation_id": str,
                "next_tool": str,
                "confidence_score": float (0-1),
                "reason": str,
                "priority": int,
                "path": str (e.g., "/results/clean-my-data"),
                "required_files": {
                    "primary": {"name": str, "available": bool},
                    "baseline": {"name": str, "available": bool} (optional)
                },
                "parameters": {
                    "selected_agents": List[str],
                    "agent_parameters": Dict[str, Any]
                },
                "expected_benefits": List[str],
                "estimated_time_minutes": int,
                "execution_steps": List[str]
            }
        """
        try:
            # Analyze current results
            analysis = self._analyze_current_results(
                current_tool,
                agent_results,
                primary_filename,
                baseline_filename
            )

            # Get AI-based recommendations
            recommendations = self._get_ai_recommendations(
                current_tool,
                analysis,
                agent_results
            )

            # Format routing decisions with paths and parameters
            routing_decisions = self._format_routing_decisions(
                current_tool,
                recommendations,
                primary_filename,
                baseline_filename,
                current_parameters
            )

            return routing_decisions

        except Exception as e:
            print(f"Error generating routing decisions: {str(e)}")
            return []

    def _analyze_current_results(
        self,
        current_tool: str,
        agent_results: Dict[str, Any],
        primary_filename: Optional[str],
        baseline_filename: Optional[str]
    ) -> Dict[str, Any]:
        """Analyze current tool results to extract key findings"""

        analysis = {
            "current_tool": current_tool,
            "success_rate": 0,
            "key_findings": [],
            "data_quality_issues": [],
            "risk_factors": [],
            "scores": {},
            "files_available": {
                "primary": primary_filename is not None,
                "baseline": baseline_filename is not None
            }
        }

        # Count successful agents
        successful_agents = sum(1 for r in agent_results.values() if r.get("status") == "success")
        total_agents = len([r for r in agent_results.values() if isinstance(r, dict) and "status" in r])
        analysis["success_rate"] = successful_agents / total_agents if total_agents > 0 else 0

        # ==================== PROFILE-MY-DATA ANALYSIS ====================
        if current_tool == "profile-my-data":
            # Profiler findings
            if agent_results.get("unified-profiler", {}).get("status") == "success":
                profiler_data = agent_results["unified-profiler"].get("data", {})
                quality_score = profiler_data.get("quality_summary", {}).get("overall_quality_score", 0)
                analysis["scores"]["quality"] = quality_score

                if quality_score < 70:
                    analysis["key_findings"].append(f"Low data quality score ({quality_score:.1f}/100)")
                    analysis["data_quality_issues"].append("poor_overall_quality")

            # Drift findings
            if agent_results.get("drift-detector", {}).get("status") == "success":
                drift_data = agent_results["drift-detector"].get("data", {})
                drift_pct = drift_data.get("drift_summary", {}).get("drift_percentage", 0)
                analysis["scores"]["drift"] = drift_pct

                if drift_pct > 20:
                    analysis["key_findings"].append(f"Significant drift detected ({drift_pct:.1f}%)")
                    analysis["risk_factors"].append("dataset_drift")

            # Risk findings
            if agent_results.get("score-risk", {}).get("status") == "success":
                risk_data = agent_results["score-risk"].get("data", {})
                risk_score = risk_data.get("risk_summary", {}).get("overall_risk_score", 0)
                analysis["scores"]["risk"] = risk_score

                if risk_score > 70:
                    analysis["key_findings"].append(f"High risk score ({risk_score:.1f}/100)")
                    analysis["risk_factors"].append("high_risk_data")

            # Readiness findings
            if agent_results.get("readiness-rater", {}).get("status") == "success":
                readiness_data = agent_results["readiness-rater"].get("data", {})
                readiness_score = readiness_data.get("readiness_assessment", {}).get("overall_score", 0)
                readiness_status = readiness_data.get("readiness_assessment", {}).get("overall_status", "unknown")
                analysis["scores"]["readiness"] = readiness_score

                if readiness_score < 60 or readiness_status == "not_ready":
                    analysis["key_findings"].append(f"Data not ready for production ({readiness_status})")
                    analysis["data_quality_issues"].append("readiness_concerns")

            # Governance findings
            if agent_results.get("governance-checker", {}).get("status") == "success":
                gov_data = agent_results["governance-checker"].get("data", {})
                compliance_status = gov_data.get("compliance_status", "unknown")

                if compliance_status in ["non_compliant", "needs_review"]:
                    analysis["key_findings"].append(f"Governance issues detected ({compliance_status})")
                    analysis["risk_factors"].append("governance_non_compliance")

        # ==================== CLEAN-MY-DATA ANALYSIS ====================
        elif current_tool == "clean-my-data":
            # Cleanse previewer findings
            if agent_results.get("cleanse-previewer", {}).get("status") == "success":
                preview_metrics = agent_results["cleanse-previewer"].get("summary_metrics", {})
                total_warnings = preview_metrics.get("total_warnings", 0)
                if total_warnings > 0:
                    analysis["key_findings"].append(f"Preview identified {total_warnings} potential issues")

            # Quarantine agent findings
            if agent_results.get("quarantine-agent", {}).get("status") == "success":
                quarantine_metrics = agent_results["quarantine-agent"].get("summary_metrics", {})
                issues_found = quarantine_metrics.get("quarantine_issues_found", 0)
                if issues_found > 0:
                    analysis["key_findings"].append(f"Quarantined {issues_found} invalid records")
                    analysis["data_quality_issues"].append("invalid_records_quarantined")

            # Type fixer findings
            if agent_results.get("type-fixer", {}).get("status") == "success":
                type_data = agent_results["type-fixer"].get("data", {})
                fixing_score = type_data.get("fixing_score", {}).get("overall_score", 0)
                type_issues_fixed = agent_results["type-fixer"].get("summary_metrics", {}).get("type_issues_fixed", 0)
                analysis["scores"]["type_fixing"] = fixing_score

                if type_issues_fixed > 0:
                    analysis["key_findings"].append(f"Type issues fixed: {type_issues_fixed}")
                    
                if fixing_score < 80:
                    analysis["data_quality_issues"].append("type_mismatch_concerns")

            # Field standardization findings
            if agent_results.get("field-standardization", {}).get("status") == "success":
                std_metrics = agent_results["field-standardization"].get("summary_metrics", {})
                total_issues = std_metrics.get("total_issues", 0)
                if total_issues > 0:
                    analysis["key_findings"].append(f"Standardized {total_issues} field values")

            # Duplicate resolver findings
            if agent_results.get("duplicate-resolver", {}).get("status") == "success":
                dup_metrics = agent_results["duplicate-resolver"].get("summary_metrics", {})
                total_issues = dup_metrics.get("total_issues", 0)
                if total_issues > 0:
                    analysis["key_findings"].append(f"Resolved {total_issues} duplicate records")

            # Null handler findings
            if agent_results.get("null-handler", {}).get("status") == "success":
                null_data = agent_results["null-handler"].get("data", {})
                cleaning_score = null_data.get("cleaning_score", {}).get("overall_score", 0)
                nulls_handled = agent_results["null-handler"].get("summary_metrics", {}).get("nulls_handled", 0)
                analysis["scores"]["null_handling"] = cleaning_score

                if nulls_handled > 0:
                    analysis["key_findings"].append(f"Null values handled: {nulls_handled}")

            # Outlier remover findings
            if agent_results.get("outlier-remover", {}).get("status") == "success":
                outlier_data = agent_results["outlier-remover"].get("data", {})
                outlier_score = outlier_data.get("outlier_score", {}).get("overall_score", 0)
                outliers_handled = agent_results["outlier-remover"].get("summary_metrics", {}).get("outliers_handled", 0)
                analysis["scores"]["outlier_removal"] = outlier_score

                if outliers_handled > 0:
                    analysis["key_findings"].append(f"Outliers handled: {outliers_handled}")

            # Governance findings
            if agent_results.get("governance-checker", {}).get("status") == "success":
                gov_data = agent_results["governance-checker"].get("data", {})
                compliance_status = gov_data.get("compliance_status", "unknown")

                if compliance_status == "compliant":
                    analysis["key_findings"].append("Data governance compliant")
                else:
                    analysis["data_quality_issues"].append("governance_concerns")

            # Test coverage findings
            if agent_results.get("test-coverage-agent", {}).get("status") == "success":
                test_data = agent_results["test-coverage-agent"].get("data", {})
                coverage_status = test_data.get("coverage_status", "unknown")
                analysis["key_findings"].append(f"Test coverage status: {coverage_status}")

            # Cleanse writeback findings
            if agent_results.get("cleanse-writeback", {}).get("status") == "success":
                analysis["key_findings"].append("Cleaned data successfully written back")

        return analysis

    def _get_ai_recommendations(
        self,
        current_tool: str,
        analysis: Dict[str, Any],
        agent_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Use LLM to generate intelligent routing recommendations with retry logic"""

        # Check if AI is available
        if not self.use_ai or not self.openai_client:
            print("Info: OpenAI not configured - using rule-based fallback recommendations")
            return self._get_fallback_recommendations(current_tool, analysis)
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Build prompt for LLM
                prompt = self._build_routing_prompt(current_tool, analysis, agent_results)

                # Use new OpenAI client interface
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert data analysis advisor. Your role is to recommend the best next tool to use based on current analysis results. Return a JSON array of recommendations."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    max_tokens=800,
                )

                # Parse response
                response_text = response.choices[0].message.content.strip()

                # Extract JSON from response
                try:
                    # Try direct JSON parsing
                    recommendations = json.loads(response_text)
                except json.JSONDecodeError:
                    # Try extracting JSON from markdown code blocks
                    if "```json" in response_text:
                        json_str = response_text.split("```json")[1].split("```")[0].strip()
                        recommendations = json.loads(json_str)
                    elif "```" in response_text:
                        json_str = response_text.split("```")[1].split("```")[0].strip()
                        recommendations = json.loads(json_str)
                    else:
                        raise ValueError("Could not parse JSON from response")

                # Ensure it's a list
                if not isinstance(recommendations, list):
                    recommendations = [recommendations]

                # Validate recommendations structure
                validated_recommendations = []
                for rec in recommendations:
                    if isinstance(rec, dict) and "next_tool" in rec:
                        validated_recommendations.append(rec)
                
                return validated_recommendations if validated_recommendations else self._get_fallback_recommendations(current_tool, analysis)
                
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"Error getting AI recommendations after {max_retries} retries: {str(e)}")
                    # Return rule-based recommendations as fallback
                    return self._get_fallback_recommendations(current_tool, analysis)
                else:
                    # Exponential backoff: wait 1, 2, 4 seconds
                    wait_time = 2 ** (retry_count - 1)
                    print(f"Retry {retry_count}/{max_retries} after {wait_time}s. Error: {str(e)}")
                    time.sleep(wait_time)
        
        # Should never reach here, but return fallback just in case
        return self._get_fallback_recommendations(current_tool, analysis)

    def _build_routing_prompt(
        self,
        current_tool: str,
        analysis: Dict[str, Any],
        agent_results: Dict[str, Any]
    ) -> str:
        """Build prompt for LLM-based routing"""

        current_tool_name = self.available_tools[current_tool]["name"]
        
        # Build available options
        available_options = []
        for tool_id, tool_info in self.available_tools.items():
            if tool_id != current_tool:
                available_options.append(f"- {tool_info['name']} ({tool_id}): {tool_info['description']}")

        prompt = f"""
You are analyzing data from a {current_tool_name} analysis. Based on the findings below, recommend the BEST next tool the user should run to maximize value and improve their data.

CURRENT ANALYSIS FINDINGS:
- Overall success rate: {analysis['success_rate']*100:.0f}%
- Key findings: {', '.join(analysis['key_findings']) if analysis['key_findings'] else 'None'}
- Data quality issues: {', '.join(analysis['data_quality_issues']) if analysis['data_quality_issues'] else 'None'}
- Risk factors: {', '.join(analysis['risk_factors']) if analysis['risk_factors'] else 'None'}
- Scores: {json.dumps(analysis['scores'], indent=2)}

AVAILABLE TOOLS:
{chr(10).join(available_options)}

TOOL DETAILS:
Profile My Data:
  - Use cases: First-time data exploration, quality baseline, drift detection, risk assessment, readiness evaluation, governance check
  - Files needed: Primary (required), Baseline (optional for drift detection)
  - Best when: You need comprehensive data understanding

Clean My Data:
  - Use cases: Remove nulls, handle outliers, fix type issues, validate governance, assess test coverage, improve quality scores, prepare for ML
  - Files needed: Primary (required)
  - Best when: Your data has quality issues (nulls, outliers, type mismatches) that need fixing

RECOMMENDATION GUIDELINES:
1. If current tool is profile-my-data and data quality is poor (<70): Recommend clean-my-data
2. If current tool is clean-my-data and data quality improved: Recommend profile-my-data to verify improvements
3. If high drift detected in profile: Recommend clean-my-data to handle quality issues
4. If type mismatches detected: Recommend clean-my-data with type-fixer agent
5. If governance issues: Recommend profile-my-data governance check or clean-my-data to fix
6. Always prioritize: Type consistency → Quality → Governance → Risk reduction

Return a JSON array with 1-2 recommendations in this exact format:
[
  {{
    "next_tool": "tool-id",
    "confidence_score": 0.95,
    "reason": "Brief explanation why this tool is recommended",
    "priority": 1,
    "expected_benefits": ["benefit1", "benefit2", "benefit3"],
    "estimated_time_minutes": 5
  }}
]

IMPORTANT: Return ONLY valid JSON array, no other text.
"""
        return prompt

    def _get_fallback_recommendations(
        self,
        current_tool: str,
        analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Rule-based fallback recommendations when LLM is unavailable"""

        recommendations = []

        if current_tool == "profile-my-data":
            # If quality score is low, recommend cleaning
            quality_score = analysis["scores"].get("quality", 100)
            if quality_score < 70:
                recommendations.append({
                    "next_tool": "clean-my-data",
                    "confidence_score": 0.9,
                    "reason": f"Data quality score is {quality_score:.1f}/100. Run Clean My Data to improve quality through null handling and outlier removal.",
                    "priority": 1,
                    "expected_benefits": ["Improved data quality", "Removed null values", "Handled outliers", "Better readiness scores"],
                    "estimated_time_minutes": 10
                })

            # If risk is high, recommend cleaning
            risk_score = analysis["scores"].get("risk", 0)
            if risk_score > 70 and quality_score >= 70:
                recommendations.append({
                    "next_tool": "clean-my-data",
                    "confidence_score": 0.8,
                    "reason": f"Risk score is {risk_score:.1f}/100. Clean My Data can help mitigate identified risks.",
                    "priority": 2,
                    "expected_benefits": ["Reduced data risk", "Better data governance compliance", "Improved test coverage"],
                    "estimated_time_minutes": 8
                })

            # If no issues found, still recommend cleaning as next step
            if not recommendations:
                recommendations.append({
                    "next_tool": "clean-my-data",
                    "confidence_score": 0.7,
                    "reason": "Proceed to Clean My Data to handle any data quality issues and prepare for production.",
                    "priority": 1,
                    "expected_benefits": ["Ensure data quality", "Handle nulls and outliers"],
                    "estimated_time_minutes": 5
                })

        elif current_tool == "clean-my-data":
            # After cleaning, recommend profile to verify improvements
            recommendations.append({
                "next_tool": "profile-my-data",
                "confidence_score": 0.95,
                "reason": "Verify data quality improvements and overall data health after cleaning operations.",
                "priority": 1,
                "expected_benefits": [
                    "Verify quality score improvements",
                    "Re-assess data readiness",
                    "Check for new data patterns",
                    "Validate governance compliance",
                    "Risk assessment update"
                ],
                "estimated_time_minutes": 7
            })

        # Return at least one recommendation
        if not recommendations:
            # Recommend the opposite tool
            opposite_tool = "clean-my-data" if current_tool == "profile-my-data" else "profile-my-data"
            recommendations.append({
                "next_tool": opposite_tool,
                "confidence_score": 0.7,
                "reason": "Complementary analysis of your data with the other available tool.",
                "priority": 1,
                "expected_benefits": ["Comprehensive data understanding"],
                "estimated_time_minutes": 5
            })

        return recommendations

    def _format_routing_decisions(
        self,
        current_tool: str,
        recommendations: List[Dict[str, Any]],
        primary_filename: Optional[str],
        baseline_filename: Optional[str],
        current_parameters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Format recommendations into executable routing decisions"""

        routing_decisions = []
        base_filename = primary_filename or "data.csv"

        for idx, rec in enumerate(recommendations, 1):
            next_tool = rec.get("next_tool", "profile-my-data")
            
            # Skip if the recommended tool is the same as the current tool
            if next_tool == current_tool:
                continue
            
            tool_info = self.available_tools.get(next_tool, {})

            # Determine which agents to recommend
            recommended_agents = self._get_recommended_agents(next_tool, rec, current_tool)

            # Build routing decision
            routing_decision = {
                "recommendation_id": f"route_{idx}",
                "next_tool": next_tool,
                "confidence_score": rec.get("confidence_score", 0.7),
                "reason": rec.get("reason", ""),
                "priority": rec.get("priority", idx),
                # Frontend navigation path
                "path": f"/results/{next_tool}",
                # Files that should be provided
                "required_files": {
                    "primary": {
                        "name": base_filename,
                        "available": True
                    }
                },
                # Optional baseline file
                "parameters": {
                    "selected_agents": recommended_agents,
                    "agent_parameters": self._build_agent_parameters(next_tool, rec)
                },
                "expected_benefits": rec.get("expected_benefits", []),
                "estimated_time_minutes": rec.get("estimated_time_minutes", 5),
                "execution_steps": [
                    f"Run {tool_info.get('name')} with selected agents",
                    "Review analysis results",
                    "Export recommendations",
                    f"Estimated time: {rec.get('estimated_time_minutes', 5)} minutes"
                ]
            }

            # Add baseline file if drift is to be checked
            if baseline_filename and next_tool == "profile-my-data" and "drift-detector" in recommended_agents:
                routing_decision["required_files"]["baseline"] = {
                    "name": baseline_filename,
                    "available": True
                }

            routing_decisions.append(routing_decision)

        return routing_decisions

    def _get_recommended_agents(
        self,
        next_tool: str,
        recommendation: Dict[str, Any],
        current_tool: str
    ) -> List[str]:
        """Determine which agents should be run for the next tool"""

        all_agents = self.available_tools[next_tool]["agents"]

        # If coming from profile-my-data to clean-my-data: all cleaning agents
        if current_tool == "profile-my-data" and next_tool == "clean-my-data":
            return all_agents  # Run all: null-handler, outlier-remover, governance-checker, test-coverage-agent

        # If coming from clean-my-data to profile-my-data: all profiling agents
        if current_tool == "clean-my-data" and next_tool == "profile-my-data":
            return all_agents  # Run all: unified-profiler, drift-detector, score-risk, readiness-rater, etc.

        # Default: return all agents
        return all_agents

    def _build_agent_parameters(
        self,
        tool: str,
        recommendation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build agent-specific parameters based on recommendation"""

        # For now, return empty - agents use defaults
        # This can be extended to fine-tune parameters based on findings
        return {}
