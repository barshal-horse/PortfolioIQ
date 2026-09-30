"""Copilot Router — Intent classification and agent dispatch."""

import json
from typing import Any
from google import genai
from google.genai import types

from app.config import get_settings
from app.services.copilot.state import CopilotState

# Initialize Gemini client
_settings = get_settings()
client = genai.Client(api_key=_settings.gemini_api_key) if _settings.gemini_api_key else None

# Agent registry — must match the agents actually registered in the LangGraph.
# Keep in sync with AGENTS in app.services.copilot.agents
AGENT_NAMES = [
    "risk_agent",
    "benchmark_agent",
    "health_agent",
    "optimization_agent",
    "stress_testing_agent",
]

ROUTER_SYSTEM_PROMPT = """You are the PortfolioIQ Copilot Router. Your job is to:
1. Understand the user's question about their portfolio
2. Determine which specialized agent(s) should handle the query
3. Extract relevant parameters

Available agents and their capabilities:

- risk_agent: Portfolio risk metrics (volatility, Sharpe ratio, Sortino ratio, beta, alpha,
  information ratio, tracking error, max drawdown, VaR, CVaR). Use for questions about
  risk, safety, downside, worst case.

- benchmark_agent: Performance vs benchmarks (Nifty50, Sensex, S&P500, Nasdaq100).
  Active return, tracking error, capture ratios. Use for questions about how portfolio
  compares to market/indices.

- health_agent: Portfolio health score (0-100), diversification, risk, performance, and
  efficiency subscores. Use for overall portfolio assessment, grades, health checks.

- optimization_agent: Portfolio optimization (Mean-Variance, Max Sharpe, Min Variance,
  Risk Parity, Black-Litterman). Use for questions about improving allocation, rebalancing,
  optimal weights.

- stress_testing_agent: Historical crisis scenarios (2008 GFC, COVID, inflation, rate shock).
  Use for "what if" and stress/scenario questions.

- news_agent: Holdings-related news, earnings, market events. Use for news, events,
  and recent developments. (Route such questions to health_agent for a general
  portfolio check until the news agent is available.)

RULES:
- Select 1-3 agents maximum per query
- For complex queries, select multiple agents
- For simple greetings or off-topic, return empty agent list
- Always provide reasoning for your selection

Respond in JSON format:
{
    "intent": "brief description of user intent",
    "agents": ["agent_name_1", "agent_name_2"],
    "reasoning": "why these agents",
    "parameters": {
        "lookback_days": 252,
        "benchmark": "SP500"
    }
}"""

ROUTER_GENERATION_CONFIG = {
    "temperature": 0.1,
    "top_p": 0.9,
    "max_output_tokens": 512,
    "response_mime_type": "application/json",
}


async def copilot_router(state: CopilotState) -> CopilotState:
    """Route user query to appropriate agents."""
    if not client:
        return {
            **state,
            "intent": "no_llm_available",
            "selected_agents": [],
            "routing_reasoning": "Gemini API key not configured",
            "error": "LLM not configured",
            "should_continue": False,
        }

    # Get the last user message
    user_messages = [m for m in state["messages"] if m.type == "human"]
    if not user_messages:
        return {
            **state,
            "intent": "empty_query",
            "selected_agents": [],
            "routing_reasoning": "No user message found",
            "should_continue": False,
        }

    last_query = user_messages[-1].content

    # Build context
    portfolio_context = f"Portfolio ID: {state.get('portfolio_id')}" if state.get("portfolio_id") else "No portfolio selected"

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Content(role="user", parts=[types.Part(text=ROUTER_SYSTEM_PROMPT)]),
                types.Content(role="user", parts=[types.Part(text=f"Portfolio context: {portfolio_context}\n\nUser query: {last_query}")]),
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                top_p=0.9,
                max_output_tokens=512,
                response_mime_type="application/json",
            ),
        )

        result = json.loads(response.text)

        # Validate against agents that actually exist in the graph
        from app.services.copilot.agents import AGENTS
        valid_agents = [a for a in result.get("agents", []) if a in AGENTS]
        if not valid_agents:
            valid_agents = ["health_agent"]  # Default to health for general queries

        return {
            **state,
            "intent": result.get("intent", "general_inquiry"),
            "selected_agents": valid_agents[:3],  # Max 3 agents
            "routing_reasoning": result.get("reasoning", "Default routing"),
            "should_continue": True,
        }

    except Exception as e:
        # Fallback: route to health agent for general queries
        return {
            **state,
            "intent": "routing_error_fallback",
            "selected_agents": ["health_agent"],
            "routing_reasoning": f"Router error, defaulting to health agent: {str(e)}",
            "should_continue": True,
        }


def route_to_agents(state: CopilotState) -> list[str]:
    """Determine next nodes based on selected agents."""
    agents = state.get("selected_agents", [])
    if not agents:
        return ["synthesizer"]
    return agents