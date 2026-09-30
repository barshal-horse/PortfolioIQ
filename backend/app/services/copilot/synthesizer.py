"""Response Synthesizer — merge multi-agent results into coherent response."""

import json
from typing import Any, Dict, List
from google import genai
from google.genai import types

from app.config import get_settings
from app.services.copilot.state import CopilotState, AgentResult
from app.services.copilot.gemini_client import resolve_gemini_client

SYNTHESIZER_PROMPT = """You are the PortfolioIQ Response Synthesizer. You receive analysis
results from one or more specialized agents and must create a unified, coherent response.

RULES:
1. Merge overlapping information (don't repeat the same metric from two agents)
2. Present information in a logical order:
   - Lead with the most relevant answer to the user's question
   - Follow with supporting data
   - End with recommendations (if any)
3. Maintain all citations from individual agents
4. Use clear formatting (headers, bullet points, tables where appropriate)
5. Keep the tone professional but accessible
6. If agents disagree, present both perspectives
7. Do NOT add information that wasn't provided by the agents

Agent results to synthesize:
{agent_results}

Original user question:
{user_query}
"""


async def response_synthesizer(state: CopilotState) -> CopilotState:
    """Synthesize multiple agent responses into a unified answer."""
    client, _source = await resolve_gemini_client(state.get("user_id"))
    
    if not client:
        # Simple fallback: concatenate agent results
        combined = []
        for result in state.get("agent_results", []):
            if result.get("content"):
                combined.append(f"**{result['agent_name'].replace('_', ' ').title()}**\n{result['content']}")
        
        return {
            **state,
            "final_response": "\n\n---\n\n".join(combined) if combined else "No analysis available.",
            "citations": [
                c for r in state.get("agent_results", []) 
                for c in r.get("citations", [])
            ],
            "needs_gemini_key": True,
        }
    
    # Get the user's original query
    user_messages = [m for m in state.get("messages", []) if m.type == "human"]
    user_query = user_messages[-1].content if user_messages else "Portfolio analysis request"
    
    # Format agent results
    agent_results_text = []
    all_citations = []
    
    for result in state.get("agent_results", []):
        if result.get("content"):
            agent_results_text.append(
                f"## {result['agent_name'].replace('_', ' ').title()}\n{result['content']}"
            )
        all_citations.extend(result.get("citations", []))
    
    if not agent_results_text:
        return {
            **state,
            "final_response": "No analysis results available.",
            "citations": [],
        }
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Content(role="user", parts=[types.Part(text=SYNTHESIZER_PROMPT)]),
                types.Content(role="user", parts=[types.Part(text=(
                    f"Agent results:\n\n" + "\n\n---\n\n".join(agent_results_text) +
                    f"\n\nOriginal user question:\n{user_query}"
                ))]),
            ],
            config=types.GenerateContentConfig(
                temperature=0.3,
                top_p=0.95,
                max_output_tokens=4096,
            ),
        )
        
        final_response = response.text or "Unable to synthesize response."
        
    except Exception as e:
        # Fallback
        final_response = "\n\n---\n\n".join(agent_results_text)
    
    return {
        **state,
        "final_response": final_response,
        "citations": all_citations,
    }