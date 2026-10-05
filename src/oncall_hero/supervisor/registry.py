"""Service registry: fixed ServiceSpecs, never built from user input."""

from __future__ import annotations

import sys

from pydantic import BaseModel, Field

from oncall_hero.supervisor.health import Http, Process, Tcp, HealthCheck

GROUP = str


class ServiceSpec(BaseModel):
    name: str
    group: str
    cmd: list[str]  # fixed argv, never built from user input
    cwd: str = "."
    env: dict[str, str] = Field(default_factory=dict)
    health: HealthCheck
    depends_on: list[str] = Field(default_factory=list)
    auto_restart: bool = False


# The dependency graph: platform must start before world.
# `cmd` uses fixed argv lists. The HTTP API only accepts a service name.
# The Temporal dev server runs via the Temporal CLI (a prerequisite, see README).
SERVICES: dict[str, ServiceSpec] = {
    "temporal": ServiceSpec(
        name="temporal",
        group="platform",
        cmd=[
            "temporal",
            "server",
            "start-dev",
            "--db-filename",
            ".run/temporal.db",
            "--ui-port",
            "8233",
        ],
        env={"TEMPORAL_HOST": "127.0.0.1", "TEMPORAL_PORT": "7233"},
        health=Tcp(kind="tcp", port=7233),
    ),
    "worker": ServiceSpec(
        name="worker",
        group="platform",
        cmd=[sys.executable, "-m", "oncall_hero.temporal.worker"],
        depends_on=["temporal"],
        health=Process(kind="process"),
    ),
    "shop-api": ServiceSpec(
        name="shop-api",
        group="world",
        cmd=[sys.executable, "-m", "world.shop_api"],
        health=Http(kind="http", url="http://127.0.0.1:9001/healthz"),
    ),
    "payments-mock": ServiceSpec(
        name="payments-mock",
        group="world",
        cmd=[sys.executable, "-m", "world.payments_mock"],
        depends_on=["shop-api"],
        health=Http(kind="http", url="http://127.0.0.1:9002/healthz"),
    ),
}

PLATFORM_SERVICES = {"temporal", "worker"}
WORLD_SERVICES = {"shop-api", "payments-mock"}
