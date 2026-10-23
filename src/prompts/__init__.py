"""JARVIS Prompts and Templates Package."""
from src.prompts.system_prompts import (
    PERSONA,
    TOOL_DECISION_RULES,
    GENERAL_ANSWER_RULES,
    NEGATIVE_EXAMPLES,
    SYNTHESIS_SYSTEM_PROMPT,
)
from src.prompts.templates import (
    TOOL_EXAMPLES,
    build_few_shot_examples,
    build_tools_description,
    build_system_prompt,
    build_error_feedback_prompt,
)

__all__ = [
    "PERSONA",
    "TOOL_DECISION_RULES",
    "GENERAL_ANSWER_RULES",
    "NEGATIVE_EXAMPLES",
    "SYNTHESIS_SYSTEM_PROMPT",
    "TOOL_EXAMPLES",
    "build_few_shot_examples",
    "build_tools_description",
    "build_system_prompt",
    "build_error_feedback_prompt",
]
