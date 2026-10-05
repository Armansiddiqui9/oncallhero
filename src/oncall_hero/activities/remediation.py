"""Remediation activities: execute_step, run_compensation, check_health.

Idempotency: every mutating activity derives its key from Temporal itself
(workflow_id:activity_id), so retries return the stored result and the
executions counter stays at 1 (G2).
"""

from __future__ import annotations

import json

import httpx
from temporalio import activity

from oncall_hero.chaos import chaos
from oncall_hero.models import Compensation, RemediationStep, StepResult
from oncall_hero.safety.sanitize import sanitize_tool_output


async def _http_post(url: str, body: dict) -> dict:
    settings = chaos()
    import random

    if settings.get("tool_error_rate", 0.0) > 0 and random.random() < settings["tool_error_rate"]:
        raise Exception("chaos: simulated mutation error 500")

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        return resp.json()


def _idempotency_key() -> str:
    info = activity.info()
    return f"{info.workflow_id}:{info.activity_id}"


async def apply_mutation(
    kind: str,
    target: str,
    params: dict,
    idempotency_key: str,
) -> StepResult:
    """Apply a mutating step against the demo world (shop-api)."""
    base = "http://127.0.0.1:9001"
    body = {"idempotency_key": idempotency_key, **params}

    if kind == "rollback_deploy":
        data = await _http_post(f"{base}/ops/rollback", body)
        return StepResult(step_index=0, ok=data.get("ok", False), message=json.dumps(data))
    if kind == "restart_service":
        data = await _http_post(f"{base}/ops/restart", body)
        return StepResult(step_index=0, ok=data.get("ok", False), message=json.dumps(data))
    if kind == "toggle_flag":
        name = target
        data = await _http_post(f"{base}/ops/flags/{name}", body)
        return StepResult(step_index=0, ok=data.get("ok", False), message=json.dumps(data))
    if kind == "start_service":
        # Start a world-group service via the supervisor's HTTP API.
        data = await _http_post(f"http://127.0.0.1:8000/api/services/{target}/start", {})
        return StepResult(step_index=0, ok=True, message=json.dumps(data))
    if kind == "stop_service":
        data = await _http_post(f"http://127.0.0.1:8000/api/services/{target}/stop", {})
        return StepResult(step_index=0, ok=True, message=json.dumps(data))
    raise ValueError(f"unknown mutation kind {kind}")


@activity.defn
async def execute_step(step: RemediationStep) -> StepResult:
    """Execute one remediation step, idempotently."""
    key = _idempotency_key()
    info = activity.info()

    result = await apply_mutation(step.kind, step.target, step.params, key)
    result.step_index = int(info.activity_id.split(":")[-1]) if ":" in info.activity_id else 0
    activity.heartbeat({"key": key, "kind": step.kind, "target": step.target})
    return result


@activity.defn
async def run_compensation(comp: Compensation) -> StepResult:
    """Run one compensation (undo) step, idempotently."""
    key = _idempotency_key()
    result = await apply_mutation(comp.kind, comp.target, comp.params, key)
    activity.heartbeat({"key": key, "comp": comp.kind})
    return result


@activity.defn
async def check_health(service: str, verify_json: str) -> dict:
    """Compare current metrics against the plan's verify spec."""
    from oncall_hero.models import VerifySpec

    spec = VerifySpec.model_validate_json(verify_json)
    metrics = await _http_get(f"http://127.0.0.1:9001/ops/metrics?window={spec.wait_seconds}")

    if spec.metric == "error_rate":
        value = metrics.get("error_rate", 1.0)
        ok = value < spec.threshold
    elif spec.metric == "memory_mb":
        value = metrics.get("memory_mb", 9999.0)
        ok = value < spec.threshold
    elif spec.metric == "p95_latency_ms":
        value = metrics.get("p95_latency_ms", 9999.0)
        ok = value < spec.threshold
    elif spec.metric == "checkout_ok":
        try:
            checkout = await _http_get("http://127.0.0.1:9001/checkout")
            ok = checkout.get("status") == "ok"
        except Exception:
            ok = False
        value = 0.0 if ok else 1.0
    else:
        ok = False
        value = None

    return {
        "metric": spec.metric,
        "value": value,
        "threshold": spec.threshold,
        "recovered": ok,
    }
