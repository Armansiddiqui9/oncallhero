"""HealthPatrolWorkflow: proactive periodic checks.

Runs on a Temporal Schedule, checks world services, and starts an
IncidentWorkflow when thresholds are crossed. The incident workflow ID is
`incident-{service}-{alert_id}` with an ID conflict policy, so a duplicate
threshold breach attaches to the existing incident instead of forking a second.
"""

from __future__ import annotations

import json
from datetime import timedelta

from temporalio import workflow
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from oncall_hero.models import Alert, Action, Observation
    from oncall_hero.workflow_config import WorkflowConfig

ERROR_THRESHOLD = 0.05


@workflow.defn
class HealthPatrolWorkflow:
    """Patrol world services and open incidents on threshold breaches."""

    def __init__(self) -> None:
        self.findings: list[str] = []

    @workflow.run
    async def run(self, config: WorkflowConfig) -> list[str]:
        for service in ("shop-api", "payments-mock"):
            action = Action(
                reasoning="patrol: read current health metrics",
                kind="query_metrics",
                args={"service": service, "window_minutes": 5},
            )
            try:
                obs = await workflow.execute_activity(
                    run_tool,
                    args=[action],
                    start_to_close_timeout=timedelta(seconds=20),
                )
            except ActivityError as exc:
                workflow.logger.warning("patrol could not reach %s: %s", service, exc)
                continue

            rate = _error_rate(obs)
            if rate is not None and rate > ERROR_THRESHOLD:
                alert = Alert(
                    alert_id=f"patrol-{service}-{workflow.now().timestamp()}",
                    service=service,
                    severity="high",
                    summary=f"health patrol: error rate {rate:.3f} above {ERROR_THRESHOLD}",
                    source="patrol",
                )
                await self._open_incident(alert, config)
                self.findings.append(f"{service}: opened incident at error rate {rate:.3f}")
            else:
                self.findings.append(f"{service}: healthy")

        return self.findings

    async def _open_incident(self, alert: Alert, config: WorkflowConfig) -> None:
        """Start the incident workflow, attaching to an existing one if present."""
        from temporalio.client import Client

        client: Client = workflow.external_client()
        try:
            await client.start_workflow(
                "IncidentWorkflow.run",
                args=[alert, config, ""],
                id=f"incident-{alert.service}-{alert.alert_id}",
                task_queue=config.task_queue,
                id_conflict_policy="USE_EXISTING",
            )
            workflow.logger.info("patrol started incident for %s", alert.service)
        except Exception as exc:  # noqa: BLE001 - patrol must not fail the schedule
            workflow.logger.warning("patrol could not start incident: %s", exc)


def _error_rate(obs: Observation) -> float | None:
    """Pull error_rate out of a metrics observation's JSON detail."""
    try:
        return float(json.loads(obs.detail).get("error_rate"))
    except (ValueError, TypeError, KeyError):
        return None


from oncall_hero.activities.tools import run_tool  # noqa: E402