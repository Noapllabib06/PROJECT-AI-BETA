"""Metrics and Evaluation Reporting for JARVIS AI Agent."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class TestCaseResult(BaseModel):
    test_case_id: str
    category: str
    query: str
    passed: bool
    latency_ms: float
    expected_tools: List[str] = Field(default_factory=list)
    actual_tools: List[str] = Field(default_factory=list)
    tool_accuracy: float = 1.0
    keyword_match: bool = True
    response: str = ""
    error: Optional[str] = None


class EvaluationReport(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    total_cases: int = 0
    passed_cases: int = 0
    success_rate_percent: float = 0.0
    average_tool_accuracy_percent: float = 0.0
    average_latency_ms: float = 0.0
    category_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    results: List[TestCaseResult] = Field(default_factory=list)


def calculate_metrics(results: List[TestCaseResult]) -> EvaluationReport:
    """Computes aggregate performance metrics across test case results."""
    total = len(results)
    if total == 0:
        return EvaluationReport()

    passed = sum(1 for r in results if r.passed)
    avg_accuracy = sum(r.tool_accuracy for r in results) / total * 100.0
    avg_latency = sum(r.latency_ms for r in results) / total

    breakdown: Dict[str, Dict[str, Any]] = {}
    for r in results:
        cat = r.category
        if cat not in breakdown:
            breakdown[cat] = {"total": 0, "passed": 0, "latencies": []}
        breakdown[cat]["total"] += 1
        if r.passed:
            breakdown[cat]["passed"] += 1
        breakdown[cat]["latencies"].append(r.latency_ms)

    formatted_breakdown = {}
    for cat, data in breakdown.items():
        cat_total = data["total"]
        cat_passed = data["passed"]
        cat_rate = (cat_passed / cat_total * 100.0) if cat_total > 0 else 0.0
        cat_avg_lat = sum(data["latencies"]) / len(data["latencies"]) if data["latencies"] else 0.0
        formatted_breakdown[cat] = {
            "total": cat_total,
            "passed": cat_passed,
            "success_rate": f"{cat_rate:.1f}%",
            "avg_latency_ms": f"{cat_avg_lat:.1f}ms"
        }

    return EvaluationReport(
        total_cases=total,
        passed_cases=passed,
        success_rate_percent=round(passed / total * 100.0, 2),
        average_tool_accuracy_percent=round(avg_accuracy, 2),
        average_latency_ms=round(avg_latency, 2),
        category_breakdown=formatted_breakdown,
        results=results
    )
