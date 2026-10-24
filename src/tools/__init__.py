"""JARVIS Consolidated Tool Suite Package.

Exposes all 17 converted tools categorized across 4 modules:
1. web_search (web, wikipedia, research, youtube)
2. code_executor (system apps, volume, files, git, codebase ingest)
3. api_tool (IMAP email & encrypted credentials vault)
4. custom_tool (vision ocr, screenshot, document parser, drafting, math, datetime, memory)
"""

from typing import List, Dict, Any
from src.tools.web_search import TOOL_DEFINITIONS as WEB_TOOLS
from src.tools.code_executor import TOOL_DEFINITIONS as CODE_TOOLS
from src.tools.api_tool import TOOL_DEFINITIONS as API_TOOLS
from src.tools.custom_tool import TOOL_DEFINITIONS as CUSTOM_TOOLS
from src.tools.system_info import TOOL_DEFINITIONS as SYSTEM_TOOLS
from src.tools.second_brain import TOOL_DEFINITIONS as SECOND_BRAIN_TOOLS
from src.tools.github_tool import TOOL_DEFINITIONS as GITHUB_TOOLS
from src.tools.academic_tools import TOOL_DEFINITIONS as ACADEMIC_TOOLS

ALL_TOOLS: List[Dict[str, Any]] = (
    WEB_TOOLS + CODE_TOOLS + API_TOOLS + CUSTOM_TOOLS + SYSTEM_TOOLS + SECOND_BRAIN_TOOLS + GITHUB_TOOLS + ACADEMIC_TOOLS
)


def get_all_tools() -> List[Dict[str, Any]]:
    """Returns the master list of all registered tool definitions and handlers."""
    return list(ALL_TOOLS)


def register_all_tools(orchestrator_instance) -> int:
    """Registers all tools into an orchestrator instance."""
    for tool in ALL_TOOLS:
        orchestrator_instance.register_tool(
            name=tool["name"],
            description=tool["description"],
            handler=tool["handler"],
            parameters=tool.get("parameters")
        )
    return len(ALL_TOOLS)


__all__ = [
    "ALL_TOOLS",
    "get_all_tools",
    "register_all_tools",
    "WEB_TOOLS",
    "CODE_TOOLS",
    "API_TOOLS",
    "CUSTOM_TOOLS",
    "SYSTEM_TOOLS",
    "SECOND_BRAIN_TOOLS",
    "GITHUB_TOOLS",
    "ACADEMIC_TOOLS",
]
