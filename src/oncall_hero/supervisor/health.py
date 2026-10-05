"""Health checks: TCP, HTTP, and process-alive probes."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Annotated, Literal, Union

import httpx
from pydantic import BaseModel, Field


class Tcp(BaseModel):
    """Check that a TCP port accepts connections."""

    kind: Literal["tcp"] = "tcp"
    port: int
    host: str = "127.0.0.1"
    timeout: float = 2.0

    async def check(self, name: str) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout):
                return True
        except OSError:
            return False


class Http(BaseModel):
    """Check an HTTP URL (defaulting to GET /healthz)."""

    kind: Literal["http"] = "http"
    url: str
    timeout: float = 2.0

    async def check(self, name: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
                resp = await client.get(self.url)
                return resp.is_success
        except Exception:  # noqa: BLE001
            return False


class Process(BaseModel):
    """Check that a process (by PID) is still alive."""

    kind: Literal["process"] = "process"
    pid_file: str = ".run/pids"

    async def check(self, name: str) -> bool:
        p = Path(self.pid_file) / f"{name}.pid"
        if not p.exists():
            return False
        try:
            pid = int(p.read_text().strip())
            import psutil

            return psutil.pid_exists(pid)
        except Exception:  # noqa: BLE001
            return False


# Discriminated union so `ServiceSpec.health` validates by `kind`.
HealthCheck = Annotated[
    Union[Tcp, Http, Process],
    Field(discriminator="kind"),
]
