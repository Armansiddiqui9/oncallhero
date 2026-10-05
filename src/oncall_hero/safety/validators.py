"""Plan validators for the `plan` step (stronger model + deterministic checks)."""

from __future__ import annotations

from oncall_hero.models import Plan, RemediationStep, VerifySpec
from oncall_hero.safety.allowlist import validate_plan_against_allowlist


def validate_plan(plan: Plan) -> str | None:
    """Validate a proposed plan. Returns None if valid, else an error string."""
    try:
        validate_plan_against_allowlist(plan.steps)
    except ValueError as e:
        return str(e)
    if not plan.steps:
        return "plan has no steps"
    if not plan.diagnosis:
        return "plan has no diagnosis"
    if not plan.verify:
        return "plan has no verify spec"
    return None


def validate_verify_spec(spec: VerifySpec) -> str | None:
    """Validate the plan's verify block."""
    if not isinstance(spec.threshold, (int, float)) or spec.threshold < 0:
        return "invalid threshold"
    if not isinstance(spec.wait_seconds, int) or spec.wait_seconds <= 0:
        return "invalid wait_seconds"
    if spec.metric not in {"error_rate", "memory_mb", "p95_latency_ms", "checkout_ok"}:
        return f"unsupported metric {spec.metric}"
    return None


def plan_has_step_kind(plan: Plan, kind: str) -> bool:
    return any(s.kind == kind for s in plan.steps)
