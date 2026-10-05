"""Gateway routes: scenarios + incidents."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from oncall_hero.config import load_config
from oncall_hero.models import Alert, ApprovalDecision, ApprovalRejection
from oncall_hero.supervisor.supervisor import supervisor
from oncall_hero.temporal.history import history_to_timeline
from oncall_hero.workflow_config import WorkflowConfig

config = load_config()

router = APIRouter()

SCENARIOS_DIR = Path("scenarios")


def _load_scenarios() -> dict:
    """Load scenario YAMLs; skip malformed files gracefully."""
    scenarios: dict = {}
    if SCENARIOS_DIR.exists():
        import yaml
        for f in sorted(SCENARIOS_DIR.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text())
                if isinstance(data, dict) and "id" in data:
                    scenarios[data["id"]] = data
            except Exception:
                continue  # malformed YAML skipped gracefully
    return scenarios


@router.get("/scenarios")
async def list_scenarios() -> dict:
    return {"scenarios": _load_scenarios()}


@router.post("/scenarios/{scenario_id}/trigger")
async def trigger_scenario(scenario_id: str) -> dict:
    """Ensure stack, inject fault, fire alert, start incident."""
    scenarios = _load_scenarios()
    if scenario_id not in scenarios:
        raise HTTPException(status_code=404, detail=f"unknown scenario {scenario_id}")
    scenario = scenarios[scenario_id]

    # 1. Ensure the stack is running (lazy start on trigger)
    ensure = await supervisor().ensure(["temporal", "worker", "shop-api"])
    if any("failed" in str(v).lower() or "timeout" in str(v).lower() for v in ensure.values()):
        raise HTTPException(status_code=503, detail=f"stack failed to start: {ensure}")

    # 2. Inject faults into the demo world
    for setup in scenario.get("setup", []):
        fault = setup["fault"]
        params = setup.get("params", {})
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            await client.post(f"http://127.0.0.1:9001/faults/{fault}", json={"params": params})

    # 3. Fire the alert: start the IncidentWorkflow
    alert = Alert(
        alert_id=f"alert-{scenario_id}-{int(time.time())}",
        service=scenario["alert"]["service"],
        severity=scenario["alert"].get("severity", "high"),
        summary=scenario["alert"]["summary"],
        source="scenario",
    )

    client = await Client.connect(
        config.temporal_address,
        namespace=config.namespace,
        data_converter=pydantic_data_converter,
    )
    # Config is resolved here (outside the workflow) and passed in as data,
    # because workflow code must not read config.yaml.
    handle = await client.start_workflow(
        "IncidentWorkflow.run",
        args=[alert, config.workflow_config(), scenario_id],
        id=f"incident-{alert.service}-{alert.alert_id}",
        task_queue=config.task_queue,
        id_conflict_policy="USE_EXISTING",
    )

    return {
        "incident_id": handle.id,
        "alert": alert.model_dump(),
        "scenario": scenario_id,
        "stack": ensure,
        "workflow_url": f"http://127.0.0.1:8233/namespaces/default/workflows/{handle.id}",
    }


@router.post("/scenarios/reset")
async def reset_scenarios() -> dict:
    """Clear faults, restore world."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
        await client.post("http://127.0.0.1:9001/faults/clear")
    return {"reset": True}


@router.get("/incidents")
async def list_incidents(phase: str | None = None, service: str | None = None) -> dict:
    """List incidents via visibility (works without a worker)."""
    client = await Client.connect(
        config.temporal_address,
        namespace=config.namespace,
        data_converter=pydantic_data_converter,
    )
    query = "WorkflowType = 'IncidentWorkflow'"
    if phase:
        query += f" AND Phase = '{phase}'"
    if service:
        query += f" AND Service = '{service}'"
    try:
        workflows = await client.list_workflows(query=query)
        return {
            "incidents": [
                {
                    "workflow_id": w.workflow_id,
                    "status": w.status.name,
                    "start_time": w.start_time.isoformat() if w.start_time else None,
                }
                for w in workflows
            ]
        }
    except Exception as e:  # noqa: BLE001 - visibility may be unavailable
        return {"incidents": [], "error": str(e)}


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str) -> dict:
    """Incident state: describe + history (+ query if worker up)."""
    client = await Client.connect(
        config.temporal_address,
        namespace=config.namespace,
        data_converter=pydantic_data_converter,
    )
    try:
        handle = client.get_workflow_handle(incident_id)
        desc = await handle.describe()
        history = await handle.fetch_workflow_history()
        timeline = history_to_timeline(history)

        # Try to query live state (works only if worker is up)
        state = None
        try:
            state = await handle.query("status")
        except Exception:  # noqa: BLE001
            pass

        return {
            "incident_id": incident_id,
            "status": desc.status.name,
            "history": timeline,
            "state": state,
            "worker_online": state is not None,
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents/{incident_id}/events")
async def incident_events(incident_id: str):
    """SSE stream: poll history and describe about once per second."""
    from oncall_hero.gateway.sse import incident_stream

    return incident_stream(incident_id)


@router.post("/incidents/{incident_id}/approve")
async def approve_incident(incident_id: str, body: dict) -> dict:
    """Approve (optionally with edited steps) via update."""
    client = await Client.connect(
        config.temporal_address,
        namespace=config.namespace,
        data_converter=pydantic_data_converter,
    )
    handle = client.get_workflow_handle(incident_id)
    decision = ApprovalDecision(
        approved=True,
        steps=body.get("steps"),
        comment=body.get("comment", ""),
    )
    try:
        result = await handle.execute_update("approve", decision)
        return {"approved": True, "result": result}
    except Exception as e:  # noqa: BLE001 - validator errors surface here
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/incidents/{incident_id}/reject")
async def reject_incident(incident_id: str, body: dict) -> dict:
    client = await Client.connect(
        config.temporal_address,
        namespace=config.namespace,
        data_converter=pydantic_data_converter,
    )
    handle = client.get_workflow_handle(incident_id)
    try:
        result = await handle.execute_update("reject", body.get("reason", "rejected"))
        return {"rejected": True, "result": result}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/incidents/{incident_id}/pause")
async def pause_incident(incident_id: str) -> dict:
    client = await Client.connect(
        config.temporal_address,
        namespace=config.namespace,
        data_converter=pydantic_data_converter,
    )
    handle = client.get_workflow_handle(incident_id)
    await handle.signal("pause")
    return {"paused": True}


@router.post("/incidents/{incident_id}/resume")
async def resume_incident(incident_id: str) -> dict:
    client = await Client.connect(
        config.temporal_address,
        namespace=config.namespace,
        data_converter=pydantic_data_converter,
    )
    handle = client.get_workflow_handle(incident_id)
    await handle.signal("resume")
    return {"resumed": True}


@router.post("/incidents/{incident_id}/note")
async def add_note(incident_id: str, body: dict) -> dict:
    client = await Client.connect(
        config.temporal_address,
        namespace=config.namespace,
        data_converter=pydantic_data_converter,
    )
    handle = client.get_workflow_handle(incident_id)
    await handle.signal("add_note", body.get("text", ""))
    return {"noted": True}


@router.post("/incidents/{incident_id}/cancel")
async def cancel_incident(incident_id: str) -> dict:
    client = await Client.connect(
        config.temporal_address,
        namespace=config.namespace,
        data_converter=pydantic_data_converter,
    )
    handle = client.get_workflow_handle(incident_id)
    await handle.signal("cancel_incident")
    return {"cancel_requested": True}


@router.get("/incidents/{incident_id}/postmortem")
async def get_postmortem(incident_id: str) -> dict:
    path = Path("postmortems") / f"{incident_id}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="postmortem not written yet")
    return {"incident_id": incident_id, "markdown": path.read_text(errors="replace")}


@router.post("/webhook/alert")
async def webhook_alert(payload: dict) -> dict:
    """Generic alert intake (Alertmanager-like JSON)."""
    alert = Alert(
        alert_id=payload.get("alert_id", "webhook-alert"),
        service=payload.get("service", "shop-api"),
        severity=payload.get("severity", "high"),
        summary=payload.get("summary", "webhook alert"),
        source="webhook",
    )
    client = await Client.connect(
        config.temporal_address,
        namespace=config.namespace,
        data_converter=pydantic_data_converter,
    )
    handle = await client.start_workflow(
        "IncidentWorkflow.run",
        args=[alert, config.workflow_config(), ""],
        id=f"incident-{alert.service}-{alert.alert_id}",
        task_queue=config.task_queue,
        id_conflict_policy="USE_EXISTING",
    )
    return {"incident_id": handle.id, "alert": alert.model_dump()}
