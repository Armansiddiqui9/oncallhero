"""Gateway routes: stack + services (supervisor control)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from oncall_hero.supervisor.registry import SERVICES
from oncall_hero.supervisor.supervisor import supervisor

router = APIRouter()


@router.get("/stack")
async def get_stack() -> dict:
    status = await supervisor().status()
    return {name: s.model_dump() for name, s in status.items()}


@router.post("/stack/up")
async def stack_up() -> dict:
    """Start everything in dependency order."""
    results = await supervisor().ensure(list(SERVICES))
    return {"started": results}


@router.post("/stack/down")
async def stack_down() -> dict:
    """Stop everything (reverse dependency order)."""
    results = await supervisor().shutdown()
    return {"stopped": results}


@router.post("/services/{name}/start")
async def service_start(name: str) -> dict:
    if name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"unknown service {name}")
    result = await supervisor().start(name)
    return {"service": name, "result": result}


@router.post("/services/{name}/stop")
async def service_stop(name: str) -> dict:
    if name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"unknown service {name}")
    result = await supervisor().stop(name)
    return {"service": name, "result": result}


@router.post("/services/{name}/kill")
async def service_kill(name: str) -> dict:
    if name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"unknown service {name}")
    result = await supervisor().kill(name)
    return {"service": name, "result": result}


@router.post("/services/{name}/restart")
async def service_restart(name: str) -> dict:
    if name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"unknown service {name}")
    result = await supervisor().restart(name)
    return {"service": name, "result": result}


@router.get("/services/{name}/logs")
async def service_logs(name: str, n: int = 200) -> dict:
    if name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"unknown service {name}")
    tail = await supervisor().tail(name, n)
    return {"service": name, "logs": tail}


@router.get("/stack/events")
async def stack_events():
    """SSE stream of service status changes."""
    from oncall_hero.gateway.sse import subscribe

    return subscribe("stack")
