"""Supervisor Agent responsible for final answer validation, sanitization, and GUI tracing.

Migrated from:
- src/engine/agent.js (answer formatting & trace emission)
"""

import re
import json
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field

from src.agents.base_agent import BaseAgent
from src.agents.tool_agent import ToolExecutionResult
from config.settings import get_logger

logger = get_logger("SupervisorAgent")


class TraceEvent(BaseModel):
    type: str = "reasoning"
    step: str = ""
    message: str = ""
    content: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=lambda: __import__("time").time())


class SupervisedResponse(BaseModel):
    final_text: str
    is_valid: bool = True
    corrections_applied: List[str] = Field(default_factory=list)
    traces: List[TraceEvent] = Field(default_factory=list)


class SupervisorAgent(BaseAgent):
    """Reviews, polishes, and validates final agent outputs before delivery to user."""

    # Literal section labels to remove if model hallucinates them
    LITERAL_SECTION_TAGS = [
        re.compile(r"^\s*\*{0,2}Header\*{0,2}\s*:\s*", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*\*{0,2}Body\*{0,2}\s*:\s*", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*\*{0,2}Footer\*{0,2}\s*:\s*", re.IGNORECASE | re.MULTILINE),
    ]

    def __init__(self, trace_callback: Optional[Callable[[Dict[str, Any]], None]] = None, **kwargs):
        super().__init__(**kwargs)
        self.trace_callback = trace_callback
        self.current_traces: List[TraceEvent] = []

    def emit_trace(self, step: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Emits structured trace event to observer / UI WebSocket."""
        d = details or {}
        event = TraceEvent(
            type=step,
            step=step,
            message=message,
            content=message,
            details=d
        )
        self.current_traces.append(event)
        logger.debug(f"[TRACE: {step}] {message}")

        if self.trace_callback:
            try:
                dump = event.model_dump()
                for k, v in d.items():
                    if k not in dump:
                        dump[k] = v
                self.trace_callback(dump)
            except Exception as e:
                logger.warning(f"Error in trace_callback: {e}")

    def clean_answer_text(self, text: str) -> tuple[str, List[str]]:
        """Cleans accidental literal tags and trailing JSON syntax from natural language text."""
        cleaned = text.strip()
        applied_corrections = []

        # 1. Remove literal Header / Body / Footer labels
        for pattern in self.LITERAL_SECTION_TAGS:
            if pattern.search(cleaned):
                cleaned = pattern.sub("", cleaned)
                applied_corrections.append("Removed literal Header/Body/Footer tags")

        # 2. Robust JSON envelope unwrapping
        stripped = cleaned.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    # Check for human response fields
                    for field in ["query", "response", "message", "answer", "content", "text", "output"]:
                        if field in parsed and isinstance(parsed[field], str) and parsed[field].strip():
                            cleaned = parsed[field].strip()
                            applied_corrections.append(f"Unwrapped JSON field '{field}'")
                            break
                    else:
                        if "tool" in parsed and "query" in parsed:
                            cleaned = str(parsed["query"]).strip()
                            applied_corrections.append("Extracted query from tool JSON envelope")
                elif isinstance(parsed, list) and len(parsed) > 0:
                    first = parsed[0]
                    if isinstance(first, dict):
                        for field in ["query", "response", "message", "answer", "content", "text"]:
                            if field in first and isinstance(first[field], str) and first[field].strip():
                                cleaned = first[field].strip()
                                applied_corrections.append(f"Unwrapped list JSON field '{field}'")
                                break
            except Exception:
                pass

        # 3. Cleanup markdown backticks if wrapped in ```json ... ```
        if cleaned.startswith("```json") and cleaned.endswith("```"):
            inner = cleaned[7:-3].strip()
            try:
                parsed = json.loads(inner)
                if isinstance(parsed, dict):
                    for field in ["query", "response", "message", "answer", "content", "text"]:
                        if field in parsed and isinstance(parsed[field], str) and parsed[field].strip():
                            cleaned = parsed[field].strip()
                            applied_corrections.append(f"Unwrapped ```json block field '{field}'")
                            break
            except Exception:
                pass

        return cleaned.strip(), applied_corrections

    def synthesize_tool_results(
        self,
        user_query: str,
        results: List[ToolExecutionResult],
        llm_synthesis: Optional[str] = None
    ) -> SupervisedResponse:
        """Produces verified final response combining tool outputs and polish."""
        self.emit_trace(
            step="supervision",
            message=f"Reviewing output for query: '{user_query[:50]}...'",
            details={"results_count": len(results)}
        )

        raw_text = llm_synthesis or ""

        # If no synthesis was provided, generate text from tool results
        if not raw_text:
            output_parts = []
            for res in results:
                if res.tool == "chat":
                    output_parts.append(str(res.output))
                elif res.success:
                    output_parts.append(str(res.output))
                else:
                    output_parts.append(f"⚠️ {res.error}")
            raw_text = "\n\n".join(output_parts)

        clean_text, corrections = self.clean_answer_text(raw_text)

        self.emit_trace(
            step="completed",
            message="Final response synthesized and validated.",
            details={"corrections": corrections}
        )

        return SupervisedResponse(
            final_text=clean_text,
            is_valid=True,
            corrections_applied=corrections,
            traces=list(self.current_traces)
        )
