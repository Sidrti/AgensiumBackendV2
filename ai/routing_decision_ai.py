"""
Routing Decision AI Agent - Intelligent Tool Recommendation Engine (OpenRouter Version)

Purpose:
    Takes analysis results from one tool and intelligently recommends the next best tool
    the user should run to get maximum value from their data.

Logic:
    1. Analyzes current tool's findings (quality issues, data characteristics, scores)
    2. Evaluates all available tools based on findings
    3. Uses OpenRouter AI to determine which tool would be most beneficial next
    4. Returns routing decision with tool path, required files, and parameters

Current Tools (4 Total):
    - profile-my-data: Data profiling, quality assessment, drift detection, risk scoring, readiness rating
    - clean-my-data: Null handling, outlier removal, type fixing, governance validation, test coverage
    - master-my-data: Master data management, key identification, golden records, survivorship, stewardship
    - analyze-my-data: Business analytics, customer segmentation, market basket analysis, experimental design
"""

import os
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False


class RoutingDecisionAI:
    """Intelligent AI agent for tool routing and recommendations using OpenRouter"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "xiaomi/mimo-v2-flash:free",
        site_url: Optional[str] = None,
        site_name: Optional[str] = None,
    ):
        """
        Initialize routing AI agent with OpenRouter configuration.
        
        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            model: Model name to use (default: xiaomi/mimo-v2-flash:free)
            site_url: Your site URL for OpenRouter rankings (optional)
            site_name: Your site name for OpenRouter rankings (optional)
        """
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
                "description": "Data cleaning and validation - null handling, outlier removal, type fixing, duplicate resolution, field standardization",
                "agents": ["cleanse-previewer", "quarantine-agent", "type-fixer", "field-standardization", "duplicate-resolver", "null-handler", "outlier-remover", "cleanse-writeback"],
                "requires_files": ["primary"],
                "optional_files": [],
                "use_cases": [
                    "Remove null/missing values",
                    "Detect and handle outliers",
                    "Fix data type inconsistencies",
                    "Detect and resolve duplicate records",
                    "Standardize field values and formats",
                    "Improve data quality scores",
                    "Prepare data for analytics/ML"
                ]
            },
            "master-my-data": {
                "name": "Master My Data",
                "description": "Master data management - key identification, contract enforcement, semantic mapping, golden records, survivorship resolution",
                "agents": ["key-identifier", "contract-enforcer", "semantic-mapper", "survivorship-resolver", "golden-record-builder", "stewardship-flagger"],
                "requires_files": ["primary"],
                "optional_files": ["schema"],
                "use_cases": [
                    "Identify primary and foreign keys",
                    "Enforce data contracts",
                    "Map semantics across sources",
                    "Resolve conflicting records",
                    "Build golden records (single source of truth)",
                    "Flag data stewardship tasks"
                ]
            },
            "analyze-my-data": {
                "name": "Analyze My Data",
                "description": "Business analytics - customer segmentation (RFM), market basket analysis, sequence mining, experimental design",
                "agents": ["customer-segmentation-agent", "market-basket-sequence-agent", "experimental-design-agent"],
                "requires_files": ["primary"],
                "optional_files": [],
                "use_cases": [
                    "Segment customers by RFM or value",
                    "Discover product affinity patterns",
                    "Find purchase sequences",
                    "Calculate A/B test sample sizes",
                    "Design experiments",
                    "Behavioral cohort analysis"
                ]
            }
        }
        
        # Configure OpenRouter API
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.site_url = site_url or os.getenv("OPENROUTER_SITE_URL", "https://agensium.app")
        self.site_name = site_name or os.getenv("OPENROUTER_SITE_NAME", "Agensium")
        self.openai_client = None
        self.use_ai = False
        
        if not self.api_key:
            print("Warning: OPENROUTER_API_KEY not set - AI-based routing will use fallback recommendations")
        elif not OPENAI_AVAILABLE:
            print("Warning: OpenAI package not installed. To enable AI routing, install 'openai' and set OPENROUTER_API_KEY.")
        else:
            try:
                self.openai_client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.api_key,
                )
                self.use_ai = True
                print(f"Info: OpenRouter client initialized successfully for routing decisions with model: {self.model}")
            except Exception as e:
                print(f"Warning: Failed to initialize OpenRouter client: {str(e)}. Using fallback routing.")
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
            List of routing decisions with tool recommendations
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
            if agent_results.get("unified-profiler", {}).get("status") == "success":
                profiler_data = agent_results["unified-profiler"].get("data", {})
                quality_score = profiler_data.get("quality_summary", {}).get("overall_quality_score", 0)
                analysis["scores"]["quality"] = quality_score

                if quality_score < 70:
                    analysis["data_quality_issues"].append(f"Low quality score: {quality_score:.1f}%")
                    analysis["key_findings"].append("Data quality needs improvement")

            if agent_results.get("drift-detector", {}).get("status") == "success":
                drift_data = agent_results["drift-detector"].get("data", {})
                drift_pct = drift_data.get("drift_summary", {}).get("drift_percentage", 0)
                analysis["scores"]["drift"] = drift_pct

                if drift_pct > 20:
                    analysis["data_quality_issues"].append(f"High drift detected: {drift_pct:.1f}%")

            if agent_results.get("score-risk", {}).get("status") == "success":
                risk_data = agent_results["score-risk"].get("data", {})
                risk_score = risk_data.get("risk_summary", {}).get("overall_risk_score", 0)
                analysis["scores"]["risk"] = risk_score

                if risk_score > 70:
                    analysis["risk_factors"].append(f"High risk score: {risk_score:.1f}%")

        # ==================== CLEAN-MY-DATA ANALYSIS ====================
        elif current_tool == "clean-my-data":
            if agent_results.get("cleanse-writeback", {}).get("status") == "success":
                writeback_data = agent_results["cleanse-writeback"].get("data", {})
                quality_score = writeback_data.get("quality_assessment", {}).get("overall_score", 0)
                analysis["scores"]["post_cleaning_quality"] = quality_score
                analysis["key_findings"].append(f"Post-cleaning quality: {quality_score:.1f}%")

            if agent_results.get("null-handler", {}).get("status") == "success":
                null_data = agent_results["null-handler"].get("data", {})
                null_reduction = null_data.get("cleaning_score", {}).get("metrics", {}).get("null_reduction_rate", 0)
                if null_reduction > 0:
                    analysis["key_findings"].append(f"Reduced nulls by {null_reduction*100:.1f}%")

        # ==================== MASTER-MY-DATA ANALYSIS ====================
        elif current_tool == "master-my-data":
            if agent_results.get("key-identifier", {}).get("status") == "success":
                key_data = agent_results["key-identifier"].get("data", {})
                pk_count = len(key_data.get("candidate_primary_keys", []))
                analysis["key_findings"].append(f"Identified {pk_count} primary key candidates")

            if agent_results.get("golden-record-builder", {}).get("status") == "success":
                golden_data = agent_results["golden-record-builder"].get("data", {})
                compression_ratio = golden_data.get("compression_metrics", {}).get("compression_ratio", 0)
                if compression_ratio > 1:
                    analysis["key_findings"].append(f"Golden records created with {compression_ratio:.1f}x compression")

        # ==================== ANALYZE-MY-DATA ANALYSIS ====================
        elif current_tool == "analyze-my-data":
            if agent_results.get("customer-segmentation-agent", {}).get("status") == "success":
                seg_data = agent_results["customer-segmentation-agent"].get("data", {})
                segments = len(seg_data.get("segment_summary", []))
                analysis["key_findings"].append(f"Created {segments} customer segments")

            if agent_results.get("market-basket-sequence-agent", {}).get("status") == "success":
                basket_data = agent_results["market-basket-sequence-agent"].get("data", {})
                rules_count = len(basket_data.get("association_rules", []))
                analysis["key_findings"].append(f"Discovered {rules_count} product affinity rules")

        return analysis

    def _get_ai_recommendations(
        self,
        current_tool: str,
        analysis: Dict[str, Any],
        agent_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Use OpenRouter LLM to generate intelligent routing recommendations"""

        if not self.use_ai or not self.openai_client:
            print("Info: OpenRouter not configured - using rule-based fallback recommendations")
            return self._get_fallback_recommendations(current_tool, analysis)
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                prompt = self._build_routing_prompt(current_tool, analysis, agent_results)
                
                response = self.openai_client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": self.site_url,
                        "X-Title": self.site_name,
                    },
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a data workflow expert. Recommend the best next tool based on analysis results. Return only valid JSON."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=800,
                )
                
                content = response.choices[0].message.content.strip()
                
                # Try to parse JSON
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                recommendations = json.loads(content)
                
                # Validate structure
                if isinstance(recommendations, list) and len(recommendations) > 0:
                    return recommendations[:2]  # Return top 2
                
                retry_count += 1
                print(f"Warning: Invalid recommendation format, retry {retry_count}/{max_retries}")
                
            except json.JSONDecodeError as e:
                retry_count += 1
                print(f"Warning: Failed to parse AI recommendations (retry {retry_count}/{max_retries}): {str(e)}")
            except Exception as e:
                retry_count += 1
                print(f"Warning: OpenRouter API call failed (retry {retry_count}/{max_retries}): {str(e)}")
        
        # Fallback after retries
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
                available_options.append(f"- {tool_id}: {tool_info['description']}")

        prompt = f"""
You are analyzing data from a {current_tool_name} analysis. Based on the findings below, recommend the BEST 1-2 next tools the user should run to maximize value and improve their data.

CURRENT ANALYSIS FINDINGS:
- Current Tool: {current_tool}
- Overall success rate: {analysis['success_rate']*100:.0f}%
- Key findings: {', '.join(analysis['key_findings']) if analysis['key_findings'] else 'None'}
- Data quality issues: {', '.join(analysis['data_quality_issues']) if analysis['data_quality_issues'] else 'None'}
- Risk factors: {', '.join(analysis['risk_factors']) if analysis['risk_factors'] else 'None'}
- Scores: {json.dumps(analysis['scores'], indent=2)}

AVAILABLE TOOLS:
{chr(10).join(available_options)}

TOOL DETAILS & USE CASES:
1. Profile My Data: First-time exploration, quality baseline, drift detection, risk assessment, readiness evaluation
2. Clean My Data: Remove nulls, handle outliers, fix types, resolve duplicates, standardize fields, improve quality
3. Master My Data: Identify keys, enforce contracts, map semantics, resolve conflicts, build golden records, manage stewardship
4. Analyze My Data: Customer segmentation (RFM), market basket analysis, sequence mining, A/B test design

ROUTING LOGIC:
- After profile: If quality < 70 → clean; If risk high → clean or master; If quality good → analyze
- After clean: → profile (verify improvements) OR master (establish MDM) OR analyze (business insights)
- After master: → analyze (segment golden records) OR profile (assess master data quality)
- After analyze: → profile (understand data better) OR clean (improve before re-analysis)

Return a JSON array with 1-2 recommendations in this EXACT format:
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

IMPORTANT: Return ONLY valid JSON array, no markdown, no other text.
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
            quality_score = analysis["scores"].get("quality", 100)
            if quality_score < 70:
                recommendations.append({
                    "next_tool": "clean-my-data",
                    "confidence_score": 0.95,
                    "reason": "Low quality score detected. Clean data to improve quality metrics.",
                    "priority": 1,
                    "expected_benefits": [
                        "Remove null values",
                        "Handle outliers",
                        "Fix type inconsistencies",
                        "Improve overall quality score"
                    ],
                    "estimated_time_minutes": 8
                })
            else:
                recommendations.append({
                    "next_tool": "analyze-my-data",
                    "confidence_score": 0.85,
                    "reason": "Data quality is good. Ready for business analytics and segmentation.",
                    "priority": 1,
                    "expected_benefits": [
                        "Customer segmentation",
                        "Product affinity analysis",
                        "Behavioral insights"
                    ],
                    "estimated_time_minutes": 6
                })

        elif current_tool == "clean-my-data":
            recommendations.append({
                "next_tool": "profile-my-data",
                "confidence_score": 0.95,
                "reason": "Verify data quality improvements and assess readiness after cleaning.",
                "priority": 1,
                "expected_benefits": [
                    "Verify quality score improvements",
                    "Re-assess data readiness",
                    "Validate cleaning operations"
                ],
                "estimated_time_minutes": 7
            })
            recommendations.append({
                "next_tool": "master-my-data",
                "confidence_score": 0.80,
                "reason": "Establish master data management on cleaned data.",
                "priority": 2,
                "expected_benefits": [
                    "Create golden records",
                    "Resolve conflicts",
                    "Single source of truth"
                ],
                "estimated_time_minutes": 10
            })

        elif current_tool == "master-my-data":
            recommendations.append({
                "next_tool": "analyze-my-data",
                "confidence_score": 0.90,
                "reason": "Golden records ready. Perform business analytics on master data.",
                "priority": 1,
                "expected_benefits": [
                    "Segment golden records",
                    "Discover patterns",
                    "Generate insights"
                ],
                "estimated_time_minutes": 6
            })

        elif current_tool == "analyze-my-data":
            recommendations.append({
                "next_tool": "profile-my-data",
                "confidence_score": 0.75,
                "reason": "Profile data to understand quality and characteristics for better analysis.",
                "priority": 1,
                "expected_benefits": [
                    "Understand data quality",
                    "Identify issues",
                    "Improve future analyses"
                ],
                "estimated_time_minutes": 7
            })

        return recommendations if recommendations else [{
            "next_tool": "profile-my-data",
            "confidence_score": 0.70,
            "reason": "Start with data profiling to understand your data.",
            "priority": 1,
            "expected_benefits": ["Comprehensive data understanding"],
            "estimated_time_minutes": 7
        }]

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
            
            # Skip if the recommended tool is the same as current
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
                "path": f"/results/{next_tool}",
                "required_files": {
                    "primary": {
                        "name": base_filename,
                        "available": True
                    }
                },
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

            # Add baseline file if applicable
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
        # Return all agents for the tool
        return self.available_tools[next_tool]["agents"]

    def _build_agent_parameters(
        self,
        tool: str,
        recommendation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build agent-specific parameters based on recommendation"""
        # Return empty - agents use defaults
        return {}
