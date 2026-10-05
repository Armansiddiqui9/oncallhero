"""Unit tests for the supervisor registry and health checks."""

from __future__ import annotations

import pytest

from oncall_hero.supervisor.registry import SERVICES, WORLD_SERVICES, PLATFORM_SERVICES
from oncall_hero.supervisor.health import Http, Process, Tcp


class TestRegistry:
    def test_all_services_present(self):
        for name in ["temporal", "worker", "shop-api", "payments-mock"]:
            assert name in SERVICES

    def test_groups(self):
        assert SERVICES["temporal"].group == "platform"
        assert SERVICES["worker"].group == "platform"
        assert SERVICES["shop-api"].group == "world"
        assert SERVICES["payments-mock"].group == "world"

    def test_fixed_argv(self):
        for spec in SERVICES.values():
            assert isinstance(spec.cmd, list)
            assert all(isinstance(c, str) for c in spec.cmd)

    def test_dependencies(self):
        assert "temporal" in SERVICES["worker"].depends_on
        assert SERVICES["temporal"].depends_on == []

    def test_world_separate_from_platform(self):
        assert WORLD_SERVICES.isdisjoint(PLATFORM_SERVICES)


class TestHealthChecks:
    @pytest.mark.asyncio
    async def test_tcp_check(self):
        check = Tcp(7233)
        # No server running on 7233 by default in tests
        result = await check.check("temporal")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_http_check(self):
        check = Http("http://127.0.0.1:9001/healthz")
        result = await check.check("shop-api")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_process_check(self):
        check = Process()
        result = await check.check("worker")
        assert isinstance(result, bool)
