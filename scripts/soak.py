"""Kill worker at random intervals during a run (soak test support)."""

from __future__ import annotations

import asyncio
import random
import sys
import time

import httpx
from oncall_hero.supervisor.supervisor import supervisor


async def main() -> None:
    """Kill the worker at random intervals while an incident runs.

    Run after triggering a scenario: python scripts/soak.py --runs N
    """
    # Check supervisor status first (fail gracefully if not running)
    try:
        status = await supervisor().status()
        if not status.get("worker", {}).get("running", False):
            print("warning: worker not running; start it with 'ohero up' first")
    except Exception as e:
        print(f"warning: stack check failed: {e}")
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    for r in range(runs):
        print(f"soak run {r+1}/{runs}")
        for _ in range(int(300 / interval)):
            if random.random() < 0.1:
                print("killing worker")
                await supervisor().kill("worker")
                await asyncio.sleep(random.uniform(2, 8))
                await supervisor().start("worker")
            await asyncio.sleep(interval)
        # verify recovery
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get("http://127.0.0.1:9001/ops/executions")
            print("executions:", resp.json())


if __name__ == "__main__":
    asyncio.run(main())
