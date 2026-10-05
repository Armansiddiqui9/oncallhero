"""IncidentWorkflow: the durable agent loop.

Golden rule: this file contains deterministic orchestration only.
All I/O, LLM calls, randomness and time live in activities.

Configuration arrives as a `WorkflowConfig` argument (not read from disk here),
so every decision the workflow makes is recorded in its event history.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from oncall_hero.models import (
        Action,
        Alert,
        ApprovalDecision,
        Compensation,
        IncidentResult,
        IncidentState,
        Observation,
        Plan,
        RemediationStep,
        TimelineEvent,
    )
    from oncall_hero.safety.allowlist import validate_plan_against_allowlist
    from oncall_hero.workflow_config import WorkflowConfig

# ---------------------------------------------------------------------------
# Retry policies, defined once and reused.
# ---------------------------------------------------------------------------

TOOL_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=6,
    non_retryable_error_types=["DisallowedAction", "SchemaError"],
)
LLM_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
    non_retryable_error_types=["SchemaError"],
)
MUTATION_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_attempts=5,
    non_retryable_error_types=["DisallowedAction"],
)


@workflow.defn
class IncidentWorkflow:
    """Durable SRE agent: investigate -> propose -> approve -> execute -> verify."""

    def __init__(self) -> None:
        self.state = IncidentState(
            incident_id="", alert=Alert(alert_id="", service="", summary="")
        )
        self.config = WorkflowConfig()
        self.decision: ApprovalDecision | None = None
        self.paused = False
        self.cancel_requested = False
        self.scenario_id = ""
        self.compensations: list[Compensation] = []

    # ------------------------------------------------------------------ main
    @workflow.run
    async def run(
        self,
        alert: Alert,
        config: WorkflowConfig,
        scenario_id: str = "",
    ) -> IncidentResult:
        self.state = IncidentState(incident_id=alert.alert_id, alert=alert)
        self.config = config
        self.scenario_id = scenario_id
        self.compensations = []

        try:
            await self.investigate(alert)
            plan = await self.propose()

            if not plan.steps:
                self.state.log("no actionable plan; escalating to a human")
                await self.postmortem()
                return await self.close("CLOSED_NO_ACTION")

            if not await self.get_approval(plan):
                return await self.close("CLOSED_NO_ACTION")

            await self.execute(plan)
            await self.verify()
            await self.postmortem()
            return await self.close("RESOLVED")

        except asyncio.CancelledError:
            # Cancellation still runs the saga.
            await self.rollback()
            raise
        except (ActivityError, ApplicationError, ValueError):
            await self.rollback()
            await self.postmortem()
            return await self.close("ESCALATED")

    # --------------------------------------------------------- agent loop
    async def investigate(self, alert: Alert) -> None:
        self.set_phase("INVESTIGATE")
        for _ in range(self.config.max_steps):
            await workflow.wait_condition(lambda: not self.paused)
            if self.budget_exhausted():
                self.state.log("investigation budget exhausted")
                break

            try:
                action = await self.decide_next()
            except ApplicationError as exc:
                self.state.log(f"no model available: {exc}")
                break

            if action.kind == "finish":
                self.state.log("investigation finished", diagnosis=str(action.args.get("diagnosis", "")))
                break

            try:
                obs = await workflow.execute_activity(
                    run_tool,
                    args=[action],
                    start_to_close_timeout=timedelta(seconds=self.config.tool_timeout_s),
                    retry_policy=TOOL_RETRY,
                )
            except ActivityError as exc:
                self.state.log(f"tool {action.kind} failed after retries", error=str(exc))
                continue

            self.state.record(action, obs)

    async def decide_next(self) -> Action:
        """Model fallback chain: try each model in order, fall back on failure."""
        for model in self.config.model_chain:
            try:
                result = await workflow.execute_activity(
                    llm_decide,
                    args=[model, self.state.model_dump_json(), self.scenario_id],
                    start_to_close_timeout=timedelta(seconds=self.config.llm_timeout_s),
                    retry_policy=LLM_RETRY,
                )
            except ActivityError as exc:
                self.state.log(f"model {model} failed, falling back", error=str(exc))
                continue
            self.state.model_used = model
            self.state.log(f"model used: {model}")
            return Action.model_validate_json(result)
        raise ApplicationError("All models failed", non_retryable=True)

    # ------------------------------------------------------------ proposal
    async def propose(self) -> Plan:
        self.set_phase("PROPOSE")
        model = self.config.proposal_model or self.config.model_chain[-1]

        plan = await self._ask_for_plan(model)
        error = self._validate(plan)
        if error is None:
            self.state.plan = plan
            self.state.log("plan proposed and validated")
            return plan

        # One re-ask on an invalid plan, then escalate with no action.
        self.state.log("plan rejected by validator", reason=error)
        plan = await self._ask_for_plan(model)
        error = self._validate(plan)
        if error is not None:
            raise ApplicationError(f"plan still invalid: {error}", non_retryable=True)

        self.state.plan = plan
        self.state.log("corrected plan accepted")
        return plan

    async def _ask_for_plan(self, model: str) -> Plan:
        result = await workflow.execute_activity(
            propose_remediation,
            args=[model, self.state.model_dump_json()],
            start_to_close_timeout=timedelta(seconds=self.config.llm_timeout_s),
            retry_policy=LLM_RETRY,
        )
        return Plan.model_validate_json(result)

    def _validate(self, plan: Plan) -> str | None:
        """Deterministic validation. Returns None when valid, else the reason."""
        if not plan.steps:
            return "plan has no remediation steps"
        try:
            validate_plan_against_allowlist(plan.steps)
        except ValueError as exc:
            return str(exc)
        return None

    # ------------------------------------------------------------ approval
    @workflow.update
    async def approve(self, decision: ApprovalDecision) -> dict:
        self.decision = decision
        if decision.steps and self.state.plan:
            self.state.plan.steps = decision.steps
            self.state.human_edits.append(
                f"plan edited by approver: {len(decision.steps)} step(s)"
            )
        self.state.log("approved", comment=decision.comment)
        return {"accepted": True, "steps": len(decision.steps or [])}

    @approve.validator
    def _validate_approve(self, decision: ApprovalDecision) -> None:
        if self.state.phase != "AWAITING_APPROVAL":
            raise ApplicationError("Incident is not awaiting approval")
        if decision.steps:
            validate_plan_against_allowlist(decision.steps)

    @workflow.update
    async def reject(self, reason: str) -> dict:
        self.decision = ApprovalDecision(approved=False, comment=reason)
        self.state.log("rejected", reason=reason)
        return {"accepted": True}

    @reject.validator
    def _validate_reject(self, reason: str) -> None:
        if self.state.phase != "AWAITING_APPROVAL":
            raise ApplicationError("Incident is not awaiting approval")

    async def get_approval(self, plan: Plan) -> bool:
        """Wait for a human across the escalation chain. Silence means no action."""
        self.set_phase("AWAITING_APPROVAL")
        for level in self.config.approval_chain:
            await workflow.execute_activity(
                notify_human,
                args=[level.name, plan.model_dump_json()],
                start_to_close_timeout=timedelta(seconds=15),
            )
            try:
                await workflow.wait_condition(
                    lambda: self.decision is not None,
                    timeout=timedelta(seconds=level.timeout_s),
                )
            except asyncio.TimeoutError:
                self.state.escalations.append(level.name)
                self.state.log(f"no response from {level.name}, escalating")
                continue
            return self.decision.approved
        return False

    # ----------------------------------------------------------- execution
    async def execute(self, plan: Plan) -> None:
        self.set_phase("EXECUTE")
        for i, step in enumerate(plan.steps):
            await workflow.execute_activity(
                execute_step,
                args=[step],
                start_to_close_timeout=timedelta(seconds=self.config.mutation_timeout_s),
                retry_policy=MUTATION_RETRY,
            )
            # Registered AFTER the step succeeded: only completed work is undone.
            if step.compensation is not None:
                self.compensations.append(step.compensation)
            self.state.log(f"step {i + 1}/{len(plan.steps)} executed", kind=step.kind, target=step.target)

    async def verify(self) -> None:
        self.set_phase("VERIFY")
        # Durable timer: survives worker death, restarts and server restarts.
        await workflow.sleep(timedelta(seconds=self.config.verify_delay_s))

        verify_json = self.state.plan.verify.model_dump_json() if self.state.plan else "{}"
        health = await workflow.execute_activity(
            check_health,
            args=[self.state.alert.service, verify_json],
            start_to_close_timeout=timedelta(seconds=30),
        )
        self.state.log("verification", **health)
        if not health.get("recovered"):
            raise ApplicationError("Verification failed", non_retryable=True)

    async def rollback(self) -> None:
        """Saga: undo completed steps in reverse order."""
        if not self.compensations:
            return
        self.set_phase("ROLLBACK")
        for comp in reversed(self.compensations):
            try:
                await workflow.execute_activity(
                    run_compensation,
                    args=[comp],
                    start_to_close_timeout=timedelta(seconds=self.config.mutation_timeout_s),
                    retry_policy=MUTATION_RETRY,
                )
                self.state.log("compensation applied", kind=comp.kind, target=comp.target)
            except ActivityError as exc:
                self.state.log("compensation failed", kind=comp.kind, error=str(exc))

    # --------------------------------------------------------------- close
    async def postmortem(self) -> None:
        try:
            name = await workflow.execute_activity(
                write_postmortem,
                args=[self.state.model_dump_json()],
                start_to_close_timeout=timedelta(seconds=30),
            )
            self.state.log("postmortem written", file=name)
        except ActivityError as exc:
            self.state.log("postmortem failed", error=str(exc))

    async def close(self, status: str) -> IncidentResult:
        self.set_phase(status)
        return IncidentResult(
            incident_id=self.state.incident_id,
            status=self.state.phase,
            diagnosis=self.state.plan.diagnosis if self.state.plan else "",
            plan=self.state.plan,
            mutations_executed=[
                e.message for e in self.state.timeline if e.message.startswith("step ")
            ],
            postmortem=self.state.postmortem,
        )

    # ------------------------------------------------------------- helpers
    def set_phase(self, phase: str) -> None:
        self.state.phase = phase
        self.state.timeline.append(
            TimelineEvent(phase=self.state.phase.value, message=f"phase -> {phase}")
        )
        # Search attributes are a nice-to-have; never fail the incident for them.
        try:
            workflow.upsert_search_attributes(
                {"Phase": phase, "Service": self.state.alert.service}
            )
        except Exception:  # noqa: BLE001 - attribute may not be registered
            pass

    def budget_exhausted(self) -> bool:
        b = self.state.budget
        return (
            b.steps_used >= self.config.max_steps
            or b.llm_calls >= b.max_llm_calls
            or b.tokens_used >= b.max_tokens
            or b.cost_usd >= b.max_cost_usd
        )

    # --------------------------------------------------- signals and queries
    @workflow.signal
    def pause(self) -> None:
        self.paused = True
        self.state.log("paused by operator")

    @workflow.signal
    def resume(self) -> None:
        self.paused = False
        self.state.log("resumed by operator")

    @workflow.signal
    def add_note(self, text: str) -> None:
        self.state.notes.append(text)
        self.state.log("note added", text=text)

    @workflow.signal
    def cancel_incident(self) -> None:
        """Request cancellation. Compensations still run.

        Raises CancelledError so the run() handler's except clause runs the
        saga. Temporal records the cancellation in history.
        """
        self.state.log("cancellation requested")
        self.cancel_requested = True
        raise asyncio.CancelledError()

    @workflow.query
    def status(self) -> dict:
        return self.state.model_dump(mode="json")

    @workflow.query
    def timeline(self) -> list[dict]:
        return [e.model_dump(mode="json") for e in self.state.timeline]

    @workflow.query
    def budget(self) -> dict:
        return self.state.budget.model_dump(mode="json")

    @workflow.query
    def plan(self) -> dict | None:
        return self.state.plan.model_dump(mode="json") if self.state.plan else None


# Activity imports live at the bottom: importing them at module scope would
# pull httpx/litellm into the workflow sandbox import graph.
from oncall_hero.activities.llm import llm_decide, propose_remediation  # noqa: E402
from oncall_hero.activities.notify import notify_human  # noqa: E402
from oncall_hero.activities.postmortem import write_postmortem  # noqa: E402
from oncall_hero.activities.remediation import (  # noqa: E402
    check_health,
    execute_step,
    run_compensation,
)
from oncall_hero.activities.tools import run_tool  # noqa: E402