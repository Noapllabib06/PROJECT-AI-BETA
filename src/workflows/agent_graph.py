"""Agent Execution Graph and State Machine for JARVIS.

Manages the complete lifecycle:
User Query -> Route -> Memory Injection -> Planning -> Tool Execution -> Self-Correction -> Synthesis -> Supervision
"""

import asyncio
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field

from src.agents.base_agent import BaseAgent, ToolCall, OutputParser
from src.agents.planner_agent import PlannerAgent, ExecutionPlan
from src.agents.tool_agent import ToolAgent, ToolExecutionResult
from src.agents.supervisor_agent import SupervisorAgent, TraceEvent, SupervisedResponse
from src.workflows.task_router import TaskRouter
from src.memory.memory_store import MemoryStore
from src.prompts import (
    build_system_prompt,
    build_error_feedback_prompt,
    SYNTHESIS_SYSTEM_PROMPT,
)
from config.settings import settings, get_logger

logger = get_logger("AgentGraph")


class AgentState(BaseModel):
    user_query: str
    conversation_id: str = "default"
    routed_tools: List[Dict[str, Any]] = Field(default_factory=list)
    augmented_context: Dict[str, Any] = Field(default_factory=dict)
    plan: Optional[ExecutionPlan] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    execution_results: List[ToolExecutionResult] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = Field(default_factory=lambda: settings.agent.max_self_correction_attempts)
    raw_llm_output: str = ""
    synthesized_answer: str = ""
    supervised_response: Optional[SupervisedResponse] = None
    is_completed: bool = False
    error: Optional[str] = None


class AgentGraph:
    """State graph orchestrating the multi-agent execution pipeline."""

    def __init__(
        self,
        base_agent: Optional[BaseAgent] = None,
        planner_agent: Optional[PlannerAgent] = None,
        tool_agent: Optional[ToolAgent] = None,
        supervisor_agent: Optional[SupervisorAgent] = None,
        task_router: Optional[TaskRouter] = None,
        memory_store: Optional[MemoryStore] = None,
    ):
        self.base_agent = base_agent or BaseAgent()
        self.planner = planner_agent or PlannerAgent()
        self.tool_agent = tool_agent or ToolAgent()
        self.supervisor = supervisor_agent or SupervisorAgent()
        self.router = task_router or TaskRouter()
        self.memory = memory_store or MemoryStore()

    def set_trace_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self.supervisor.trace_callback = callback

    async def run_pipeline(
        self,
        user_query: str,
        available_tool_defs: List[Dict[str, Any]],
        conversation_id: str = "default",
        on_trace: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> AgentState:
        if on_trace:
            self.set_trace_callback(on_trace)

        state = AgentState(user_query=user_query, conversation_id=conversation_id)

        # ----------------------------------------------------
        # 1. Intent Routing & Tool Selection
        # ----------------------------------------------------
        self.supervisor.emit_trace("routing", "Analyzing user query and routing tools...", {"query": user_query})
        routed_tools, scores = self.router.route_tools(user_query, available_tool_defs)
        state.routed_tools = routed_tools
        self.supervisor.emit_trace("routing_completed", f"Selected {len(routed_tools)} candidate tools", {"tools": [t.get("name") for t in routed_tools]})

        # ----------------------------------------------------
        # 2. Memory Context Retrieval
        # ----------------------------------------------------
        self.supervisor.emit_trace("memory_retrieval", "Fetching facts and long-term memories...")
        context_data = self.memory.build_augmented_context(user_query)
        state.augmented_context = context_data

        # ----------------------------------------------------
        # 3. Planning & Sub-Task Analysis
        # ----------------------------------------------------
        available_names = [t.get("name", "") for t in routed_tools]
        plan = self.planner.create_plan(user_query, available_tools=available_names)
        state.plan = plan
        if plan.is_multi_step:
            self.supervisor.emit_trace("planning", f"Multi-step query detected with {len(plan.tasks)} subtasks", {"tasks": [t.description for t in plan.tasks]})

        # ----------------------------------------------------
        # 4. LLM Tool-Call Generation & Self-Correction Loop
        # ----------------------------------------------------
        system_prompt = build_system_prompt(
            relevant_tools=routed_tools,
            facts=context_data.get("facts", []),
            conversation_context=context_data.get("formatted_context", "")
        )

        current_prompt = f"User: {user_query}\nAssistant:"
        state.retry_count = 0

        while state.retry_count <= state.max_retries:
            self.supervisor.emit_trace("llm_reasoning", f"Invoking LLM for tool decision (attempt {state.retry_count + 1})...")

            # Include recent chat history
            recent_msgs = self.memory.get_chat_history(limit=6)
            chat_messages = [{"role": m["role"], "content": m["content"]} for m in recent_msgs]
            chat_messages.append({"role": "user", "content": current_prompt})

            try:
                raw_output = await self.base_agent.a_chat(
                    messages=chat_messages,
                    system_prompt=system_prompt,
                    temperature=0.1
                )
                state.raw_llm_output = raw_output
            except Exception as e:
                logger.error(f"LLM invocation failed: {e}")
                # Fallback to pure chat if Ollama is unreachable
                state.tool_calls = [ToolCall(tool="chat", query=f"Maaf, terjadi kendala pada LLM: {str(e)}")]
                break

            # Validate tool output with Pydantic v2 OutputParser
            all_known_tools = list(self.tool_agent.tool_handlers.keys())
            validation = OutputParser.parse_and_validate(
                raw_output,
                valid_tools=available_names,
                all_fallback_tools=all_known_tools
            )

            if validation.success:
                state.tool_calls = validation.data
                self.supervisor.emit_trace("tool_decision", f"Selected tools: {[tc.tool for tc in state.tool_calls]}")
                break
            else:
                state.retry_count += 1
                logger.warning(f"Invalid model output (attempt {state.retry_count}): {validation.error}")
                if state.retry_count > state.max_retries:
                    logger.error("Max self-correction retries exceeded. Falling back to direct chat.")
                    state.tool_calls = [ToolCall(tool="chat", query=user_query)]
                    break

                # Self-Correction Feedback Injection
                feedback = build_error_feedback_prompt(raw_output, validation.error or "Format tidak valid")
                self.supervisor.emit_trace("self_correction", "Sending structured correction feedback to LLM...", {"error": validation.error})
                current_prompt = f"{user_query}\n\n{feedback}"

        # ----------------------------------------------------
        # 5. Tool Execution
        # ----------------------------------------------------
        if state.tool_calls:
            self.supervisor.emit_trace("tool_execution", f"Executing {len(state.tool_calls)} tool calls...")
            results = await self.tool_agent.execute_batch(state.tool_calls)
            state.execution_results = results

            # ReAct feedback: check if any tool failed with retryable error
            for tc, res in zip(state.tool_calls, results):
                if not res.success and settings.agent.enable_feedback_loop:
                    self.supervisor.emit_trace("tool_warning", f"Tool '{tc.tool}' failed: {res.error}")

        # ----------------------------------------------------
        # 6. Response Synthesis
        # ----------------------------------------------------
        has_non_chat = any(tc.tool != "chat" for tc in state.tool_calls)

        # Tools that already provide a full, formatted Markdown response
        full_markdown_tools = {"get_jarvis_capabilities", "draft_content"}
        is_self_contained = (
            len(state.tool_calls) == 1
            and state.tool_calls[0].tool in full_markdown_tools
            and state.execution_results
            and state.execution_results[0].success
        )

        if is_self_contained and state.execution_results:
            state.synthesized_answer = str(state.execution_results[0].output)
        elif not has_non_chat and state.execution_results:
            raw_chat_output = str(state.execution_results[0].output).strip()
            # If chat output is a query echo, raw JSON, or too short for a factual question, synthesize a rich answer
            if raw_chat_output == user_query or raw_chat_output.startswith("{") or raw_chat_output.startswith("[") or len(raw_chat_output) < 20:
                try:
                    state.synthesized_answer = await self.base_agent.a_generate(
                        prompt=user_query,
                        system_prompt=SYNTHESIS_SYSTEM_PROMPT,
                        temperature=settings.llm.temperature
                    )
                except Exception:
                    state.synthesized_answer = raw_chat_output
            else:
                state.synthesized_answer = raw_chat_output
        else:
            self.supervisor.emit_trace("synthesis", "Synthesizing tool results into final answer...")
            synthesis_prompt = f"""Instruksi Pengguna: {user_query}

Hasil Tindakan / Eksekusi Tool:
"""
            for res in state.execution_results:
                status = "BERHASIL" if res.success else "GAGAL"
                synthesis_prompt += f"\n- Tool '{res.tool}' [{status}]:\n{res.output or res.error}\n"

            synthesis_prompt += """
Instruksi Sintesis:
Susunlah jawaban akhir yang sangat terstruktur, jelas, komprehensif, dan elegan dalam bahasa Indonesia.
Gunakan struktur:
1. Ringkasan Inti (langsung menjawab tanpa basa-basi teknis).
2. Poin-Poin Kunci & Analisis (gunakan bullet points tebal: - **Poin**: Penjelasan).
3. Konteks/Dampak penting bila ada.
4. Tautan Sumber & Referensi jika tersedia dari hasil tool.
DILARANG menggunakan format JSON atau menyebutkan label internal sistem."""

            try:
                state.synthesized_answer = await self.base_agent.a_generate(
                    prompt=synthesis_prompt,
                    system_prompt=SYNTHESIS_SYSTEM_PROMPT,
                    temperature=settings.llm.temperature
                )
            except Exception as e:
                logger.error(f"Synthesis failed: {e}")
                state.synthesized_answer = "\n".join(str(r.output or r.error) for r in state.execution_results)

        # ----------------------------------------------------
        # 7. Supervision & Answer Sanitization
        # ----------------------------------------------------
        supervised = self.supervisor.synthesize_tool_results(
            user_query=user_query,
            results=state.execution_results,
            llm_synthesis=state.synthesized_answer
        )
        state.supervised_response = supervised
        state.is_completed = True

        # Store message turn in Short-Term Memory
        self.memory.add_user_message(user_query)
        self.memory.add_assistant_message(
            content=supervised.final_text,
            metadata={"tools": [tc.tool for tc in state.tool_calls]}
        )

        return state
