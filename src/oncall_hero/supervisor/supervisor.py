"""Supervisor: start/stop/kill processes with dependency order + health waits."""

from __future__ import annotations

import asyncio
import os
import signal
import time
from pathlib import Path

import psutil
from pydantic import BaseModel

from oncall_hero.supervisor.health import HealthCheck, Process, Tcp  # noqa: F401
from oncall_hero.supervisor.registry import SERVICES, ServiceSpec

LOGS_DIR = Path(".run/logs")
PIDS_DIR = Path(".run/pids")

os.environ.setdefault("TEMPORAL_HOST", "127.0.0.1")
os.environ.setdefault("TEMPORAL_PORT", "7233")


class ServiceStatus(BaseModel):
    running: bool
    pid: int | None = None
    healthy: bool = False
    uptime_s: float | None = None
    last_exit_code: int | None = None


class Supervisor:
    """Start/stop/kill services, respecting dependency order."""

    def __init__(self) -> None:
        self._procs: dict[str, asyncio.subprocess.Process] = {}
        self._started: set[str] = set()
        self._health_timeout = 60.0

    async def start(self, name: str) -> str:
        """Spawn, tee logs, write PID, wait for health."""
        spec = SERVICES[name]
        await self._ensure_deps(spec)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        PIDS_DIR.mkdir(parents=True, exist_ok=True)
        pid_file = PIDS_DIR / f"{name}.pid"
        log_file = LOGS_DIR / f"{name}.log"

        # Re-adopt if already running via PID file
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                if psutil.pid_exists(pid):
                    # Re-adopt: keep process tracked but don't replace subprocess
                    self._procs[name] = None  # adopted; managed via PID
                    return f"adopted existing process {name} (pid {pid})"
            except Exception:  # noqa: BLE001
                pass

        proc = await asyncio.create_subprocess_exec(
            *spec.cmd,
            cwd=spec.cwd,
            env={**os.environ, **spec.env},
            stdout=open(log_file, "a"),
            stderr=open(log_file, "a"),
        )
        self._procs[name] = proc
        pid_file.write_text(str(proc.pid))

        # Wait for health
        for _ in range(int(self._health_timeout * 10)):
            if await spec.health.check(name):
                self._started.add(name)
                return f"service {name} started (pid {proc.pid}, healthy)"
            await asyncio.sleep(0.1)
        raise TimeoutError(f"service {name} failed health check")

    async def stop(self, name: str, grace: float = 5.0) -> str:
        """SIGTERM, then SIGKILL after grace period."""
        proc = self._procs.get(name)
        if proc is None:
            return f"service {name} not running"
        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=grace)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        except ProcessLookupError:
            pass
        self._procs.pop(name, None)
        (Path(".run/pids") / f"{name}.pid").unlink(missing_ok=True)
        self._started.discard(name)
        return f"service {name} stopped"

    async def kill(self, name: str) -> str:
        """Hard kill via psutil (cross-platform, like `kill -9`)."""
        pid_file = Path(".run/pids") / f"{name}.pid"
        pid = None
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
            except Exception:  # noqa: BLE001
                pass
        try:
            if pid:
                proc = psutil.Process(pid)
                if proc.is_running():
                    proc.kill()
                    return f"service {name} killed (pid {pid})"
            return f"service {name} not found"
        except psutil.NoSuchProcess:
            return f"service {name} not running"

    async def restart(self, name: str) -> str:
        """Restart: stop, brief wait, start — improved for Phase 2 reliability."""
        await self.stop(name)
        await asyncio.sleep(0.5)  # brief for port release / cleanup
        return await self.start(name)

    async def status(self, name: str | None = None) -> dict[str, ServiceStatus]:
        out: dict[str, ServiceStatus] = {}
        targets = [name] if name else list(SERVICES)
        for t in targets:
            pid = None
            healthy = False
            uptime: float | None = None
            last_code: int | None = None
            proc = self._procs.get(t)
            pid_file = Path(".run/pids") / f"{t}.pid"
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                except Exception:  # noqa: BLE001
                    pass
            if pid:
                try:
                    p = psutil.Process(pid)
                    running = p.is_running()
                    healthy = await SERVICES[t].health.check(t)
                    uptime = time.time() - p.create_time() if p.create_time() else None
                    if not running:
                        last_code = p.exit_code()
                except psutil.NoSuchProcess:
                    pass
            elif proc is not None and proc.returncode is None:
                running = True
                healthy = await SERVICES[t].health.check(t)
                uptime = None
            else:
                running = False
            out[t] = ServiceStatus(running=running, pid=pid, healthy=healthy, uptime_s=uptime, last_exit_code=last_code)
        return out

    async def ensure(self, names: list[str]) -> dict[str, str]:
        """Start in dependency order, skip already-healthy ones."""
        results: dict[str, str] = {}
        for name in names:
            spec = SERVICES[name]
            if all(n in self._started for n in spec.depends_on):
                try:
                    results[name] = await self.start(name)
                except TimeoutError as e:
                    results[name] = str(e)
                    return results
            else:
                results[name] = f"waiting on deps of {name}"
        return results

    async def _ensure_deps(self, spec: ServiceSpec) -> None:
        """Make sure dependencies of a spec are healthy before starting it."""
        for dep in spec.depends_on:
            if dep not in self._started:
                await self.start(dep)

    async def tail(self, name: str, n: int = 200) -> str:
        """Tail the service log file."""
        log_file = Path(".run/logs") / f"{name}.log"
        if not log_file.exists():
            return ""
        text = log_file.read_text(errors="replace")
        lines = text.splitlines()[-n:]
        return "\n".join(lines)

    async def shutdown(self) -> dict[str, str]:
        """Stop world, then worker, then temporal (reverse dependency order)."""
        order = ["payments-mock", "shop-api", "worker", "temporal"]
        results: dict[str, str] = {}
        for name in order:
            results[name] = await self.stop(name)
        self._procs.clear()
        return results


_supervisor: Supervisor | None = None


def supervisor() -> Supervisor:
    global _supervisor
    if _supervisor is None:
        _supervisor = Supervisor()
    return _supervisor
