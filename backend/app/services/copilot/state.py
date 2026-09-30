"""Copilot state definition for LangGraph."""

from typing import Annotated, Literal, TypedDict, Any
from langgraph.graph import StateGraph
from langchain_core.messages import BaseMessage
import operator


class AgentResult(TypedDict):
    """Result from a single agent execution."""

    agent_name: str
    content: str
    citations: list[dict]
    tool_calls: list[dict]
    confidence: float
    error: str | None


class CopilotState(TypedDict):
    """Global state shared across all nodes in the graph."""

    # User context
    user_id: str
    portfolio_id: str | None
    session_id: str

    # Conversation
    messages: Annotated[list[BaseMessage], operator.add]

    # Router decisions
    intent: str
    selected_agents: list[str]
    routing_reasoning: str

    # Agent execution
    agent_results: Annotated[list[AgentResult], operator.add]
    current_agent: str | None
    agents_completed: list[str]

    # Final output
    final_response: str | None
    citations: list[dict]
    guardrail_flags: list[str]

    # Control flow
    error: str | None
    should_continue: bool
    iteration_count: int
    max_iterations: int