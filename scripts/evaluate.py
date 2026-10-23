import sys
import asyncio
import json
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.evaluation.eval_agents import evaluate_agent
from config.settings import get_logger

logger = get_logger("EvalCLI")


async def main():
    report = await evaluate_agent()
    
    # Save evaluation report to data/processed
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "latest_evaluation_report.json"
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2, ensure_ascii=False)
        
    print(f"\n[JARVIS] Laporan evaluasi disimpan ke: {out_file}")
    print(f"[JARVIS] Success Rate: {report.success_rate_percent}%")
    print(f"[JARVIS] Tool Accuracy: {report.average_tool_accuracy_percent}%")
    print(f"[JARVIS] Average Latency: {report.average_latency_ms:.1f}ms\n")


if __name__ == "__main__":
    asyncio.run(main())
