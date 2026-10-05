"""Kill-worker script for the demo."""

from __future__ import annotations

import asyncio

from oncall_hero.supervisor.supervisor import supervisor


async def main() -> None:
    result = await supervisor().kill("worker")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
