"""Integration tests: real shop-api + worker + dev server, scripted LLM."""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from oncall_hero.models import Alert, ApprovalDecision
from oncall_hero.supervisor.supervisor import supervisor

pytestmark = pytest.mark.asyncio


async def _wait_for_phase(client: Client, incident_id: str, phase: str, timeout: float = 30.0) -> dict:
    handle = client.get_workflow_handle(incident_id)
    start = time.perf_counter()
    while time.perf_counter() - start < timeout:
        try:
            state = await handle.query("status")
            if state.get("phase") == phase:
                return state
        except Exception:  # noqa: BLE001 - worker may be starting
            pass
        await asyncio.sleep(0.5)
    raise TimeoutError(f"phase {phase} not reached")


async def test_kill_worker_mid_run_still_resolves() -> None:
    """Durability proof: kill the worker mid-run, restart, incident resolves."""
    # This test requires a running stack; skip if unavailable.
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
            await client.get("http://127.0.0.1:9001/healthz")
    except Exception:  # noqa: BLE001
        pytest.skip("shop-api not running; start the stack first")

    client = await Client.connect("127.0.0.1:7233", namespace="default", data_converter=pydantic_data_converter)

    # Trigger S1
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as http:
        resp = await http.post("http://127.0.0.1:8000/api/scenarios/s1_bad_deploy/trigger")
        data = resp.json()
    incident_id = data["incident_id"]

    # Wait for INVESTIGATE, then kill the worker
    await _wait_for_phase(client, incident_id, "INVESTIGATE")
    await supervisor().kill("worker")
    await asyncio.sleep(3)
    await supervisor().start("worker")

    # Wait for AWAITING_APPROVAL and approve
    await _wait_for_phase(client, incident_id, "AWAITING_APPROVAL", timeout=60)
    handle = client.get_workflow_handle(incident_id)
    await handle.execute_update("approve", ApprovalDecision(approved=True))

    result = await handle.result()
    assert result.status.value == "RESOLVED"

    # Exactly-once proof
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as http:
        resp = await http.get("http://127.0.0.1:9001/ops/executions")
        executions = (resp.json())["executions"]
    assert sum(executions.values()) == 1


async def test_duplicate_mutation_executes_once() -> None:
    """Sending the same mutation twice with the same key executes once."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
            await client.get("http://127.0.0.1:9001/healthz")
    except Exception:  # noqa: BLE001
        pytest.skip("shop-api not running")

    key = "test-duplicate-key-123"
    body = {"to_version": "2.4.0", "idempotency_key": key}
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
        await client.post("http://127.0.0.1:9001/ops/rollback", json=body)
        await client.post("http://127.0.0.1:9001/ops/rollback", json=body)
        resp = await client.get("http://127.0.0.1:9001/ops/executions")
        executions = (resp.json())["executions"]
    assert executions.get(key) == 1
