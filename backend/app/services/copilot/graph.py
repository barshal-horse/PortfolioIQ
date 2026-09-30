"""LangGraph StateGraph compilation for Copilot."""

from langgraph.graph import StateGraph, END
from typing import Dict, List, Any, Callable, Optional

from app.services.copilot.state import CopilotState
from app.services.copilot.router import copilot_router, route_to_agents
from app.services.copilot.synthesizer import response_synthesizer
from app.services.copilot.guardrails import guardrails_node

# Import all agent nodes
from app.services.copilot.agents import AGENTS


def make_agent_node(agent_name: str) -> Callable:
    """Create a node function for an agent."""
    async def agent_node(state: CopilotState) -> CopilotState:
        agent_class = AGENTS.get(agent_name)
        if not agent_class:
            return {
                **state,
                "agent_results": state["agent_results"] + [{
                    "agent_name": agent_name,
                    "content": f"Agent {agent_name} not found",
                    "citations": [],
                    "tool_calls": [],
                    "confidence": 0.0,
                    "error": "agent_not_found",
                }],
                "agents_completed": state["agents_completed"] + [agent_name],
                "current_agent": None,
            }
        
        agent = agent_class()
        return await agent.execute(state)
    
    return agent_node


# Build the graph
def build_copilot_graph() -> StateGraph:
    """Build and compile the Copilot LangGraph."""
    
    graph = StateGraph(CopilotState)
    
    # Add router node
    graph.add_node("router", copilot_router)
    
    # Add agent nodes
    for agent_name in AGENTS.keys():
        graph.add_node(agent_name, make_agent_node(agent_name))
    
    # Add synthesizer and guardrails
    graph.add_node("synthesizer", response_synthesizer)
    graph.add_node("guardrails", guardrails_node)
    
    # Set entry point
    graph.set_entry_point("router")
    
    # Router dispatches to agents
    graph.add_conditional_edges(
        "router",
        route_to_agents,
        {name: name for name in AGENTS.keys()} | {"synthesizer": "synthesizer"},
    )
    
    # All agents → synthesizer
    for agent_name in AGENTS.keys():
        graph.add_edge(agent_name, "synthesizer")
    
    # Synthesizer → guardrails → END
    graph.add_edge("synthesizer", "guardrails")
    graph.add_edge("guardrails", END)
    
    return graph


# Compile the graph
copilot_graph = build_copilot_graph().compile()


async def run_copilot(
    user_id: str,
    portfolio_id: Optional[str],
    session_id: str,
    messages: List[Any],
    max_iterations: int = 5,
) -> CopilotState:
    """Run the Copilot graph with given inputs."""
    
    initial_state: CopilotState = {
        "user_id": user_id,
        "portfolio_id": portfolio_id,
        "session_id": session_id,
        "messages": messages,
        "intent": "",
        "selected_agents": [],
        "routing_reasoning": "",
        "agent_results": [],
        "current_agent": None,
        "agents_completed": [],
        "final_response": None,
        "citations": [],
        "guardrail_flags": [],
        "error": None,
        "should_continue": True,
        "iteration_count": 0,
        "max_iterations": max_iterations,
    }
    
    result = await copilot_graph.ainvoke(initial_state)
    return result