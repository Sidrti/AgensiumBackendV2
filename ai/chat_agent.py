"""
Chat Agent AI - Intelligent Q&A System

Answers user questions about analysis reports using OpenAI's language models.
Maintains conversation context and provides data-driven insights.
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


class ChatAgent:
    """Intelligent chat agent for answering questions about analysis reports."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
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
        self.client = None
        self.use_ai = False

        if not self.api_key:
            print(
                "Info: OPENAI_API_KEY not set. Chat will use rule-based responses."
            )
        elif not OPENAI_AVAILABLE:
            print(
                "Warning: OpenAI package not installed. To enable chat, install 'openai' and set OPENAI_API_KEY."
            )
        else:
            try:
                self.client = OpenAI(api_key=self.api_key)
                self.use_ai = True
                print("Info: OpenAI client initialized successfully for chat agent.")
            except Exception as e:
                print(f"Warning: Failed to initialize OpenAI client: {str(e)}. Using fallback responses.")
                self.client = None
                self.use_ai = False

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
            report: Analysis report dictionary
            conversation_history: Previous messages in conversation

        Returns:
            Response dictionary with answer and metadata
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

            if self.use_ai and self.client:
                return self._get_ai_answer(question, report, conversation_history, start_time)
            else:
                return self._get_fallback_answer(question, report, start_time)

        except Exception as e:
            return {
                "status": "error",
                "answer": f"Failed to process question: {str(e)}",
                "sources": [],
                "confidence": 0,
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "model_used": self.model if self.use_ai else None,
            }

    def _get_ai_answer(
        self,
        question: str,
        report: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        start_time: float,
    ) -> Dict[str, Any]:
        """Get AI-powered answer using OpenAI API."""
        try:
            system_prompt = """You are Agensium Co-Pilot, an expert data analyst assistant.
Analyze the provided report and conversation history to answer questions accurately and concisely.
Base your answers strictly on the data provided. Be direct, helpful, and brief."""

            # Build context from report
            report_context = json.dumps(report, indent=2)

            # Build messages
            messages = [{"role": "system", "content": system_prompt}]
            
            if conversation_history:
                messages.extend(conversation_history)

            messages.append(
                {
                    "role": "user",
                    "content": f"Report Data:\n{report_context}\n\nQuestion: {question}",
                }
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=500,
            )

            return {
                "status": "success",
                "answer": response.choices[0].message.content,
                "sources": [],
                "confidence": 0.9,
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "model_used": self.model,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

        except Exception as e:
            print(f"Warning: OpenAI API call failed in chat agent: {str(e)}. Using fallback response.")
            return self._get_fallback_answer(question, report, start_time)

    def _get_fallback_answer(
        self,
        question: str,
        report: Dict[str, Any],
        start_time: float,
    ) -> Dict[str, Any]:
        """Get fallback answer when AI is unavailable."""
        try:
            # Provide a simplified response without full report dump
            answer = f"Your question: {question}\n\n"
            
            if report:
                # Extract key information from report
                tool_name = report.get('tool_name', 'Unknown tool')
                status = report.get('status', 'Unknown status')
                answer += f"Analysis Tool: {tool_name}\nStatus: {status}\n\n"
                answer += "I'm currently unable to provide AI-powered insights. Please review the detailed report sections for information."
            else:
                answer += "No report data available. Please ensure the analysis has completed successfully."
            
            return {
                "status": "success",
                "answer": answer,
                "sources": [],
                "confidence": 0.5,
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "model_used": "fallback",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        except Exception as e:
            print(f"Error in fallback answer generation: {str(e)}")
            return {
                "status": "error",
                "answer": "Unable to process your question at this time.",
                "sources": [],
                "confidence": 0,
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "model_used": "fallback",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

    @staticmethod
    def get_fallback_answer(question: str) -> str:
        """Get fallback answer when system is unavailable."""
        return (
            "I'm unable to process your question at the moment. "
            "Please try again later."
        )
