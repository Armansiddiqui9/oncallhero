"""Tool activities: query_logs, query_metrics, get_recent_deploys, get_service_status, search_runbooks, finish.

All I/O lives here; the workflow only orchestrates. Chaos settings are read at call time
so changes in .run/chaos.json take effect instantly across processes.
"""

from __future__ import annotations

import asyncio
import json
import random
import urllib.parse
from datetime import datetime, timezone

import httpx
from temporalio import activity

from oncall_hero.chaos import chaos
from oncall_hero.models import Action, Observation
from oncall_hero.safety.sanitize import sanitize_tool_output

activity_logger = activity.logger


async def _http_get(url: str) -> dict:
    """Execute an HTTP GET with chaos injection."""
    settings = chaos()
    roll = random.random()

    if settings.get("tool_error_rate", 0.0) > 0 and roll < settings["tool_error_rate"]:
        raise Exception("chaos: simulated tool error 500")

    if settings.get("tool_latency_ms", 0) > 0 and roll < settings.get("tool_latency_ms", 0) / 1000.0:
        await asyncio.sleep(settings["tool_latency_ms"] / 1000.0)

    async with httpx.AsyncClient(timeout=httpx.Timeout(25.0)) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def query_logs(service: str, level: str | None, q: str | None, last_minutes: int) -> dict:
    cutoff = (datetime.now(timezone.utc).timestamp() - last_minutes * 60) if last_minutes else 0.0
    url = f"http://127.0.0.1:9001/ops/logs?limit=100"
    if level:
        url += f"&level={level}"
    if q:
        url += f"&q={urllib.parse.quote(q)}"
    try:
        data = await _http_get(url)
        lines = data.get("logs", [])
        if cutoff:
            lines = [l for l in lines if l.get("timestamp", 0) >= cutoff]
        detail = "\n".join(f"{l['iso']} [{l['level']}] {l['message']}" for l in lines[:100])
        return {"service": service, "count": len(lines), "detail": detail}
    except Exception:
        detail = "shop-api unreachable (check the service is running)"
        return {"service": service, "count": 0, "detail": detail}


async def query_metrics(service: str, window_minutes: int) -> dict:
    url = f"http://127.0.0.1:9001/ops/metrics?window={window_minutes}"
    data = await _http_get(url)
    return {
        "service": service,
        "error_rate": data.get("error_rate"),
        "p95_latency_ms": data.get("p95_latency_ms"),
        "memory_mb": data.get("memory_mb"),
        "rps": data.get("rps"),
        "current_version": data.get("current_version"),
        "faults": data.get("faults"),
    }


async def get_recent_deploys(service: str, limit: int) -> dict:
    url = f"http://127.0.0.1:9001/ops/deploys"
    data = await _http_get(url)
    deploys = data.get("deploys", [])[:limit]
    return {"service": service, "current_version": data.get("current_version"), "deploys": deploys}


async def get_service_status(service: str) -> dict:
    from httpx import RequestError

    flags = None
    if service == "shop-api":
        try:
            flags = await _http_get("http://127.0.0.1:9001/ops/flags")
        except Exception:
            flags = {}
    return {
        "service": service,
        "status": "ok" if service == "shop-api" else "unknown",
        "version": "2.4.1" if service == "shop-api" else None,
        "flags": flags,
    }


async def search_runbooks(query: str) -> dict:
    from pathlib import Path

    matches: list[dict] = []
    runbooks_dir = Path(__file__).parent.parent.parent.parent / "runbooks"
    if not runbooks_dir.exists():
        runbooks_dir = Path("runbooks")
    for file in runbooks_dir.glob("*.md"):
        text = file.read_text(errors="replace")
        if query.lower() in text.lower():
            matches.append({"file": file.name, "content": text[:2000]})
    return {"query": query, "matches": matches}


async def finish(diagnosis: str, confidence: float) -> Observation:
    return Observation(action_kind="finish", summary=diagnosis, detail=json.dumps({"confidence": confidence}))


async def run_tool(action: Action) -> Observation:
    """Execute one tool action and return an Observation for the prompt history."""
    kind = action.kind
    args = action.args

    # Chaos: tool errors.
    settings = chaos()
    if settings.get("tool_error_rate", 0.0) > 0 and random.random() < settings["tool_error_rate"]:
        raise Exception("chaos: simulated tool error 500")

    if kind == "query_logs":
        data = await query_logs(
            service=args.get("service", "shop-api"),
            level=args.get("level"),
            q=args.get("q"),
            last_minutes=int(args.get("last_minutes", 15)),
        )
        summary = f"{data['count']} log lines, {data['service']}"
        detail = sanitize_tool_output(data["detail"])
    elif kind == "query_metrics":
        data = await query_metrics(
            service=args.get("service", "shop-api"),
            window_minutes=int(args.get("window_minutes", 5)),
        )
        err = data.get("error_rate", 0.0)
        summary = f"{data['service']} error_rate={err:.3f} p95={data.get('p95_latency_ms', 0):.0f}ms"
        detail = json.dumps(data, indent=2, default=str)
    elif kind == "get_recent_deploys":
        data = await get_recent_deploys(
            service=args.get("service", "shop-api"),
            limit=int(args.get("limit", 5)),
        )
        version = data["current_version"]
        summary = f"current version {version}, {len(data['deploys'])} deploys"
        detail = json.dumps(data, indent=2, default=str)
    elif kind == "get_service_status":
        data = await get_service_status(service=args.get("service", "shop-api"))
        summary = f"{data['service']}: {data['status']}, version {data['version']}"
        detail = json.dumps(data, indent=2, default=str)
    elif kind == "search_runbooks":
        data = await search_runbooks(str(args.get("query", "unknown")))
        summary = f"searched runbooks for {args.get('query')}: {len(data['matches'])} matches"
        detail = json.dumps(data, indent=2, default=str)
    elif kind == "finish":
        data = await finish(diagnosis=str(args.get("diagnosis", "unknown")), confidence=float(args.get("confidence", 0.8)))
        return data
    else:
        detail = json.dumps({"error": f"unknown action kind {kind}"})
        return Observation(action_kind="finish", summary=f"unknown action {kind}", detail=detail)

    return Observation(action_kind=kind, summary=summary, detail=detail)
