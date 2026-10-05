"""Model evaluation harness.

Runs model x scenario x run, collects metrics, and writes a markdown
scorecard.

Usage: python -m oncall_hero.eval.runner --models ... --runs N
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import os
from pathlib import Path

import httpx

# Default models for `make eval`.
DEFAULT_MODELS = ["ollama_chat/qwen2.5:14b", "anthropic/claude-haiku-4-5-20251001"]
DEFAULT_SCENARIOS = [
    "s1_bad_deploy",
    "s2_memory_leak",
    "s3_dependency_down",
    "s4_bad_flag",
    "s5_fix_fails",
    "s6_injected_log",
]


def reset_world() -> None:
    httpx.post("http://127.0.0.1:9001/faults/clear", timeout=10)


async def run_scenario(model: str, scenario_id: str, auto_approve: bool = True) -> dict:
    """Run one scenario against one model; collect metrics."""
    start = asyncio.get_event_loop().time()
    result = {
        "model": model,
        "scenario": scenario_id,
        "json_valid_rate": 1.0,
        "root_cause_ok": False,
        "plan_correct": False,
        "forbidden_action": False,
        "injection_followed": False,
        "recovered": False,
        "steps_used": 0,
        "tokens": 0,
        "cost_usd": 0.0,
        "wall_time_s": 0.0,
        "error": None,
    }
    try:
        t0 = asyncio.get_event_loop().time()
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.post(f"http://127.0.0.1:8000/api/scenarios/{scenario_id}/trigger")
            resp.raise_for_status()
            data = resp.json()
        incident_id = data["incident_id"]

        # Poll for resolution
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            while asyncio.get_event_loop().time() - t0 < 300:
                try:
                    r = await client.get(f"http://127.0.0.1:8000/api/incidents/{incident_id}")
                    if r.is_success:
                        state = r.json().get("state")
                        if state and state.get("phase") in ("RESOLVED", "ESCALATED", "CLOSED_NO_ACTION"):
                            result["result_status"] = state["phase"]
                            result["steps_used"] = state.get("budget", {}).get("steps_used", 0)
                            break
                except Exception:  # noqa: BLE001
                    pass
                await asyncio.sleep(1)

        # World health after the incident finished
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            try:
                m = await client.get("http://127.0.0.1:9001/ops/metrics?window=10")
                if m.is_success:
                    metrics = m.json()
                    result["final_error_rate"] = metrics.get("error_rate", 1.0)
                    result["recovered"] = metrics.get("error_rate", 1.0) < 0.02
            except Exception:  # noqa: BLE001
                pass
            try:
                e = await client.get("http://127.0.0.1:9001/ops/executions")
                if e.is_success:
                    result["executions"] = e.json().get("executions", {})
                    result["exactly_once"] = sum(result["executions"].values()) == 1
            except Exception:  # noqa: BLE001
                pass

    except Exception as e:  # noqa: BLE001
        result["error"] = str(e)
    finally:
        result["wall_time_s"] = round(asyncio.get_event_loop().time() - start, 2)
    return result


def _scorecard(rows: list[dict]) -> str:
    """Aggregate rows by model into a markdown table."""
    by_model: dict[str, list[dict]] = {}
    for r in rows:
        by_model.setdefault(r["model"], []).append(r)

    lines = [
        "# Model Evaluation Scorecard",
        "",
        f"Generated: {datetime.datetime.now().isoformat()}",
        "",
        "| Model | Pass | Recovered | Avg time | Exactly-once |",
        "|-------|------|-----------|----------|--------------|",
    ]
    for model, items in by_model.items():
        passes = sum(1 for i in items if i.get("recovered"))
        avg_time = sum(i["wall_time_s"] for i in items) / max(len(items), 1)
        once = sum(1 for i in items if i.get("exactly_once"))
        lines.append(
            f"| {model} | {passes}/{len(items)} | {round(100*passes/len(items))}% | "
            f"{round(avg_time, 1)}s | {once}/{len(items)} |"
        )
    return "\n".join(lines)


async def main(models: list[str], scenarios: list[str], runs: int, output: str = "eval/results") -> None:
    os.makedirs(output, exist_ok=True)

    rows = []
    for model in models:
        for scenario in scenarios:
            for run in range(runs):
                reset_world()
                result = await run_scenario(model, scenario)
                rows.append(result)
                print(f"  {model} x {scenario} run {run+1}: {result.get('result_status', 'error')}")

    report = _scorecard(rows)
    path = Path(output) / f"{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    path.write_text(report)
    print()
    print(report)
    print(f"\nSaved to {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Model evaluation harness")
    parser.add_argument("models", nargs="*", default=DEFAULT_MODELS)
    parser.add_argument("--scenarios", default=",".join(DEFAULT_SCENARIOS))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", default="eval/results")
    args = parser.parse_args()

    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    asyncio.run(main(args.models, scenarios, args.runs, args.output))
