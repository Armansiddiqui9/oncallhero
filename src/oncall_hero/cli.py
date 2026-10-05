"""CLI for On-Call Hero (Typer).

Every command talks to the running gateway over HTTP, except `up`/`down`
which manage the gateway process itself.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser

import httpx
import typer

from oncall_hero.config import load_config
from oncall_hero.supervisor.registry import SERVICES
from oncall_hero.supervisor.supervisor import supervisor

app = typer.Typer(help="On-Call Hero: durable AI SRE agent built on Temporal")
config = load_config()

GATEWAY = f"http://{config.gateway_host}:{config.gateway_port}"


def _emit(data: object) -> None:
    """Print JSON (or a table) to stdout."""
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, default=str))
    else:
        print(data)


async def _get(path: str, timeout: float = 10.0) -> dict:
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
        resp = await client.get(f"{GATEWAY}{path}")
        resp.raise_for_status()
        return resp.json()


async def _post(path: str, payload: dict | None = None, timeout: float = 60.0) -> dict:
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
        resp = await client.post(f"{GATEWAY}{path}", json=payload or {})
        resp.raise_for_status()
        return resp.json()


def _run(coro) -> None:
    try:
        _emit(asyncio.run(coro))
    except httpx.ConnectError:
        print(f"gateway not reachable at {GATEWAY}; start it with: ohero up", file=sys.stderr)
        raise SystemExit(1)


@app.command()
def up(open_browser: bool = True, no_browser: bool = False) -> None:
    """Start the gateway (and the full stack via the launcher)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, ["src", os.getcwd(), env.get("PYTHONPATH", "")])
    )
    # Start the stack first, then serve the UI from the same process.
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "oncall_hero.gateway.app:app",
        "--host",
        config.gateway_host,
        "--port",
        str(config.gateway_port),
    ]
    print(f"starting gateway on {GATEWAY}")
    if open_browser and not no_browser:
        t = threading.Timer(1.5, webbrowser.open, args=[GATEWAY])
        t.daemon = True
        t.start()
    subprocess.run(cmd, env=env)


@app.command()
def down() -> None:
    """Stop everything (graceful, reverse dependency order)."""
    try:
        _emit(asyncio.run(_post("/api/stack/down", timeout=30)))
    except Exception:
        # Fall back to killing known processes directly.
        import psutil

        killed = []
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = " ".join(proc.info["cmdline"] or [])
                if any(
                    token in cmdline
                    for token in (
                        "uvicorn oncall_hero.gateway",
                        "temporal server start-dev",
                        "oncall_hero.temporal.worker",
                        "world.shop_api",
                        "world.payments_mock",
                    )
                ):
                    psutil.Process(proc.info["pid"]).kill()
                    killed.append(proc.info["pid"])
            except (psutil.NoSuchProcess, KeyError):
                continue
        _emit({"killed_pids": killed})


@app.command()
def status() -> None:
    """Print the service table."""
    st = asyncio.run(supervisor().status())
    print(f"{'SERVICE':<16}{'RUNNING':<9}{'PID':<9}{'HEALTHY':<8}UPTIME")
    for name in SERVICES:
        s = st.get(name)
        if s is None:
            continue
        dot = "●" if s.running else "○"
        up = f"{int(s.uptime_s // 60)}m" if s.uptime_s else "-"
        print(f"{name:<16}{dot:<9}{str(s.pid or '-'):<9}{str(s.healthy):<8}{up}")


@app.command()
def start(name: str) -> None:
    """Start one service."""
    _run(_post(f"/api/services/{name}/start"))


@app.command()
def stop(name: str) -> None:
    """Graceful stop one service."""
    _run(_post(f"/api/services/{name}/stop"))


@app.command()
def kill(name: str) -> None:
    """Hard kill one service (cross-platform, works on Windows)."""
    _run(_post(f"/api/services/{name}/kill"))


@app.command()
def logs(name: str, n: int = 200) -> None:
    """Tail a service log."""
    _run(_get(f"/api/services/{name}/logs?n={n}"))


@app.command()
def trigger(scenario: str) -> None:
    """Fire a scenario (same as the UI button)."""
    _run(_post(f"/api/scenarios/{scenario}/trigger", timeout=120))


@app.command()
def approve(incident: str, comment: str = "approved from CLI") -> None:
    """Approve an incident (optionally with an edited plan via --steps-file)."""
    _run(_post(f"/api/incidents/{incident}/approve", {"comment": comment}))


@app.command()
def reject(incident: str, reason: str = "rejected from CLI") -> None:
    """Reject an incident."""
    _run(_post(f"/api/incidents/{incident}/reject", {"reason": reason}))


@app.command()
def incidents() -> None:
    """List incidents."""
    _run(_get("/api/incidents"))


@app.command()
def incident(incident_id: str) -> None:
    """Show one incident's state and timeline."""
    _run(_get(f"/api/incidents/{incident_id}"))


@app.command()
def chaos(
    preset: str | None = None,
    error_rate: float | None = None,
    latency_ms: int | None = None,
    garbage_rate: float | None = None,
) -> None:
    """Set chaos. Example: ohero chaos --preset everything_on_fire"""
    if preset:
        _run(_post(f"/api/chaos/preset/{preset}"))
        return
    payload: dict = {}
    if error_rate is not None:
        payload["tool_error_rate"] = error_rate
    if latency_ms is not None:
        payload["tool_latency_ms"] = latency_ms
    if garbage_rate is not None:
        payload["llm_garbage_rate"] = garbage_rate
    if not payload:
        _run(_get("/api/chaos"))
        return
    _run(_post("/api/chaos", payload))


@app.command()
def models(model: str | None = None) -> None:
    """Check LLM providers: reachability, models present, JSON validity, latency."""
    _run(_get("/api/models"))
    if model:
        _run(_post("/api/models/test", {"model": model}, timeout=180))


@app.command()
def stack(action: str = "status") -> None:
    """Control the whole stack: ohero stack up | down | status"""
    if action == "up":
        _run(_post("/api/stack/up", timeout=180))
    elif action == "down":
        _run(_post("/api/stack/down", timeout=60))
    else:
        _run(_get("/api/stack"))


@app.command()
def webhook(payload: str) -> None:
    """Fire a generic alert at the webhook intake.

    Example: ohero webhook '{"service":"shop-api","summary":"5xx high"}'
    """
    _run(_post("/webhook/alert", json.loads(payload)))


@app.command()
def eval_cmd(models: str = "", runs: int = 3) -> None:
    """Run the evaluation harness.

    Example: ohero eval-cmd --models "ollama_chat/qwen2.5:14b" --runs 5
    """
    from oncall_hero.eval.runner import DEFAULT_MODELS, main as eval_main

    selected = [m.strip() for m in models.split(",") if m.strip()] or DEFAULT_MODELS
    asyncio.run(eval_main(selected, ["s1_bad_deploy"], runs, "eval/results"))


@app.command()
def demo() -> None:
    """Print the demo walkthrough with narration prompts."""
    path = "docs/demo-script.md"
    if os.path.exists(path):
        print(open(path).read())
    else:
        print("See docs/demo-script.md for the demo script.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
