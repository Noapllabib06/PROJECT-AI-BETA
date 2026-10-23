"""Tool Agent responsible for executing individual tools and handling error recovery.

Migrated from:
- src/engine/agent.js
- src/engine/feedback_loop.js
"""

import time
import inspect
import asyncio
from typing import Dict, Any, Optional, Callable, List, Union
from pydantic import BaseModel, Field

from src.agents.base_agent import BaseAgent, ToolCall
from config.settings import settings, get_logger

logger = get_logger("ToolAgent")


class ToolExecutionResult(BaseModel):
    tool: str
    query: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class ToolAgent(BaseAgent):
    """Executes validated tool calls and handles micro-ReAct retry logic."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tool_handlers: Dict[str, Callable] = {}

    def register_tool(self, name: str, handler: Callable) -> None:
        self.tool_handlers[name] = handler
        logger.debug(f"Registered tool handler: '{name}'")

    def register_tools(self, handlers: Dict[str, Callable]) -> None:
        for name, handler in handlers.items():
            self.register_tool(name, handler)

    async def execute_tool_call(self, tool_call: ToolCall) -> ToolExecutionResult:
        """Executes a single ToolCall with timeout and error capture."""
        tool_name = tool_call.tool
        query = tool_call.query
        params = tool_call.parameters or {}

        if tool_name == "chat":
            return ToolExecutionResult(
                tool="chat",
                query=query,
                success=True,
                output=query,
                duration_ms=0.0
            )

        handler = self.tool_handlers.get(tool_name)
        if not handler:
            err_msg = f"Tool '{tool_name}' tidak ditemukan di sistem."
            logger.error(err_msg)
            return ToolExecutionResult(
                tool=tool_name,
                query=query,
                success=False,
                error=err_msg
            )

        start_time = time.perf_counter()
        try:
            logger.info(f"Executing tool '{tool_name}' with query: '{query[:80]}'")
            timeout_sec = float(settings.tools.command_timeout_seconds)

            # Determine whether handler accepts **kwargs or (query, **kwargs)
            sig = inspect.signature(handler)
            accepts_query = "query" in sig.parameters
            has_var_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

            call_args = {**params}
            if accepts_query and "query" not in call_args:
                call_args["query"] = query

            if not has_var_kwargs:
                # If tool only accepts 'query' but args had expression or other keys
                if accepts_query and "query" in call_args:
                    call_args = {"query": call_args["query"]}
                else:
                    call_args = {k: v for k, v in call_args.items() if k in sig.parameters}

            if not call_args and len(sig.parameters) > 0:
                first_param = list(sig.parameters.keys())[0]
                call_args[first_param] = query

            if inspect.iscoroutinefunction(handler):
                output = await asyncio.wait_for(handler(**call_args), timeout=timeout_sec)
            else:
                loop = asyncio.get_event_loop()
                def sync_call():
                    return handler(**call_args)

                output = await asyncio.wait_for(loop.run_in_executor(None, sync_call), timeout=timeout_sec)

            duration = (time.perf_counter() - start_time) * 1000.0
            logger.info(f"Tool '{tool_name}' executed successfully in {duration:.1f}ms")
            return ToolExecutionResult(
                tool=tool_name,
                query=query,
                success=True,
                output=output,
                duration_ms=duration
            )

        except asyncio.TimeoutError:
            duration = (time.perf_counter() - start_time) * 1000.0
            err_msg = f"Eksekusi tool '{tool_name}' melebihi batas waktu ({settings.tools.command_timeout_seconds} detik)."
            logger.error(err_msg)
            return ToolExecutionResult(
                tool=tool_name,
                query=query,
                success=False,
                error=err_msg,
                duration_ms=duration
            )
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000.0
            err_msg = f"Kesalahan saat menjalankan tool '{tool_name}': {str(e)}"
            logger.error(err_msg)
            return ToolExecutionResult(
                tool=tool_name,
                query=query,
                success=False,
                error=err_msg,
                duration_ms=duration
            )

    async def execute_batch(self, tool_calls: List[ToolCall]) -> List[ToolExecutionResult]:
        """Executes multiple tool calls concurrently or sequentially."""
        tasks = [self.execute_tool_call(tc) for tc in tool_calls]
        return await asyncio.gather(*tasks)
