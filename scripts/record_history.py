"""Record a workflow's event history into tests/histories/ for replay tests."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path

import httpx
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.api.enums.v1 import EventType as _EventType


def _attribute_name(event_type: int) -> str:
    """Map an EventType to its oneof attribute field (e.g. timer_fired_event_attributes)."""
    name = _EventType.GetName(event_type).replace("EVENT_TYPE_", "")
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return f"{snake}_event_attributes"


async def main(scenario_id: str = "s1_bad_deploy", out_dir: str = "tests/histories") -> None:
    out = Path(out_dir) / f"{scenario_id}.json"
    client = await Client.connect("127.0.0.1:7233", namespace="default", data_converter=pydantic_data_converter)
    handle = None
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as http_client:
        while time.perf_counter() - start < 60:
            try:
                r = await http_client.get("http://127.0.0.1:8000/api/incidents")
                incs = (await r.json()).get("incidents", [])
                if incs:
                    handle = client.get_workflow_handle(incs[0]["workflow_id"])
                    break
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(0.5)
        if handle is None:
            raise TimeoutError("no incident appeared")

    hist = await handle.fetch_workflow_history()
    data = []
    for event in hist.events:
        entry = {
            "event_type": _EventType.GetName(event.event_type),
            "event_id": event.event_id,
            "timestamp": event.event_time.isoformat() if event.event_time else None,
        }
        attrs = getattr(event, _attribute_name(event.event_type), None)
        if event.event_type == _EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED and attrs and attrs.result:
            entry["result"] = attrs.result.decode()[:500]
        elif event.event_type == _EventType.EVENT_TYPE_ACTIVITY_TASK_FAILED and attrs and attrs.failure:
            entry["failure"] = attrs.failure.failure_message[:300]
        data.append(entry)

    with out.open("w") as fh:
        json.dump(data, fh, indent=2)
    print(f"saved {out}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", default="s1_bad_deploy")
    parser.add_argument("--out", default="tests/histories")
    args = parser.parse_args()
    asyncio.run(main(args.scenario, args.out))
