"""Base Agent class for Copilot specialized agents."""

import json
import time
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
from google import genai
from google.genai import types
from langchain_core.tools import BaseTool

from app.config import get_settings
from app.services.copilot.state import CopilotState, AgentResult

class BaseAgent(ABC):
    """Base class for all specialized agents."""
    
    # Override in subclasses
    name: str = "base_agent"
    system_prompt: str = ""
    tools: List[BaseTool] = []
    
    # Model configuration
    MODEL = "gemini-2.0-flash"
    GENERATION_CONFIG = {
        "temperature": 0.3,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 4096,
    }
    
    def __init__(self):
        _key = get_settings().gemini_api_key
        self.client = genai.Client(api_key=_key) if _key else None
        self._tool_map = {tool.name: tool for tool in self.tools}
    
    @abstractmethod
    async def execute(self, state: CopilotState) -> CopilotState:
        """Execute the agent and return updated state."""
        pass
    
    def _build_context(self, state: CopilotState) -> str:
        """Build context string for the agent."""
        # Get portfolio info from state
        portfolio_id = state.get("portfolio_id")
        user_id = state.get("user_id")
        
        context_parts = [
            f"Portfolio ID: {portfolio_id or 'Not selected'}",
            f"User ID: {user_id}",
        ]
        
        # Add recent conversation
        recent_messages = state.get("messages", [])[-5:]
        if recent_messages:
            context_parts.append("\nRecent conversation:")
            for msg in recent_messages:
                role = "User" if msg.type == "human" else "Assistant"
                context_parts.append(f"  {role}: {msg.content[:200]}")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, prompt: str, tools: Optional[List[BaseTool]] = None) -> Dict[str, Any]:
        """Call Gemini LLM with tool calling support."""
        client = getattr(self, "_effective_client", None) or self.client
        if not client:
            return {"text": "LLM not configured", "tool_calls": []}
        
        # Convert tools to Gemini format
        gemini_tools = []
        if tools:
            for tool in tools:
                # Get tool schema
                schema = tool.args_schema.model_json_schema() if tool.args_schema else {"type": "object", "properties": {}}
                gemini_tools.append(types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=schema,
                ))
        
        config = types.GenerateContentConfig(
            temperature=self.GENERATION_CONFIG["temperature"],
            top_p=self.GENERATION_CONFIG["top_p"],
            top_k=self.GENERATION_CONFIG["top_k"],
            max_output_tokens=self.GENERATION_CONFIG["max_output_tokens"],
            tools=[types.Tool(function_declarations=gemini_tools)] if gemini_tools else None,
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO")
            ) if gemini_tools else None,
        )
        
        response = client.models.generate_content(
            model=self.MODEL,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=config,
        )
        
        # Parse response
        result = {"text": response.text or "", "tool_calls": []}
        
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    fc = part.function_call
                    result["tool_calls"].append({
                        "name": fc.name,
                        "args": dict(fc.args) if fc.args else {},
                    })
        
        return result
    
    async def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Execute a tool by name."""
        tool = self._tool_map.get(tool_name)
        if not tool:
            return {"error": f"Tool {tool_name} not found"}
        
        try:
            # Extract portfolio_id and user_id from args if needed
            # These would be passed from the state
            result = await tool.ainvoke(args)
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _run_agent_loop(self, state: CopilotState) -> AgentResult:
        """Main agent execution loop with tool calling."""
        start_time = time.time()
        
        # Build initial prompt
        context = self._build_context(state)
        prompt = f"{self.system_prompt}\n\nContext:\n{context}\n\nProvide your analysis. Use tools as needed."
        
        citations = []
        tool_calls = []
        tool_results = []
        all_content = []
        
        # Agent loop - max 5 tool call rounds
        for round_num in range(5):
            response = await self._call_llm(prompt, self.tools)
            content = response.get("text", "")
            all_content.append(content)
            
            tool_calls_made = response.get("tool_calls", [])
            if not tool_calls_made:
                break
            
            # Execute tool calls
            for tc in tool_calls_made:
                tool_name = tc["name"]
                tool_args = tc["args"]
                tool_calls.append({"name": tool_name, "args": tool_args, "round": round_num})
                
                # Execute tool
                result = await self._execute_tool(tool_name, tool_args)
                tool_results.append({"tool": tool_name, "args": tool_args, "result": result, "round": round_num})
                
                # Extract citations from tool results
                if isinstance(result, dict) and "data" in result:
                    data = result["data"]
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if isinstance(value, (str, int, float)):
                                citations.append({
                                    "source": tool_name,
                                    "data_point": key,
                                    "value": value,
                                })
                
                # Add tool result to prompt for next round
                prompt += f"\n\nTool Result ({tool_name}):\n{json.dumps(result, default=str)[:2000]}"
        
        final_content = "\n".join(all_content).strip()
        
        return AgentResult(
            agent_name=self.name,
            content=final_content,
            citations=citations,
            tool_calls=tool_calls,
            confidence=0.85 if final_content else 0.3,
            error=None,
        )
    
    async def execute(self, state: CopilotState) -> CopilotState:
        """Execute the agent and return updated state."""
        # Per-request key resolution: user-stored key > server env key.
        from app.services.copilot.gemini_client import resolve_gemini_client
        client, _source = await resolve_gemini_client(state.get("user_id"))
        self._effective_client = client

        if not client:
            return {
                **state,
                "agent_results": state["agent_results"] + [AgentResult(
                    agent_name=self.name,
                    content="LLM not configured (no Gemini API key)",
                    citations=[],
                    tool_calls=[],
                    confidence=0.0,
                    error="missing_api_key",
                )],
                "agents_completed": state["agents_completed"] + [self.name],
                "current_agent": None,
                "needs_gemini_key": True,
            }
        
        # Update state
        state["current_agent"] = self.name
        
        # Run agent
        result = await self._run_agent_loop(state)
        
        return {
            **state,
            "agent_results": state["agent_results"] + [result],
            "agents_completed": state["agents_completed"] + [self.name],
            "current_agent": None,
        }