"""Verification test script for Phase 4 (Workflows & Orchestration)."""
import os
import sys
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.workflows import TaskRouter, JarvisOrchestrator, OrchestrationResult
from src.agents import BaseAgent

class MockLLMAgent(BaseAgent):
    """Mock LLM returning deterministic responses for test suite."""
    async def a_chat(self, messages, system_prompt=None, temperature=None):
        last_msg = messages[-1]["content"].lower()
        if "kalkulator" in last_msg:
            return '[{"tool": "open_app", "query": "kalkulator"}]'
        elif "cuaca" in last_msg:
            return '[{"tool": "mock_weather", "query": "Bandung"}]'
        return '{"tool": "chat", "query": "Halo, ada yang bisa saya bantu?"}'

    async def a_generate(self, prompt, system_prompt=None, temperature=None):
        return "Berdasarkan data cuaca, suhu di Bandung saat ini adalah 24 derajat Celsius berawan."


def run_tests():
    print("--- 1. Testing TaskRouter & Intent Detection ---")
    router = TaskRouter()

    # Test sensitive routing
    assert router.is_sensitive("simpan password fb saya 123456") is True
    assert router.is_sensitive("gimana kabar hari ini") is False

    # Test forced web search
    assert router.requires_forced_web_search("siapa presiden indonesia saat ini?") is True
    assert router.requires_forced_web_search("apa status kamu jarvis?") is False

    # Test tool routing
    tools = [
        {"name": "open_app", "description": "Buka aplikasi desktop"},
        {"name": "search_web", "description": "Cari informasi web"},
        {"name": "check_email", "description": "Cek inbox email"},
    ]
    routed, scores = router.route_tools("buka kalkulator di laptop", tools)
    routed_names = [t["name"] for t in routed]
    assert "open_app" in routed_names
    print(f"[PASS] TaskRouter routed: {routed_names} (scores: {scores})")

    print("\n--- 2. Testing JarvisOrchestrator End-to-End ---")
    mock_llm = MockLLMAgent()
    orch = JarvisOrchestrator(base_agent=mock_llm)

    # Register mock weather tool
    orch.register_tool(
        name="mock_weather",
        description="Mengecek kondisi cuaca",
        handler=lambda query: f"Cuaca di {query}: 24°C Berawan"
    )

    traces_received = []
    def on_trace(event):
        traces_received.append(event["step"])

    # Run query through orchestrator
    result: OrchestrationResult = asyncio.run(
        orch.execute_query("bagaimana cuaca di bandung hari ini?", on_trace=on_trace)
    )

    assert result.success is True
    assert "mock_weather" in result.tools_used
    assert "Bandung" in result.response or "24" in result.response
    assert len(traces_received) > 0
    print(f"[PASS] Orchestrator executed successfully!")
    print(f"Tools used: {result.tools_used}")
    print(f"Traces captured: {traces_received}")
    print(f"Final response:\n{result.response}")

    print("\n>>> FASE 4 VERIFIKASI BERHASIL 100% <<<")


if __name__ == "__main__":
    run_tests()
