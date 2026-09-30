"""SSE Streaming utilities for Copilot."""

import json
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from uuid import UUID

from app.services.copilot.graph import run_copilot


async def stream_copilot_response(
    user_id: str,
    portfolio_id: Optional[str],
    session_id: str,
    user_message: str,
    max_iterations: int = 5,
) -> AsyncGenerator[str, None]:
    """
    Stream Copilot response as SSE events.
    
    Yields SSE-formatted strings for:
    - token: streaming text content
    - citation: citation from tool result
    - done: completion signal
    - error: error signal
    """
    
    try:
        from app.services.copilot.memory import session_store
        from langchain_core.messages import HumanMessage, AIMessage
        
        # Add user message to session
        session_store.add_message(session_id, "user", user_message)
        
        # Get message history
        messages = session_store.get_messages(session_id, limit=10)
        
        # Convert to LangChain messages
        lc_messages = []
        for msg in messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))
        
        # Run the graph with REAL user and portfolio context
        result = await run_copilot(
            user_id=user_id,
            portfolio_id=portfolio_id,
            session_id=session_id,
            messages=lc_messages,
        )
        
        # Stream the final response in chunks
        final_response = result.get("final_response", "") or ""
        citations = result.get("citations", [])
        
        # Simulate token streaming by chunking
        chunk_size = 50
        if final_response:
            for i in range(0, len(final_response), chunk_size):
                chunk = final_response[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                await asyncio.sleep(0.02)  # Small delay for streaming effect
        
        # Send citations
        for citation in citations:
            yield f"data: {json.dumps({'type': 'citation', 'citation': citation})}\n\n"
        
        # Send done event
        yield f"data: {json.dumps({'type': 'done', 'message_id': 'msg-' + str(abs(hash(final_response)))})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


async def run_copilot_sync(
    user_id: str,
    portfolio_id: Optional[str],
    session_id: str,
    user_message: str,
) -> Dict[str, Any]:
    """Run Copilot synchronously and return full result."""
    from app.services.copilot.memory import session_store
    from langchain_core.messages import HumanMessage, AIMessage
    
    # Add user message
    session_store.add_message(session_id, "user", user_message)
    
    # Get message history
    messages = session_store.get_messages(session_id, limit=10)
    
    lc_messages = []
    for msg in messages:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))
    
    # Run graph with REAL user and portfolio context
    result = await run_copilot(
        user_id=user_id,
        portfolio_id=portfolio_id,
        session_id=session_id,
        messages=lc_messages,
    )
    
    # Add assistant response to history
    final_response = result.get("final_response", "")
    citations = result.get("citations", [])
    tool_calls = []
    for r in result.get("agent_results", []):
        tool_calls.extend(r.get("tool_calls", []))
    
    session_store.add_message(
        session_id=session_id,
        role="assistant",
        content=final_response,
        citations=citations,
        tool_calls=tool_calls,
    )
    
    return {
        "response": final_response,
        "citations": citations,
        "tool_calls": tool_calls,
        "guardrail_flags": result.get("guardrail_flags", []),
    }