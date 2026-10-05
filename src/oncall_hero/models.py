"""Core Pydantic models for On-Call Hero.

These models cross the workflow/activity boundary, so they are
imported inside workflow code via `workflow.unsafe.imports_passed_through()`.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Alert and investigation
# ---------------------------------------------------------------------------


class Alert(BaseModel):
    """An incoming alert (from the demo scenario or a webhook)."""

    alert_id: str
    service: str
    severity: Literal["low", "medium", "high", "critical"] = "high"
    summary: str
    source: str = "demo"


class Action(BaseModel):
    """One agent decision. The LLM chooses from a closed set of kinds."""

    reasoning: str = Field(max_length=600)
    kind: Literal[
        "query_logs",
        "query_metrics",
        "get_recent_deploys",
        "get_service_status",
        "search_runbooks",
        "finish",
    ]
    args: dict[str, str | int | float | bool] = Field(default_factory=dict)


class Observation(BaseModel):
    """Result of one action, fed back into the prompt."""

    action_kind: str
    summary: str = Field(max_length=800)
    detail: str = Field(max_length=4000)


class Finding(BaseModel):
    """A conclusion from an investigator (child workflow)."""

    source: str
    summary: str
    evidence: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Remediation
# ---------------------------------------------------------------------------


class Compensation(BaseModel):
    """How to undo a step. None means explicitly non-compensable."""

    kind: Literal["rollback_deploy", "restart_service", "stop_service", "toggle_flag"]
    target: str
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)


class RemediationStep(BaseModel):
    """One mutating step in a plan. Always gated by human approval."""

    kind: Literal["rollback_deploy", "restart_service", "start_service", "toggle_flag"]
    target: str
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)
    risk: Literal["low", "medium", "high"] = "medium"
    rationale: str = Field(max_length=400)
    compensation: Compensation | None = None


class VerifySpec(BaseModel):
    """What 'healthy' means after the fix."""

    metric: str = "error_rate"
    threshold: float = 0.02
    wait_seconds: int = 20


class Plan(BaseModel):
    """The proposed remediation plan, validated by deterministic code."""

    diagnosis: str
    evidence: list[str] = Field(default_factory=list)
    steps: list[RemediationStep] = Field(default_factory=list)
    expected_outcome: str = ""
    verify: VerifySpec = Field(default_factory=VerifySpec)


class ApprovalDecision(BaseModel):
    """Human answer to a plan. May carry edited steps (re-validated)."""

    approved: bool
    steps: list[RemediationStep] | None = None
    comment: str = ""


class ApprovalRejection(BaseModel):
    reason: str


class StepResult(BaseModel):
    step_index: int
    ok: bool
    message: str = ""


# ---------------------------------------------------------------------------
# Workflow state
# ---------------------------------------------------------------------------


class Phase(str, Enum):
    TRIAGE = "TRIAGE"
    INVESTIGATE = "INVESTIGATE"
    PROPOSE = "PROPOSE"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    ROLLBACK = "ROLLBACK"
    RESOLVED = "RESOLVED"
    CLOSED_NO_ACTION = "CLOSED_NO_ACTION"
    ESCALATED = "ESCALATED"


class TimelineEvent(BaseModel):
    phase: str
    message: str
    # activity attempts, retries etc. get recorded here too
    detail: dict[str, Any] = Field(default_factory=dict)


class Budget(BaseModel):
    max_steps: int = 10
    max_llm_calls: int = 20
    max_tokens: int = 40000
    max_cost_usd: float = 0.25
    max_wall_clock_s: int = 600
    steps_used: int = 0
    llm_calls: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0


class IncidentState(BaseModel):
    """The full mutable incident state, carried inside the workflow."""

    incident_id: str
    alert: Alert
    phase: Phase = Phase.TRIAGE
    observations: list[Observation] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    plan: Plan | None = None
    model_used: str = ""
    notes: list[str] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    human_edits: list[str] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)
    postmortem: str = ""

    def record(self, action: Action, obs: Observation) -> None:
        self.observations.append(obs)
        self.budget.steps_used += 1
        self.timeline.append(
            TimelineEvent(
                phase=self.phase.value,
                message=f"{action.kind}: {obs.summary}",
            )
        )

    def log(self, message: str, **detail: Any) -> None:
        self.timeline.append(
            TimelineEvent(phase=self.phase.value, message=message, detail=detail)
        )

    def prompt_view(self) -> str:
        """Compact view of state for the LLM prompt (deterministic)."""
        parts = []
        if self.observations:
            parts.append("<history>")
            recent = self.observations[-3:]
            for o in self.observations[: max(0, len(self.observations) - 3)]:
                parts.append(f"- {o.action_kind}: {o.summary}")
            for o in recent:
                parts.append(f"- {o.action_kind}: {o.summary} | {o.detail}")
            parts.append("</history>")
        if self.notes:
            parts.append("<notes>" + " | ".join(self.notes) + "</notes>")
        parts.append(
            f"<budget>steps left: {self.budget.max_steps - self.budget.steps_used}, "
            f"tokens left: {self.budget.max_tokens - self.budget.tokens_used}</budget>"
        )
        return "\n".join(parts)


class IncidentResult(BaseModel):
    incident_id: str
    status: Phase
    diagnosis: str = ""
    plan: Plan | None = None
    mutations_executed: list[str] = Field(default_factory=list)
    postmortem: str = ""

class LLMResult(BaseModel):
    '''Result from LLM decision activity (scripted replay / real model).'''
    reasoning: str
    actions: list[Action] = []
    plan: Plan | None = None
    budget_spent: float = 0.0
