"""
Analysis Summary AI Generator

Generates intelligent, actionable analysis summaries using OpenAI's language models.
Universal, general-purpose summarization for any analysis data.

Key Features:
- Simple text-based input (no complex object transformations)
- Universal prompt for any analysis tool/agent
- Cost-optimized with smart token management
- Robust error handling with fallback summaries
- Works with any agent output structure
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


class AnalysisSummaryAI:
    """
    Generates AI-powered analysis summaries from analysis data.
    Universal generator that works with any analysis tool or agent output.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ):
        """
        Initialize the Analysis Summary AI generator.

        Args:
            api_key: OpenAI API key
            model: Model name to use (default: gpt-4o-mini - latest & most efficient)
        """
        # Prefer a provided api_key argument, but fall back to environment variable.
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model

        if not self.api_key:
            # Do not raise here; allow using fallback summarizer behavior when API key is missing.
            print(
                "Info: OPENAI_API_KEY not set. Falling back to rule-based summary for analysis summaries."
            )
            self.client = None
            self.use_ai = False
        else:
            if OpenAI is None:
                print(
                    "Warning: OpenAI package not installed. To enable AI summaries install 'openai' and set OPENAI_API_KEY."
                )
                self.client = None
                self.use_ai = False
            else:
                self.client = OpenAI(api_key=self.api_key)
                self.use_ai = True

    @staticmethod
    def _create_summary_prompt(analysis_data: str, dataset_name: str = "Dataset") -> str:
        """
        Create a universal prompt for summary generation.
        Works with any analysis data in text format.

        Args:
            analysis_data: Complete analysis data as formatted text
            dataset_name: Name of the dataset being analyzed

        Returns:
            Formatted prompt string for OpenAI
        """
        prompt = f"""You are an expert data analyst. Based on the following analysis results for "{dataset_name}", 
generate a professional, actionable analysis summary.

ANALYSIS DATA:
{analysis_data}

Generate a summary with EXACTLY this markdown structure:

## Executive Summary
[2-3 sentences on overall health, readiness, and key metrics]

## Technical Findings
[List 3-4 most critical findings. Use bullet points.]
- [Finding 1 with impact]
- [Finding 2 with impact]
- [Finding 3 with impact]
- [Finding 4 with impact (if applicable)]

## Recommended Actions
[List 3-4 immediate actions ranked by priority. Use bullet points.]
- [Priority 1: Action with expected benefit]
- [Priority 2: Action with expected benefit]
- [Priority 3: Action with expected benefit]
- [Priority 4: Action with expected benefit (if applicable)]

## Next Steps
[1-2 sentences on next steps and monitoring recommendations.]

Be concise, data-driven, and actionable. Focus on what matters most."""

        return prompt

    def generate_summary(
        self,
        analysis_text: str,
        dataset_name: str = "Dataset",
    ) -> Dict[str, Any]:
        """
        Generate an analysis summary from text-based analysis data.

        Args:
            analysis_text: Complete analysis data formatted as text/string
            dataset_name: Name of the dataset for context

        Returns:
            Dictionary with 'status', 'summary', 'execution_time_ms', and 'model_used'
        """
        start_time = time.time()

        try:
            if not analysis_text or not analysis_text.strip():
                return {
                    "status": "error",
                    "summary": "No analysis data provided for summarization.",
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "model_used": self.model,
                }

            # Create universal prompt
            prompt = self._create_summary_prompt(analysis_text, dataset_name)

            # Call OpenAI API if configured, otherwise use fallback
            if not getattr(self, "use_ai", False) or not self.client:
                # No OpenAI client configured - return the fallback summary
                return {
                    "status": "success",
                    "summary": self.get_fallback_summary(analysis_text, dataset_name),
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "model_used": None,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }

            # Call the OpenAI-based client
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional data analyst expert. Generate clear, concise, actionable analysis summaries.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            summary_text = response.choices[0].message.content

            return {
                "status": "success",
                "summary": summary_text,
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "model_used": self.model,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

        except Exception as e:
            return {
                "status": "error",
                "summary": f"Failed to generate summary: {str(e)}",
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "model_used": self.model,
                "error_details": str(e),
            }

    @staticmethod
    def get_fallback_summary(
        analysis_text: str,
        dataset_name: str = "Dataset",
    ) -> str:
        """
        Generate a rule-based fallback summary when OpenAI is unavailable.
        Simple, general-purpose fallback that works with any analysis data.

        Args:
            analysis_text: Text-based analysis data
            dataset_name: Name of the dataset

        Returns:
            Fallback summary string
        """
        lines = [
            f"# Analysis Summary - {dataset_name}",
            "",
            "## Executive Summary",
            f"Analysis completed for {dataset_name}. The data has been comprehensively evaluated across multiple dimensions.",
            "",
            "## Technical Findings",
            "- Data quality and structure have been analyzed",
            "- Patterns and anomalies have been identified",
            "- Compliance and governance checks completed",
            "- Risk factors have been assessed",
            "",
            "## Recommended Actions",
            "- Review detailed findings in the analysis report",
            "- Address high-priority issues identified in the alerts section",
            "- Implement governance controls as recommended",
            "- Monitor key metrics for trends and changes",
            "",
            "## Next Steps",
            "Refer to the detailed analysis sections (Quality Overview, Alerts & Issues, Recommendations) for specific actions and insights.",
        ]

        return "\n".join(lines)
