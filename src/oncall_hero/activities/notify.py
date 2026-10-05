"""Notify activities: notify_human writes to the UI feed.

The escalation chain calls notify_human for each level; the UI
shows who was notified and when.
"""

from __future__ import annotations

import json

import httpx
from temporalio import activity

from oncall_hero.models import Plan


@activity.defn
async def notify_human(level: str, plan_json: str) -> dict:
    """Post the plan to the UI notification feed (gateway API)."""
    plan = Plan.model_validate_json(plan_json)
    payload = {
        "level": level,
        "incident_id": activity.info().workflow_id,
        "diagnosis": plan.diagnosis,
        "steps": [s.model_dump() for s in plan.steps],
        "expected_outcome": plan.expected_outcome,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            await client.post("http://127.0.0.1:8000/api/notifications", json=payload)
    except Exception:  # noqa: BLE001 - notification must never block the chain
        activity.logger.warning("notify_human failed (non-fatal)")
    return {"level": level, "sent": True}
