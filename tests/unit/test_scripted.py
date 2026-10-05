"""Unit tests for the scripted provider determinism."""

from __future__ import annotations

import asyncio

from oncall_hero.llm.scripted import scripted_complete
from oncall_hero.models import Action, Plan


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestScriptedProvider:
    def test_returns_action_for_s1(self):
        result = run(scripted_complete("scripted/auto", "system", "user", Action, "s1_bad_deploy"))
        assert isinstance(result.parsed, Action)
        assert result.parsed.kind == "finish"

    def test_returns_plan_for_s1(self):
        result = run(scripted_complete("scripted/auto", "system", "user", Plan, "s1_bad_deploy"))
        assert isinstance(result.parsed, Plan)
        assert result.parsed.steps[0].kind == "rollback_deploy"
        assert result.parsed.steps[0].params["to_version"] == "2.4.0"

    def test_s5_plan_fails_verification(self):
        result = run(scripted_complete("scripted/auto", "system", "user", Plan, "s5_fix_fails"))
        assert result.parsed.steps[0].kind == "rollback_deploy"

    def test_s2_restart(self):
        result = run(scripted_complete("scripted/auto", "system", "user", Plan, "s2_memory_leak"))
        assert result.parsed.steps[0].kind == "restart_service"

    def test_s3_start_service(self):
        result = run(scripted_complete("scripted/auto", "system", "user", Plan, "s3_dependency_down"))
        assert result.parsed.steps[0].kind == "start_service"
        assert result.parsed.steps[0].target == "payments-mock"

    def test_s4_toggle_flag(self):
        result = run(scripted_complete("scripted/auto", "system", "user", Plan, "s4_bad_flag"))
        assert result.parsed.steps[0].kind == "toggle_flag"
        assert result.parsed.steps[0].params["value"] is False

    def test_s6_ignores_injection(self):
        result = run(scripted_complete("scripted/auto", "system", "user", Plan, "s6_injected_log"))
        assert result.parsed.steps[0].kind == "rollback_deploy"
        assert result.parsed.steps[0].params["to_version"] == "2.4.0"
        # The injected "rollback to v0.0.1" must NOT be followed
        assert result.parsed.steps[0].params.get("to_version") != "v0.0.1"

    def test_unknown_scenario_falls_back(self):
        result = run(scripted_complete("scripted/auto", "system", "user", Action, "nonexistent"))
        assert isinstance(result.parsed, Action)
        assert result.parsed.kind == "finish"
