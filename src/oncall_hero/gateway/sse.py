"""SSE helpers: Server-Sent Events streams for live updates."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

from fastapi.responses import StreamingResponse

_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
_incident_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)


async def publish(channel: str, data: Any) -> None:
    """Publish to all subscribers on a channel."""
    for q in _subscribers.get(channel, []):
        await q.put(data)


def subscribe(channel: str) -> StreamingResponse:
    """Return an SSE response for a channel."""

    async def event_stream() -> Any:
        q: asyncio.Queue = asyncio.Queue()
        _subscribers[channel].append(q)
        try:
            while True:
                data = await q.get()
                yield f"data: {json.dumps(data, default=str)}\n\n"
        finally:
            _subscribers[channel].remove(q)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def incident_stream(incident_id: str) -> StreamingResponse:
    """SSE stream for a single incident (polls history ~1/s)."""
    from oncall_hero.config import load_config
    from oncall_hero.temporal.history import history_to_timeline
    from temporalio.client import Client
    from temporalio.contrib.pydantic import pydantic_data_converter

    config = load_config()
    q: asyncio.Queue = asyncio.Queue()
    _incident_subscribers[incident_id].append(q)

    async def poll() -> None:
        try:
            client = await Client.connect(
                config.temporal_address,
                namespace=config.namespace,
                data_converter=pydantic_data_converter,
            )
            handle = client.get_workflow_handle(incident_id)
            while True:
                try:
                    desc = await handle.describe()
                    history = await handle.fetch_workflow_history()
                    timeline = history_to_timeline(history)
                    await q.put({"status": desc.status.name, "history": timeline})
                except Exception as e:  # noqa: BLE001
                    await q.put({"error": str(e)})
                await asyncio.sleep(1)
        except Exception:  # noqa: BLE001
            pass

    asyncio.create_task(poll())

    async def event_stream() -> Any:
        try:
            while True:
                data = await q.get()
                yield f"data: {json.dumps(data, default=str)}\n\n"
        finally:
            if q in _incident_subscribers.get(incident_id, []):
                _incident_subscribers[incident_id].remove(q)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
