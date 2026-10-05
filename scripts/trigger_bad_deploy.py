"""Triggers a bad deploy scenario from the command line."""

from __future__ import annotations

import asyncio
import json

import httpx


async def main(scenario_id: str = "s1_bad_deploy") -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        result = await client.post(f"http://127.0.0.1:8000/api/scenarios/{scenario_id}/trigger")
        print(json.dumps(result.json(), indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", default="s1_bad_deploy")
    args = parser.parse_args()
    asyncio.run(main(args.scenario))
