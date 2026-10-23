"""Tests for JARVIS System Info & Dynamic Capabilities Tool."""

import pytest
from src.tools.system_info import get_jarvis_capabilities
from src.tools import get_all_tools, register_all_tools
from src.workflows.task_router import TaskRouter
from src.workflows.orchestrator import JarvisOrchestrator


def test_get_jarvis_capabilities_content():
    """Verify that get_jarvis_capabilities returns identity, architecture, limits, and tools."""
    output = get_jarvis_capabilities()
    
    assert "JARVIS" in output
    assert "Arsitektur" in output or "Arsitektur & Identitas" in output
    assert "Kemampuan Utama" in output
    assert "Limitasi & Batasan" in output
    assert "Daftar Lengkap Tool Aktif" in output
    
    # Check that registered tools are listed
    all_tools = get_all_tools()
    for tool in all_tools[:5]:
        assert f"`{tool['name']}`" in output


def test_dynamic_modularity():
    """Verify that adding a new tool dynamically appears in capabilities report without code changes."""
    from src.tools import ALL_TOOLS
    
    mock_tool = {
        "name": "quantum_simulator_tool",
        "description": "Simulasi sirkuit kuantum superkonduktor tingkat lanjut.",
        "parameters": {"type": "object", "properties": {}},
        "handler": lambda query="": "simulated"
    }
    
    # Temporarily append mock tool
    ALL_TOOLS.append(mock_tool)
    try:
        report = get_jarvis_capabilities()
        assert "`quantum_simulator_tool`" in report
        assert "Simulasi sirkuit kuantum superkonduktor" in report
    finally:
        # Clean up
        ALL_TOOLS.remove(mock_tool)


def test_task_router_routes_capabilities():
    """Verify that user queries about capabilities route to get_jarvis_capabilities."""
    router = TaskRouter()
    all_tools = get_all_tools()
    
    queries = [
        "apa saja yang kamu bisa",
        "apa kemampuanmu",
        "kamu bisa apa aja",
        "jelaskan tentang dirimu dan fiturnya",
        "daftar tool yang kamu punya",
        "apa batasan dan limitasi kamu"
    ]
    
    for q in queries:
        routed, scores = router.route_tools(q, all_tools)
        routed_names = [t["name"] for t in routed]
        assert "get_jarvis_capabilities" in routed_names, f"Failed for query: '{q}', got: {routed_names}"


def test_orchestrator_execution():
    """Verify that JarvisOrchestrator has get_jarvis_capabilities registered and can run it."""
    import asyncio
    
    async def _run():
        orchestrator = JarvisOrchestrator()
        tool_names = [t["name"] for t in orchestrator.tool_definitions]
        assert "get_jarvis_capabilities" in tool_names
        
        # Test direct execution of the tool handler
        handler = orchestrator.tool_agent.tool_handlers.get("get_jarvis_capabilities")
        assert handler is not None
        output = handler(query="")
        assert "JARVIS" in output
        assert "Kemampuan Utama" in output

    asyncio.run(_run())
