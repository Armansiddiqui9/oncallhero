"""FastAPI gateway app: HTTP API, SSE, static UI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from oncall_hero.chaos import set_chaos, chaos
from oncall_hero.config import load_config
from oncall_hero.gateway.routes_incidents import router as incidents_router
from oncall_hero.gateway.routes_stack import router as stack_router
from oncall_hero.gateway.sse import subscribe, publish
from oncall_hero.supervisor.registry import SERVICES
from oncall_hero.supervisor.supervisor import supervisor

config = load_config()

app = FastAPI(title="On-Call Hero gateway", version="0.1.0")

app.include_router(stack_router, prefix="/api")
app.include_router(incidents_router, prefix="/api")

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


@app.get("/api/config")
async def get_config() -> dict:
    data = config.as_dict()
    # redact secrets
    if "llm" in data and isinstance(data["llm"], dict):
        data["llm"].pop("api_key", None)
    return data


@app.get("/api/chaos")
async def get_chaos() -> dict:
    return chaos()


@app.post("/api/chaos")
async def post_chaos(settings: dict) -> dict:
    merged = set_chaos(settings)
    await publish("chaos", merged)
    return merged


@app.post("/api/chaos/preset/{name}")
async def post_chaos_preset(name: str) -> dict:
    from oncall_hero.chaos import preset

    p = preset(name)
    if p is None:
        raise HTTPException(status_code=404, detail=f"unknown preset {name}")
    merged = set_chaos(p)
    await publish("chaos", merged)
    return merged


@app.get("/api/models")
async def get_models() -> dict:
    """Provider health: Ollama models present, chain status."""
    import httpx

    chain = config.llm_chain
    providers: dict[str, str] = {}
    for model in chain:
        provider = model.split("/")[0]
        providers[provider] = "unknown"
    # Check Ollama reachability
    ollama_ok = False
    ollama_models: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            resp = await client.get(f"{config.ollama_api_base}/api/tags")
            if resp.is_success:
                data = resp.json()
                ollama_models = [m["name"] for m in data.get("models", [])]
                ollama_ok = True
    except Exception:  # noqa: BLE001
        pass
    providers["ollama"] = "reachable" if ollama_ok else "unreachable"
    return {
        "chain": chain,
        "providers": providers,
        "ollama": {"reachable": ollama_ok, "models": ollama_models},
    }


@app.post("/api/models/test")
async def test_model(model: str) -> dict:
    """One completion + JSON validity check."""
    from oncall_hero.llm.prompts import SYSTEM_PROMPT
    from oncall_hero.llm.provider import complete
    from oncall_hero.llm.scripted import scripted_complete
    from oncall_hero.models import Action, Budget
    from oncall_hero.llm import SchemaError, ProviderError

    budget = Budget()
    try:
        if "scripted" in model:
            result = await scripted_complete(
                model, SYSTEM_PROMPT, "test prompt", Action
            )
        else:
            result = await complete(
                model, SYSTEM_PROMPT, "test prompt", Action, budget
            )
        return {
            "model": model,
            "ok": True,
            "latency_s": result.latency_s,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "parsed_kind": result.parsed.kind,
        }
    except (SchemaError, ProviderError) as e:
        return {"model": model, "ok": False, "error": str(e)}


@app.post("/api/notifications")
async def notifications(payload: dict) -> dict:
    """Receive notifications from activities (notify_human)."""
    await publish("notification", payload)
    return {"received": True}


@app.get("/api/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(_sse_broadcaster())


async def _sse_broadcaster() -> None:
    """Broadcast stack status + chaos changes over SSE every second."""
    while True:
        try:
            status = await supervisor().status()
            await publish(
                "stack",
                {name: s.model_dump() for name, s in status.items()},
            )
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(1)
