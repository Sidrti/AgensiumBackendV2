"""
AI Module - Analysis Summary Generation & Chat

This module handles OpenAI integration for:
- Generating intelligent analysis summaries based on data profiling results
- Intelligent tool routing decisions
- Chat agent for Q&A on analysis reports

Uses optimized prompt engineering to avoid oversized data payloads
while capturing essential insights.
"""

import os
from .analysis_summary_ai import AnalysisSummaryAI
from .routing_decision_ai import RoutingDecisionAI
from .chat_agent import ChatAgent

__all__ = [
    "AnalysisSummaryAI",
    "RoutingDecisionAI",
    "ChatAgent",
]
