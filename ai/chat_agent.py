"""
Chat Agent AI - Intelligent Q&A System

Answers user questions about analysis reports using OpenAI's language models.
Maintains conversation context and provides data-driven insights.

Key Features:
- Context-aware question answering based on analysis reports
- Conversation history support for follow-up questions
- Intelligent summarization and data extraction
- Robust error handling with fallback responses
- Cost-optimized token management
"""

import os
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    import openai
    from openai import OpenAI
except ImportError:
    openai = None
    OpenAI = None


class ChatAgent:
    """
    Intelligent chat agent for answering questions about analysis reports.
    Leverages OpenAI's language models for natural conversation.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-5-nano",
    ):
        """
        Initialize the Chat Agent.

        Args:
            api_key: OpenAI API key (defaults to environment variable)
            model: Model name to use (default: gpt-4o-mini - fast and cost-effective)
        """
        # Prefer provided api_key, fall back to environment variable
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model

        if not self.api_key:
            print(
                "Info: OPENAI_API_KEY not set. Chat will use rule-based responses."
            )
            self.client = None
            self.use_ai = False
        else:
            if OpenAI is None:
                print(
                    "Warning: OpenAI package not installed. To enable chat, install 'openai' and set OPENAI_API_KEY."
                )
                self.client = None
                self.use_ai = False
            else:
                self.client = OpenAI(api_key=self.api_key)
                self.use_ai = True

    def answer_question(
        self,
        question: str,
        report: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Answer a user's question about an analysis report.

        Args:
            question: User's question
            report: Analysis report dictionary (full response from /analyze endpoint)
            conversation_history: Previous messages in conversation (optional)
                Format: [{"role": "user"|"assistant", "content": "message"}, ...]

        Returns:
            Dictionary with:
            {
                "status": "success" | "error",
                "answer": "Response to the question",
                "sources": ["field1", "field2"],  # Which fields were used
                "confidence": 0.95,  # Confidence in answer (0-1)
                "execution_time_ms": 1234,
                "model_used": "gpt-4o-mini" | "rule-based"
            }
        """
        start_time = time.time()
        conversation_history = conversation_history or []

        try:
            if not question or not question.strip():
                return {
                    "status": "error",
                    "answer": "No question provided.",
                    "sources": [],
                    "confidence": 0,
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "model_used": None,
                }

            # Build report context
            report_context = self._build_report_context(report)

            if not getattr(self, "use_ai", False) or not self.client:
                # Use rule-based response
                return {
                    "status": "success",
                    "answer": self._get_rule_based_answer(question, report),
                    "sources": self._extract_relevant_fields(question, report),
                    "confidence": 0.6,
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "model_used": "rule-based",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }

            # Use AI-based response
            return self._get_ai_answer(
                question, report_context, conversation_history, start_time
            )

        except Exception as e:
            return {
                "status": "error",
                "answer": f"Failed to process question: {str(e)}",
                "sources": [],
                "confidence": 0,
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "model_used": self.model if self.use_ai else "rule-based",
                "error_details": str(e),
            }

    def _get_ai_answer(
        self,
        question: str,
        report_context: str,
        conversation_history: List[Dict[str, str]],
        start_time: float,
    ) -> Dict[str, Any]:
        """
        Get AI-powered answer using OpenAI API.

        Args:
            question: User's question
            report_context: Formatted report context
            conversation_history: Previous messages
            start_time: Start time for execution timing

        Returns:
            Response dictionary with AI answer
        """
        try:
            # Build system prompt
            system_prompt = """You are 'Agensium Co-Pilot', a world-class AI data analyst assistant.

Your role is to answer questions about data analysis reports with precision and helpfulness.
You support all analysis tools and report types (profiling, cleaning, risk assessment, etc).

CRITICAL RULES:
1. Base answers EXCLUSIVELY on the provided report data
2. Do not make assumptions or infer information not in the report
3. If asked about something not in the report, say: "I cannot find this information in the current analysis report"
4. Be concise, professional, and data-driven
5. Cite relevant metrics/findings when answering
6. If uncertain, express that uncertainty
7. Help users understand what the data means and what actions to take
8. Work with any analysis tool and report format

FORMAT YOUR ANSWERS:
- Start with a direct answer to the question
- Support with relevant data points from the report
- Suggest follow-up actions if applicable
- Keep responses under 500 words"""

            # Build user message with report context
            user_message = f"""ANALYSIS REPORT DATA:
{report_context}

USER QUESTION: {question}

Please answer based ONLY on the report data above."""

            # Build messages list
            messages = [{"role": "system", "content": system_prompt}]

            # Add conversation history
            if conversation_history:
                messages.extend(conversation_history)

            # Add current question
            messages.append({"role": "user", "content": user_message})

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Lower temperature for factual answers
                max_tokens=1000,
            )

            answer = response.choices[0].message.content

            return {
                "status": "success",
                "answer": answer,
                "sources": self._extract_relevant_fields(question, user_message),
                "confidence": 0.95,
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "model_used": self.model,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

        except Exception as e:
            # Fallback to rule-based if API fails
            return {
                "status": "success",
                "answer": self._get_rule_based_answer(
                    question, json.loads(report_context) if isinstance(report_context, str) else report_context
                ),
                "sources": [],
                "confidence": 0.6,
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "model_used": "rule-based-fallback",
                "fallback_reason": str(e),
            }

    @staticmethod
    def _build_report_context(report: Dict[str, Any]) -> str:
        """
        Build formatted context from analysis report.
        Works with any tool's analysis report (profile-my-data, clean-my-data, etc).

        Args:
            report: Analysis report dictionary from any /analyze response

        Returns:
            Formatted report context string
        """
        context_parts = []

        # Add basic info
        context_parts.append("=== ANALYSIS OVERVIEW ===")
        context_parts.append(f"Tool: {report.get('tool', 'Unknown')}")
        context_parts.append(f"Status: {report.get('status', 'Unknown')}")
        context_parts.append(f"Timestamp: {report.get('timestamp', 'Unknown')}")
        context_parts.append("")

        # Get report data (works with any tool)
        report_data = report.get("report", {})
        
        # Add alerts (common across all tools)
        alerts = report_data.get("alerts", [])
        if alerts:
            context_parts.append("=== ALERTS ===")
            for alert in alerts[:5]:  # Limit to first 5 to save tokens
                context_parts.append(
                    f"- [{alert.get('severity', 'Unknown').upper()}] "
                    f"{alert.get('category', 'Unknown')}: {alert.get('message', '')}"
                )
            context_parts.append("")

        # Add executive summary metrics (common across all tools)
        summary = report_data.get("executiveSummary", [])
        if summary:
            context_parts.append("=== KEY METRICS ===")
            for item in summary[:8]:  # Limit to first 8
                context_parts.append(
                    f"- {item.get('title', '')}: {item.get('value', '')} "
                    f"({item.get('status', '')})"
                )
            context_parts.append("")

        # Add analysis summary (common across all tools)
        analysis_summary = report_data.get("analysisSummary", {})
        if analysis_summary.get("summary"):
            context_parts.append("=== ANALYSIS SUMMARY ===")
            context_parts.append(analysis_summary.get("summary", ""))
            context_parts.append("")

        # Add recommendations (common across all tools)
        recommendations = report_data.get("recommendations", [])
        if recommendations:
            context_parts.append("=== RECOMMENDATIONS ===")
            for rec in recommendations[:3]:  # Limit to first 3
                context_parts.append(
                    f"- {rec.get('recommendation', '')} "
                    f"(Priority: {rec.get('priority', 'Unknown')})"
                )
            context_parts.append("")

        # Add routing decisions (common across all tools)
        routing = report_data.get("routing_decisions", [])
        if routing:
            context_parts.append("=== NEXT STEPS ===")
            for route in routing[:1]:  # Show only first recommendation
                context_parts.append(
                    f"Recommended tool: {route.get('next_tool', 'Unknown')} "
                    f"(Confidence: {route.get('confidence_score', 0):.0%})"
                )
                context_parts.append(
                    f"Reason: {route.get('reason', '')}"
                )

        # Add any tool-specific data that might be in the report
        if "data" in report_data:
            context_parts.append("=== ADDITIONAL DATA ===")
            data = report_data.get("data", {})
            if isinstance(data, dict):
                for key in list(data.keys())[:5]:  # Limit to first 5 keys
                    value = data[key]
                    if isinstance(value, str):
                        context_parts.append(f"- {key}: {value[:100]}")

        return "\n".join(context_parts)

    @staticmethod
    def _get_rule_based_answer(question: str, report: Dict[str, Any]) -> str:
        """
        Generate rule-based answer when AI is unavailable.
        Works with any tool's analysis report.

        Args:
            question: User's question
            report: Analysis report from any tool

        Returns:
            Rule-based answer string
        """
        question_lower = question.lower()
        report_data = report.get("report", {})

        # Detect question type and provide relevant answer (tool-agnostic)
        if any(word in question_lower for word in ["quality", "score", "metric", "rating", "readiness"]):
            summary = report_data.get("executiveSummary", [])
            if summary:
                metrics = [f"{s.get('title')}: {s.get('value')}" for s in summary[:3]]
                return f"Key metrics from the analysis: {', '.join(metrics)}. Please review the full report for detailed metrics and explanations."

        elif any(word in question_lower for word in ["issue", "problem", "error", "alert", "concern"]):
            alerts = report_data.get("alerts", [])
            if alerts:
                alert_msgs = [a.get("message", "") for a in alerts[:2]]
                return f"Key issues identified: {'; '.join(alert_msgs)}. Please review the full report for all details and severity levels."

        elif any(word in question_lower for word in ["recommendation", "action", "improve", "next", "do"]):
            recs = report_data.get("recommendations", [])
            if recs:
                actions = [r.get("recommendation", "") for r in recs[:2]]
                return f"Recommended actions: {'; '.join(actions)}. Prioritize these actions based on your business needs and available resources."
            
            # Fallback to routing if no recommendations
            routing = report_data.get("routing_decisions", [])
            if routing:
                next_tool = routing[0].get("next_tool", "")
                reason = routing[0].get("reason", "")
                return f"Next recommended step: Run {next_tool}. {reason}"

        elif any(word in question_lower for word in ["summary", "overview", "overall", "what happened"]):
            analysis_summary = report_data.get("analysisSummary", {})
            if analysis_summary.get("summary"):
                return analysis_summary.get("summary", "")

        # Default response
        return "I found the analysis report. Please ask more specific questions about: quality metrics, issues/problems, recommendations, next steps, or the overall summary. I can answer questions about any analysis tool."

    @staticmethod
    def _extract_relevant_fields(question: str, context: str) -> List[str]:
        """
        Extract relevant fields/sections used to answer question.
        Works with any analysis tool.

        Args:
            question: User's question
            context: Report context or raw context

        Returns:
            List of relevant field names
        """
        sources = []
        question_lower = question.lower()

        # Map keywords to sources (tool-agnostic)
        keyword_map = {
            "quality": ["executiveSummary", "quality_metrics"],
            "score": ["executiveSummary", "summary_metrics"],
            "metric": ["executiveSummary", "summary_metrics"],
            "rating": ["executiveSummary", "readiness-rater"],
            "readiness": ["executiveSummary", "readiness-rater"],
            "issue": ["alerts", "issues", "recommendations"],
            "problem": ["alerts", "issues", "recommendations"],
            "alert": ["alerts"],
            "concern": ["alerts", "issues"],
            "recommendation": ["recommendations", "routing_decisions"],
            "action": ["recommendations", "routing_decisions"],
            "next": ["routing_decisions", "recommendations"],
            "improve": ["recommendations"],
            "tool": ["routing_decisions"],
            # Tool-specific keywords
            "drift": ["drift-detector"],
            "risk": ["score-risk"],
            "governance": ["governance-checker"],
            "null": ["null-handler"],
            "outlier": ["outlier-remover"],
            "type": ["type-fixer"],
            "test": ["test-coverage-agent"],
            "clean": ["routing_decisions", "clean-my-data"],
            "profile": ["unified-profiler", "profile-my-data"],
        }

        for keyword, fields in keyword_map.items():
            if keyword in question_lower:
                sources.extend(fields)

        return list(set(sources))  # Remove duplicates

    @staticmethod
    def get_fallback_answer(question: str) -> str:
        """
        Get fallback answer when system is unavailable.

        Args:
            question: User's question

        Returns:
            Fallback response
        """
        return (
            "I'm unable to process your question at the moment. "
            "Please try again later or review the detailed analysis report "
            "to find the information you're looking for."
        )
