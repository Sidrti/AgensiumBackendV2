"""
Routing Decision AI Agent - Intelligent Tool Recommendation Engine (OpenRouter Version)

Purpose:
    Takes analysis results from one tool and intelligently recommends the next best tool
    the user should run to get maximum value from their data.

Logic:
    1. Dynamically loads available tools from the tools folder JSON files
    2. Uses analysisSummary and executiveSummary from transformers (not raw agent_results)
    3. Uses OpenRouter AI to determine which tool would be most beneficial next
    4. Returns routing decision with tool path, required files, and parameters

Architecture:
    - Tools are loaded dynamically from backend/tools/*.json files
    - analysis_summary provides AI-generated text summary of the analysis
    - executive_summary provides structured KPIs and metrics
    - success_rate is still calculated from agent_results for reliability
"""

import os
import json
import glob
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
        model: str = "nvidia/nemotron-3-nano-30b-a3b:free",
        site_url: Optional[str] = None,
        site_name: Optional[str] = None,
    ):
        """
        Initialize routing AI agent with OpenRouter configuration.
        
        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            model: Model name to use (default: nvidia/nemotron-3-nano-30b-a3b:free)
            site_url: Your site URL for OpenRouter rankings (optional)
            site_name: Your site name for OpenRouter rankings (optional)
        """
        # Dynamically load available tools from JSON files
        self.available_tools = self._load_tools_from_json()
        
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

    def _load_tools_from_json(self) -> Dict[str, Dict[str, Any]]:
        """
        Dynamically load all available tools from the tools folder JSON files.
        
        Returns:
            Dictionary of tool_id -> tool info containing name, description, agents, 
            required files, optional files, and use cases.
        """
        available_tools = {}
        
        # Get the tools directory path relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tools_dir = os.path.join(os.path.dirname(current_dir), "tools")
        
        # Find all JSON files in the tools directory
        json_pattern = os.path.join(tools_dir, "*.json")
        json_files = glob.glob(json_pattern)
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    tool_data = json.load(f)
                
                # Extract tool info from JSON structure
                tool_info = tool_data.get("tool", {})
                tool_id = tool_info.get("id")
                
                if not tool_id:
                    continue
                
                # Skip if tool is not available
                if not tool_info.get("isAvailable", True):
                    continue
                
                # Extract file requirements
                files_config = tool_info.get("files", {})
                required_files = []
                optional_files = []
                
                for file_key, file_config in files_config.items():
                    if file_config.get("required", False):
                        required_files.append(file_key)
                    else:
                        optional_files.append(file_key)
                
                # Extract agent list
                agents = tool_info.get("available_agents", [])
                
                # Build use cases from agent descriptions
                use_cases = []
                agents_data = tool_data.get("agents", {})
                for agent_id, agent_info in agents_data.items():
                    features = agent_info.get("features", [])
                    if features:
                        use_cases.extend(features[:2])  # Take up to 2 features per agent
                
                # Limit use cases to avoid too long lists
                use_cases = use_cases[:8]
                
                available_tools[tool_id] = {
                    "name": tool_info.get("name", tool_id),
                    "description": tool_info.get("description", ""),
                    "category": tool_info.get("category", ""),
                    "agents": agents,
                    "requires_files": required_files,
                    "optional_files": optional_files,
                    "use_cases": use_cases
                }
                
            except Exception as e:
                print(f"Warning: Failed to load tool from {json_file}: {str(e)}")
                continue
        
        if not available_tools:
            print("Warning: No tools loaded from JSON files. Check tools directory.")
        else:
            print(f"Info: Loaded {len(available_tools)} tools dynamically: {list(available_tools.keys())}")
        
        return available_tools

    def reload_tools(self) -> None:
        """Reload tools from JSON files (useful if tools are added/modified)."""
        self.available_tools = self._load_tools_from_json()

    def get_routing_decisions(
        self,
        current_tool: str,
        agent_results: Dict[str, Any],
        executive_summary: Optional[List[Dict[str, Any]]] = None,
        analysis_summary: Optional[Dict[str, Any]] = None,
        primary_filename: Optional[str] = None,
        baseline_filename: Optional[str] = None,
        current_parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze current tool results and generate routing recommendations.

        Args:
            current_tool: Current tool identifier (e.g., "profile-my-data")
            agent_results: Results from current tool's agents (used for success_rate calculation)
            executive_summary: Structured summary with KPIs from transformer
            analysis_summary: AI-generated analysis summary from transformer
            primary_filename: Name of primary file
            baseline_filename: Name of baseline file (if applicable)
            current_parameters: Current tool's parameters

        Returns:
            List of routing decisions with tool recommendations
        """
        try:
            # Build analysis context from executive_summary and analysis_summary
            analysis = self._build_analysis_context(
                current_tool=current_tool,
                agent_results=agent_results,
                executive_summary=executive_summary or [],
                analysis_summary=analysis_summary or {},
                primary_filename=primary_filename,
                baseline_filename=baseline_filename
            )

            # Get AI-based recommendations
            recommendations = self._get_ai_recommendations(
                current_tool=current_tool,
                analysis=analysis
            )

            # Format routing decisions with paths and parameters
            routing_decisions = self._format_routing_decisions(
                current_tool=current_tool,
                recommendations=recommendations,
                primary_filename=primary_filename,
                baseline_filename=baseline_filename,
                current_parameters=current_parameters
            )

            return routing_decisions

        except Exception as e:
            print(f"Error generating routing decisions: {str(e)}")
            return []

    def _build_analysis_context(
        self,
        current_tool: str,
        agent_results: Dict[str, Any],
        executive_summary: List[Dict[str, Any]],
        analysis_summary: Dict[str, Any],
        primary_filename: Optional[str],
        baseline_filename: Optional[str]
    ) -> Dict[str, Any]:
        """
        Build analysis context from executive_summary and analysis_summary.
        
        This replaces the old _analyze_current_results method that depended on
        tool-specific agent_results parsing. Now uses the standardized outputs
        from transformers.
        """
        analysis = {
            "current_tool": current_tool,
            "success_rate": 0.0,
            "key_metrics": [],
            "key_findings": [],
            "ai_summary": "",
            "files_available": {
                "primary": primary_filename is not None,
                "baseline": baseline_filename is not None
            }
        }

        # Calculate success rate from agent_results (still needed for reliability assessment)
        successful_agents = sum(1 for r in agent_results.values() if isinstance(r, dict) and r.get("status") == "success")
        total_agents = len([r for r in agent_results.values() if isinstance(r, dict) and "status" in r])
        analysis["success_rate"] = successful_agents / total_agents if total_agents > 0 else 0.0

        # Extract key metrics from executive_summary
        for item in executive_summary:
            if not isinstance(item, dict):
                continue
            
            metric = {
                "id": item.get("summary_id", ""),
                "title": item.get("title", ""),
                "value": item.get("value", ""),
                "status": item.get("status", ""),
                "description": item.get("description", "")
            }
            analysis["key_metrics"].append(metric)
            
            # Extract key findings from metrics with warning/critical/excellent status
            status = item.get("status", "").lower()
            if status in ["warning", "critical", "excellent", "good"]:
                finding = f"{item.get('title', '')}: {item.get('value', '')} ({status})"
                analysis["key_findings"].append(finding)

        # Extract AI summary text
        if isinstance(analysis_summary, dict):
            summary_text = analysis_summary.get("summary", "")
            if summary_text:
                analysis["ai_summary"] = summary_text

        return analysis

    def _get_ai_recommendations(
        self,
        current_tool: str,
        analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Use OpenRouter LLM to generate intelligent routing recommendations"""

        if not self.use_ai or not self.openai_client:
            print("Info: OpenRouter not configured - no routing recommendations will be generated")
            return []
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                prompt = self._build_routing_prompt(current_tool, analysis)
                
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
                    # Ensure recommended tools exist in our available_tools
                    valid_recommendations = []
                    for rec in recommendations:
                        next_tool = rec.get("next_tool", "")
                        if next_tool in self.available_tools and next_tool != current_tool:
                            valid_recommendations.append(rec)
                    
                    if valid_recommendations:
                        return valid_recommendations[:2]  # Return top 2
                
                retry_count += 1
                print(f"Warning: Invalid recommendation format, retry {retry_count}/{max_retries}")
                
            except json.JSONDecodeError as e:
                retry_count += 1
                print(f"Warning: Failed to parse AI recommendations (retry {retry_count}/{max_retries}): {str(e)}")
            except Exception as e:
                retry_count += 1
                print(f"Warning: OpenRouter API call failed (retry {retry_count}/{max_retries}): {str(e)}")
        
        # No recommendations if all retries failed
        print("Warning: Could not generate routing recommendations after retries. Returning empty list.")
        return []

    def _build_routing_prompt(
        self,
        current_tool: str,
        analysis: Dict[str, Any]
    ) -> str:
        """Build prompt for LLM-based routing using analysis context"""

        current_tool_info = self.available_tools.get(current_tool, {})
        current_tool_name = current_tool_info.get("name", current_tool)
        
        # Build available options (exclude current tool)
        available_options = []
        tool_details = []
        for tool_id, tool_info in self.available_tools.items():
            if tool_id != current_tool:
                available_options.append(f"- {tool_id}: {tool_info['description']}")
                use_cases_str = ", ".join(tool_info.get("use_cases", [])[:4])
                tool_details.append(f"  {tool_info['name']}: {use_cases_str}")

        # Format key metrics
        metrics_str = ""
        for metric in analysis.get("key_metrics", [])[:10]:
            metrics_str += f"  - {metric['title']}: {metric['value']} (status: {metric['status']})\n"

        # Format key findings
        findings_str = ", ".join(analysis.get("key_findings", [])[:5]) if analysis.get("key_findings") else "None"
        
        # Get AI summary excerpt
        ai_summary = analysis.get("ai_summary", "")[:500]

        prompt = f"""
You are analyzing data from a {current_tool_name} analysis. Based on the findings below, recommend the BEST 1-2 next tools the user should run to maximize value and improve their data.

CURRENT ANALYSIS SUMMARY:
- Current Tool: {current_tool}
- Success Rate: {analysis['success_rate']*100:.0f}%
- Key Findings: {findings_str}

KEY METRICS:
{metrics_str if metrics_str else "  No metrics available"}

AI ANALYSIS EXCERPT:
{ai_summary if ai_summary else "No AI analysis available"}

AVAILABLE TOOLS:
{chr(10).join(available_options)}

TOOL CAPABILITIES:
{chr(10).join(tool_details)}

ROUTING GUIDELINES:
- Recommend tools that logically follow the current analysis
- Consider the success rate and key findings when making recommendations
- After profiling: recommend cleaning if quality issues found, or analysis if data is clean
- After cleaning: recommend profiling to verify improvements, or analysis for insights
- After mastering: recommend analysis on golden records, or profiling to assess quality
- After analysis: recommend profiling for deeper understanding, or cleaning if issues found

Return a JSON array with 1-2 recommendations in this EXACT format:
[
  {{
    "next_tool": "tool-id",
    "confidence_score": 0.95,
    "reason": "Brief explanation why this tool is recommended based on the analysis findings",
    "priority": 1,
    "expected_benefits": ["benefit1", "benefit2", "benefit3"],
    "estimated_time_minutes": 5
  }}
]

IMPORTANT: Return ONLY valid JSON array, no markdown, no other text.
Only recommend tools that exist in the AVAILABLE TOOLS list above.
"""
        return prompt

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
            next_tool = rec.get("next_tool", "")
            
            # Skip if the recommended tool doesn't exist or is the same as current
            if next_tool not in self.available_tools or next_tool == current_tool:
                continue
            
            tool_info = self.available_tools.get(next_tool, {})

            # Get all agents for the tool
            recommended_agents = tool_info.get("agents", [])

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
                    "agent_parameters": {}
                },
                "expected_benefits": rec.get("expected_benefits", []),
                "estimated_time_minutes": rec.get("estimated_time_minutes", 5),
                "execution_steps": [
                    f"Run {tool_info.get('name', next_tool)} with selected agents",
                    "Review analysis results",
                    "Export recommendations",
                    f"Estimated time: {rec.get('estimated_time_minutes', 5)} minutes"
                ]
            }

            # Add baseline file if applicable (e.g., for drift detection)
            if baseline_filename and "baseline" in tool_info.get("optional_files", []):
                routing_decision["required_files"]["baseline"] = {
                    "name": baseline_filename,
                    "available": True
                }

            routing_decisions.append(routing_decision)

        return routing_decisions
