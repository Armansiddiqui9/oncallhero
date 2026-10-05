"""Unit tests for the safety model and validators."""

from __future__ import annotations

import pytest

from oncall_hero.models import Compensation, Plan, RemediationStep
from oncall_hero.safety.allowlist import (
    DisallowedAction,
    NonCompensableWarning,
    UnknownTarget,
    UnknownVersion,
    validate_plan_against_allowlist,
)
from oncall_hero.safety.sanitize import sanitize_tool_output, truncate_summary
from oncall_hero.safety.validators import validate_plan, validate_verify_spec


def _step(kind: str = "rollback_deploy", target: str = "shop-api", **params) -> RemediationStep:
    return RemediationStep(
        kind=kind,
        target=target,
        params=params or {},
        risk="low",
        rationale="test",
        compensation=Compensation(kind="toggle_flag", target="new_pricing", params={"value": False}),
    )


class TestAllowlist:
    def test_valid_rollback(self):
        plan = Plan(steps=[_step(to_version="2.4.0")])
        validate_plan_against_allowlist(plan.steps)  # no exception

    def test_unknown_kind(self):
        with pytest.raises(DisallowedAction):
            validate_plan_against_allowlist([_step(kind="delete_everything")])

    def test_platform_target_rejected(self):
        with pytest.raises(DisallowedAction):
            validate_plan_against_allowlist([_step(target="worker")])

    def test_unknown_target(self):
        with pytest.raises(UnknownTarget):
            validate_plan_against_allowlist([_step(target="nonexistent-service")])

    def test_unknown_version(self):
        with pytest.raises(UnknownVersion):
            validate_plan_against_allowlist([_step(params={"to_version": "9.9.9"})])

    def test_missing_compensation(self):
        step = _step()
        step.compensation = None
        with pytest.raises(DisallowedAction):
            validate_plan_against_allowlist([step])

    def test_restart_non_compensable(self):
        step = _step(kind="restart_service", target="shop-api")
        step.compensation = None
        with pytest.raises(NonCompensableWarning):
            validate_plan_against_allowlist([step])

    def test_toggle_flag_unknown_flag(self):
        with pytest.raises(UnknownTarget):
            validate_plan_against_allowlist([_step(kind="toggle_flag", target="nonexistent_flag")])

    def test_toggle_flag_invalid_value(self):
        with pytest.raises(DisallowedAction):
            validate_plan_against_allowlist([_step(kind="toggle_flag", target="new_pricing", params={"value": "maybe"})])


class TestValidators:
    def test_validate_plan_valid(self):
        plan = Plan(
            diagnosis="deploy bug",
            evidence=["evidence"],
            steps=[_step(to_version="2.4.0")],
        )
        assert validate_plan(plan) is None

    def test_validate_plan_no_steps(self):
        plan = Plan(diagnosis="x")
        assert validate_plan(plan) == "plan has no steps"

    def test_validate_verify_spec(self):
        from oncall_hero.models import VerifySpec

        assert validate_verify_spec(VerifySpec()) is None
        assert validate_verify_spec(VerifySpec(metric="bogus")) == "unsupported metric bogus"


class TestSanitizer:
    def test_wraps_in_untrusted_tags(self):
        out = sanitize_tool_output("hello world")
        assert "<untrusted_data" in out
        assert "hello world" in out
        assert "</untrusted_data>" in out

    def test_truncates_long_output(self):
        out = sanitize_tool_output("x" * 10000)
        assert len(out) < 4100

    def test_strips_control_chars(self):
        out = sanitize_tool_output("bad\x00\x01chars\nnew")
        assert "\x00" not in out
        assert "\n" in out

    def test_truncate_summary(self):
        assert len(truncate_summary("y" * 2000)) <= 800
