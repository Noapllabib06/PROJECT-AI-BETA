"""Main Agent Orchestrator for JARVIS.

Entrypoint for query processing, conversation lifecycle, and UI streaming.
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from pydantic import BaseModel, Field

from src.workflows.agent_graph import AgentGraph, AgentState
from src.workflows.task_router import TaskRouter
from src.agents.base_agent import BaseAgent
from src.agents.planner_agent import PlannerAgent
from src.agents.tool_agent import ToolAgent
from src.agents.supervisor_agent import SupervisorAgent
from src.memory.memory_store import memory_store, MemoryStore
from config.settings import settings, get_logger

logger = get_logger("Orchestrator")


class OrchestrationResult(BaseModel):
    conversation_id: str
    response: str
    tools_used: List[str] = Field(default_factory=list)
    traces: List[Dict[str, Any]] = Field(default_factory=list)
    is_multi_step: bool = False
    success: bool = True
    error: Optional[str] = None


class JarvisOrchestrator:
    """Central orchestrator managing agents, memory, tools, and conversations."""

    def __init__(
        self,
        memory: Optional[MemoryStore] = None,
        base_agent: Optional[BaseAgent] = None
    ):
        self.memory = memory or memory_store
        self.base_agent = base_agent or BaseAgent()
        self.planner = PlannerAgent()
        self.tool_agent = ToolAgent()
        self.supervisor = SupervisorAgent()
        self.router = TaskRouter()

        self.graph = AgentGraph(
            base_agent=self.base_agent,
            planner_agent=self.planner,
            tool_agent=self.tool_agent,
            supervisor_agent=self.supervisor,
            task_router=self.router,
            memory_store=self.memory
        )

        self.tool_definitions: List[Dict[str, Any]] = []
        
        # Automatically load and register all 17 tools
        try:
            from src.tools import register_all_tools
            register_all_tools(self)
        except Exception as e:
            logger.warning(f"Failed to auto-register all tools: {e}")

        logger.info(f"JarvisOrchestrator initialized with {len(self.tool_definitions)} tools (Model: {self.base_agent.model_name})")

    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable,
        parameters: Optional[Dict[str, Any]] = None
    ) -> None:
        """Registers a tool with its schema definition and execution callable."""
        tool_def = {
            "name": name,
            "description": description,
            "parameters": parameters or {"type": "object", "properties": {}}
        }
        self.tool_definitions.append(tool_def)
        self.tool_agent.register_tool(name, handler)
        logger.debug(f"Registered tool in orchestrator: '{name}'")

    def switch_conversation(self, conversation_id: str) -> None:
        self.memory.switch_conversation(conversation_id)
        logger.info(f"Switched active conversation to: {conversation_id}")

    async def execute_query(
        self,
        user_query: str,
        conversation_id: Optional[str] = None,
        on_trace: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> OrchestrationResult:
        """Executes a user request through the full AgentGraph workflow."""
        if conversation_id:
            self.switch_conversation(conversation_id)

        active_conv_id = self.memory.short_term.active_conversation.id

        try:
            state: AgentState = await self.graph.run_pipeline(
                user_query=user_query,
                available_tool_defs=self.tool_definitions,
                conversation_id=active_conv_id,
                on_trace=on_trace
            )

            final_text = state.supervised_response.final_text if state.supervised_response else state.synthesized_answer
            tools_used = [tc.tool for tc in state.tool_calls if tc.tool != "chat"]
            traces_dump = [t.model_dump() for t in (state.supervised_response.traces if state.supervised_response else [])]

            return OrchestrationResult(
                conversation_id=active_conv_id,
                response=final_text,
                tools_used=tools_used,
                traces=traces_dump,
                is_multi_step=(state.plan.is_multi_step if state.plan else False),
                success=True
            )

        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            return OrchestrationResult(
                conversation_id=active_conv_id,
                response=f"Maaf, terjadi kesalahan pada sistem: {str(e)}",
                tools_used=[],
                success=False,
                error=str(e)
            )

    async def stream_query(
        self,
        user_query: str,
        conversation_id: Optional[str] = None,
        on_trace: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Streams real-time trace events followed by the final answer."""
        queue: asyncio.Queue = asyncio.Queue()

        def trace_bridge(event: Dict[str, Any]):
            queue.put_nowait({"type": "trace", "data": event})
            if on_trace:
                on_trace(event)

        task = asyncio.create_task(
            self.execute_query(user_query, conversation_id, on_trace=trace_bridge)
        )

        while not task.done():
            while not queue.empty():
                yield await queue.get()
            await asyncio.sleep(0.05)

        # Drain any remaining traces
        while not queue.empty():
            yield await queue.get()

        result = await task
        yield {"type": "answer", "data": result.model_dump()}


# Singleton instance
orchestrator = JarvisOrchestrator()
