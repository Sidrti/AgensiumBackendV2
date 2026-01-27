"""
Analysis Summary AI Generator (OpenRouter Version)

Generates intelligent, actionable analysis summaries using OpenRouter API.
Universal, general-purpose summarization for any analysis data.

Key Features:
- Simple text-based input (no complex object transformations)
- Universal prompt for any analysis tool/agent
- Cost-optimized with smart token management
- Robust error handling with fallback summaries
- Works with any agent output structure
- Uses OpenRouter for access to multiple LLM providers

OpenRouter Integration:
- Provides access to multiple AI models through a single API
- Fallback model support for reliability
- Better pricing and availability options
"""

import os
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False


class AnalysisSummaryAI:
    """
    Generates AI-powered analysis summaries from analysis data using OpenRouter.
    Universal generator that works with any analysis tool or agent output.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "google/gemma-3-27b-it:free", # google/gemma-3-27b-it:free
        site_url: Optional[str] = None,
        site_name: Optional[str] = None,
    ):
        """
        Initialize the Analysis Summary AI generator with OpenRouter.

        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            model: Model name to use with OpenRouter
            site_url: Your site URL for OpenRouter rankings (optional)
            site_name: Your site name for OpenRouter rankings (optional)
        """
        # Prefer a provided api_key argument, but fall back to environment variable
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.site_url = site_url or os.getenv("OPENROUTER_SITE_URL", "https://agensium.app")
        self.site_name = site_name or os.getenv("OPENROUTER_SITE_NAME", "Agensium")
        self.client = None
        self.use_ai = False

        if not self.api_key:
            # Do not raise here; allow using fallback summarizer behavior when API key is missing
            print(
                "Info: OPENROUTER_API_KEY not set. Falling back to rule-based summary for analysis summaries."
            )
        elif not OPENAI_AVAILABLE:
            print(
                "Warning: OpenAI package not installed. To enable AI summaries install 'openai' package and set OPENROUTER_API_KEY."
            )
        else:
            try:
                # Initialize OpenAI client with OpenRouter base URL
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.api_key,
                )
                self.use_ai = True
                print(f"Info: OpenRouter client initialized successfully with model: {self.model}")
            except Exception as e:
                print(f"Warning: Failed to initialize OpenRouter client: {str(e)}. Using fallback summaries.")
                self.client = None
                self.use_ai = False

    @staticmethod
    def _create_summary_prompt(analysis_data: str, dataset_name: str = "Dataset") -> str:
        """
        Create a universal prompt for summary generation.
        Works with any analysis data in text format.

        Args:
            analysis_data: Complete analysis data as formatted text
            dataset_name: Name of the dataset being analyzed

        Returns:
            Formatted prompt string for the AI model
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
        Generate an analysis summary from text-based analysis data using OpenRouter.

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

            # Call OpenRouter API if configured, otherwise use fallback
            if not self.use_ai or not self.client:
                # No OpenRouter client configured - return the fallback summary
                return {
                    "status": "success",
                    "summary": self.get_fallback_summary(analysis_text, dataset_name),
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "model_used": "fallback",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }

            try:
                # Call the OpenRouter API with extra headers
                response = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": self.site_url,  # For rankings on openrouter.ai
                        "X-Title": self.site_name,       # For rankings on openrouter.ai
                    },
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional data analyst expert. Generate clear, concise, actionable analysis summaries.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=800,
                )

                summary_text = response.choices[0].message.content

                return {
                    "status": "success",
                    "summary": summary_text,
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "model_used": self.model,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            except Exception as api_error:
                print(f"Warning: OpenRouter API call failed: {str(api_error)}. Using fallback summary.")
                return {
                    "status": "success",
                    "summary": self.get_fallback_summary(analysis_text, dataset_name),
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "model_used": "fallback",
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
        Generate a rule-based fallback summary when OpenRouter is unavailable.
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