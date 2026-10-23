"""Verification test script for Phase 3 (Prompts & Agents)."""
import os
import sys
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.prompts import build_system_prompt, build_few_shot_examples, build_error_feedback_prompt
from src.agents import OutputParser, ToolCall, PlannerAgent, ToolAgent, SupervisorAgent

def run_tests():
    print("--- 1. Testing System Prompts & Dynamic Templates ---")
    sp = build_system_prompt(
        relevant_tools=[{"name": "search_web", "description": "Cari info web"}],
        facts=["User: Naufal"]
    )
    assert "JARVIS" in sp
    assert "Cari info web" in sp
    assert "User: Naufal" in sp
    print("[PASS] System Prompt Builder verified.")

    print("\n--- 2. Testing Pydantic v2 OutputParser ---")
    # Test valid array
    raw1 = '[{"tool": "search_web", "query": "berita teknologi terbaru"}]'
    res1 = OutputParser.parse_and_validate(raw1, valid_tools=["search_web", "read_file"])
    assert res1.success is True
    assert len(res1.data) == 1
    assert res1.data[0].tool == "search_web"
    assert res1.data[0].query == "berita teknologi terbaru"

    # Test markdown code block with parameters
    raw2 = 'Tentu, ini hasilnya:\n```json\n{"tool": "check_email", "sender": "paimon", "date": "14/8/2026"}\n```'
    res2 = OutputParser.parse_and_validate(raw2, valid_tools=["check_email"])
    assert res2.success is True
    assert res2.data[0].parameters.get("sender") == "paimon"

    # Test invalid JSON and error feedback prompt
    res_bad = OutputParser.parse_and_validate("Bukan JSON sama sekali")
    assert res_bad.success is False
    feedback = build_error_feedback_prompt("Bukan JSON", res_bad.error or "")
    assert "OUTPUT TIDAK VALID" in feedback
    print("[PASS] Pydantic v2 OutputParser & Self-Correction Feedback verified.")

    print("\n--- 3. Testing PlannerAgent ---")
    planner = PlannerAgent()
    plan = planner.create_plan("cari cuaca jakarta lalu putar lagu jazz")
    assert plan.is_multi_step is True
    assert len(plan.tasks) == 2
    print(f"[PASS] PlannerAgent verified (tasks: {len(plan.tasks)}).")

    print("\n--- 4. Testing ToolAgent & SupervisorAgent ---")
    tool_agent = ToolAgent()
    tool_agent.register_tool("mock_tool", lambda query: f"MOCK OUTPUT: {query}")
    res = asyncio.run(tool_agent.execute_tool_call(ToolCall(tool="mock_tool", query="test_query")))
    assert res.success is True
    assert "test_query" in res.output

    supervisor = SupervisorAgent()
    final_res = supervisor.synthesize_tool_results(
        user_query="apa itu",
        results=[res],
        llm_synthesis="Header: Hasil\nBody: Selesai!"
    )
    assert "Header:" not in final_res.final_text
    assert "Body:" not in final_res.final_text
    assert len(final_res.traces) > 0
    print("[PASS] ToolAgent execution and SupervisorAgent sanitization verified.")

    print("\n>>> FASE 3 VERIFIKASI BERHASIL 100% <<<")

if __name__ == "__main__":
    run_tests()
