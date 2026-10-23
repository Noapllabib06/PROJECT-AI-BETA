"""Automated Evaluation Runner for JARVIS Agents."""

import time
import asyncio
from typing import List, Optional
from src.evaluation.test_cases import BENCHMARK_TEST_CASES, EvaluationTestCase
from src.evaluation.metrics import TestCaseResult, EvaluationReport, calculate_metrics
from src.workflows.orchestrator import orchestrator, JarvisOrchestrator
from config.settings import get_logger

logger = get_logger("Evaluation")


async def evaluate_agent(
    target_orchestrator: Optional[JarvisOrchestrator] = None,
    test_cases: Optional[List[EvaluationTestCase]] = None
) -> EvaluationReport:
    """Executes benchmark test cases against the agent orchestrator and calculates performance metrics."""
    orch = target_orchestrator or orchestrator
    cases = test_cases or BENCHMARK_TEST_CASES
    results: List[TestCaseResult] = []

    logger.info(f"Starting Agent Evaluation with {len(cases)} test cases...")

    for i, tc in enumerate(cases, 1):
        logger.info(f"[{i}/{len(cases)}] Running test case: {tc.id} ({tc.category})")
        start_time = time.perf_counter()
        
        try:
            res = await orch.execute_query(user_query=tc.query)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Evaluate tool selection accuracy
            expected_set = set(tc.expected_tools)
            actual_set = set(res.tools_used)

            if not expected_set and not actual_set:
                tool_accuracy = 1.0
            elif not expected_set or not actual_set:
                # One is empty and other is not
                tool_accuracy = 0.5 if not expected_set else 0.0
            else:
                intersection = len(expected_set.intersection(actual_set))
                union = len(expected_set.union(actual_set))
                tool_accuracy = intersection / union if union > 0 else 1.0

            # Evaluate keyword matching
            keyword_match = True
            if tc.expected_keywords:
                resp_lower = res.response.lower()
                keyword_match = any(kw.lower() in resp_lower for kw in tc.expected_keywords)

            # Determine pass condition
            passed = res.success and (tool_accuracy >= 0.5) and keyword_match

            test_result = TestCaseResult(
                test_case_id=tc.id,
                category=tc.category,
                query=tc.query,
                passed=passed,
                latency_ms=round(latency_ms, 2),
                expected_tools=tc.expected_tools,
                actual_tools=res.tools_used,
                tool_accuracy=round(tool_accuracy, 2),
                keyword_match=keyword_match,
                response=res.response,
                error=res.error
            )
            results.append(test_result)
            status_symbol = "✅ PASSED" if passed else "❌ FAILED"
            logger.info(f"[{tc.id}] {status_symbol} ({latency_ms:.1f}ms) | Tools: {res.tools_used}")

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"[{tc.id}] Exception: {e}")
            results.append(TestCaseResult(
                test_case_id=tc.id,
                category=tc.category,
                query=tc.query,
                passed=False,
                latency_ms=round(latency_ms, 2),
                expected_tools=tc.expected_tools,
                actual_tools=[],
                tool_accuracy=0.0,
                keyword_match=False,
                error=str(e)
            ))

    report = calculate_metrics(results)
    logger.info("=" * 60)
    logger.info(f"📊 Evaluation Complete: Success Rate = {report.success_rate_percent}%")
    logger.info(f"   Avg Tool Accuracy = {report.average_tool_accuracy_percent}% | Avg Latency = {report.average_latency_ms}ms")
    logger.info("=" * 60)
    return report
