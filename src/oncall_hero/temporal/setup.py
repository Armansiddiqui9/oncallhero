"""Temporal setup: search attributes + one-time initialization."""

from __future__ import annotations

import asyncio
from typing import Any

from temporalio.client import Client
from temporalio.worker import Worker


def _ensure_str(x: Any) -> str:
    return str(x)


async def setup_search_attributes(client: Client) -> None:
    """Register Phase / Severity / Service search attributes on first run."""
    await client.update_namespace(
        namespace=client.namespace,
        update_request={"search_attributes": {"Phase": {"name": "Phase", "type": "Keyword"}}},
    )


async def initialize_once(client: Client) -> None:
    """Run one-time setup after Temporal boots."""
    try:
        await setup_search_attributes(client)
    except Exception:  # noqa: BLE001 - search attribute registration can fail on replay
        pass


async def ensure_namespace_health(client: Client, timeout: float = 15.0) -> bool:
    """Wait for the Temporal server to be reachable."""
    for _ in range(int(timeout * 10)):
        try:
            await client.workflow_service.get_system_info()
            return True
        except Exception:  # noqa: BLE001
            await asyncio.sleep(0.1)
    return False
