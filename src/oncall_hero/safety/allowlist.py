"""Safety model: deterministic validation of agent plans (no LLM involved)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel

from oncall_hero.models import (
    Compensation,
    Plan,
    RemediationStep,
)

if TYPE_CHECKING:
    from pathlib import Path


WORLD_GROUP = {"payments-mock", "shop-api"}
PLATFORM_GROUP = {"temporal", "worker"}

ALLOWED_REMEDIATION_KINDS = {"rollback_deploy", "restart_service", "start_service", "toggle_flag"}
ALLOWED_INVESTIGATION_KINDS = {
    "query_logs",
    "query_metrics",
    "get_recent_deploys",
    "get_service_status",
    "search_runbooks",
    "finish",
}

# Version availability for each service (mirrors DEPLOYS in shop-api)
SERVICE_VERSIONS: dict[str, list[str]] = {
    "shop-api": ["2.3.0", "2.4.0", "2.4.1"],
    "payments-mock": ["1.0.0"],
}

# Flag name -> known values for toggle_flag validation
KNOWN_FLAGS: dict[str, bool] = {"new_pricing": False, "experimental_checkout": False}

# Non-compensable steps: the UI must warn and require explicit confirmation
NON_COMPENSABLE_KINDS: set[str] = {"restart_service"}


class DisallowedAction(ValueError):
    """Raised when a plan violates a safety rule."""


class NonCompensableWarning(RuntimeError):
    """Raised for a non-compensable step that needs explicit human confirmation."""


class UnknownVersion(ValueError):
    pass


class UnknownTarget(ValueError):
    pass


def validate_plan_against_allowlist(steps: list[RemediationStep]) -> None:
    """Deterministic validation: kinds, targets, versions, compensation.

    Errors:
        DisallowedAction - an action kind or target not allowed
        UnknownVersion   - rollback target does not exist
        NonCompensableWarning - step has no compensation and needs explicit confirm
    """
    seen: set[str] = set()
    for step in steps:
        # 1. Kind
        if step.kind not in ALLOWED_REMEDIATION_KINDS:
            raise DisallowedAction(f"unknown action kind {step.kind}")

        # 2. Target must be in the world group (never platform)
        if step.target in PLATFORM_GROUP:
            raise DisallowedAction(f"cannot remediate platform service {step.target}")
        if step.target not in WORLD_GROUP and step.target not in KNOWN_FLAGS:
            raise UnknownTarget(f"unknown remediation target {step.target}")

        # 3. Version existence for rollback_deploy
        if step.kind == "rollback_deploy":
            if step.target not in SERVICE_VERSIONS:
                raise UnknownVersion(f"no deploy history for {step.target}")
            if step.params.get("to_version") not in SERVICE_VERSIONS[step.target]:
                raise UnknownVersion(
                    f"{step.target} does not have version {step.params.get('to_version')}"
                )

        # 4. Flags must exist and use known values
        if step.kind == "toggle_flag":
            if step.target not in KNOWN_FLAGS:
                raise UnknownTarget(f"unknown flag {step.target}")
            value = step.params.get("value")
            if value not in (True, False):
                raise DisallowedAction(f"invalid flag value {value!r}")

        # 5. Compensation
        comp = step.compensation
        if step.kind in NON_COMPENSABLE_KINDS:
            if comp is None:
                raise NonCompensableWarning(f"{step.kind} is non-compensable: {step}")
            continue  # compensable steps must have a compensation
        if comp is None:
            raise DisallowedAction(f"step {step.kind} must have a compensation")

        # 6. No duplicates
        if step.kind == "toggle_flag" and comp.kind == "toggle_flag":
            if comp.target == step.target:
                raise DisallowedAction(f"flag {step.target} cannot be toggled twice")
        key = f"{step.kind}:{step.target}"
        if key in seen:
            raise DisallowedAction(f"duplicate step {key}")
        seen.add(key)


def load_scenario(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)  # type: ignore[return-value]


def scenario_expected(path: Path) -> dict:
    data = load_scenario(path)
    return data.get("expected", {})
