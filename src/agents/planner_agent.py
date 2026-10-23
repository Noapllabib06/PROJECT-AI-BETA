"""Planner Agent for task decomposition and execution plan construction in JARVIS.

Analyzes user instructions to decide whether single, parallel, or multi-step execution is required.
"""

import re
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

from src.agents.base_agent import BaseAgent, ToolCall
from config.settings import get_logger

logger = get_logger("PlannerAgent")


class SubTask(BaseModel):
    step_id: int
    description: str
    expected_tool: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    depends_on_step: Optional[int] = None


class ExecutionPlan(BaseModel):
    original_query: str
    is_multi_step: bool = False
    tasks: List[SubTask] = Field(default_factory=list)
    suggested_tools: List[str] = Field(default_factory=list)


class PlannerAgent(BaseAgent):
    """Decomposes complex requests into structured sub-tasks."""

    # Conjunction words signaling multi-step tasks in Indonesian
    CONJUNCTION_PATTERN = re.compile(
        r"\b(?:lalu|kemudian|setelah itu|sekaligus|dan juga|baru kemudian|habis itu)\b",
        re.IGNORECASE
    )

    def analyze_complexity(self, user_query: str) -> bool:
        """Heuristic check for multi-step or compound instructions."""
        if not user_query:
            return False
        return bool(self.CONJUNCTION_PATTERN.search(user_query))

    def split_compound_instruction(self, user_query: str) -> List[str]:
        """Splits query on conjunctions into separate clauses."""
        parts = self.CONJUNCTION_PATTERN.split(user_query)
        cleaned = [p.strip() for p in parts if p.strip()]
        return cleaned if cleaned else [user_query]

    def create_plan(
        self,
        user_query: str,
        available_tools: Optional[List[str]] = None
    ) -> ExecutionPlan:
        """Constructs an ExecutionPlan using heuristics or quick LLM decomposition."""
        is_compound = self.analyze_complexity(user_query)
        clauses = self.split_compound_instruction(user_query) if is_compound else [user_query]

        tasks: List[SubTask] = []
        for i, clause in enumerate(clauses, start=1):
            tasks.append(
                SubTask(
                    step_id=i,
                    description=clause,
                    depends_on_step=(i - 1) if i > 1 else None
                )
            )

        logger.debug(f"Created plan with {len(tasks)} tasks (is_multi_step={len(tasks) > 1})")
        return ExecutionPlan(
            original_query=user_query,
            is_multi_step=(len(tasks) > 1),
            tasks=tasks,
            suggested_tools=available_tools or []
        )
