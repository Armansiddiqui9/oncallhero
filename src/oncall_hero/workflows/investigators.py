"""Investigator child workflows (P1, behind a feature flag).

In INVESTIGATE the parent can fan out parallel investigators for logs, metrics
and deploys. Each runs one focused tool call and returns a Finding; the parent
merges them. In the Temporal Web UI this renders as a clean tree.

Enable with `agent.parallel_investigators: true` in config.yaml.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from oncall_hero.models import Action, Alert, Finding


async def _investigate(alert: Alert, kind: str, args: dict[str, object], source: str) -> Finding:
    """Run one focused tool call and wrap the result as a Finding."""
    action = Action(reasoning=f"investigate via {kind}", kind=kind, args=args)  # type: ignore[arg-type]
    try:
        obs = await workflow.execute_activity(
            run_tool,
            args=[action],
            start_to_close_timeout=timedelta(seconds=30),
        )
    except ActivityError as exc:
        return Finding(source=source, summary=f"{source} investigation failed: {exc}")
    return Finding(source=source, summary=obs.summary, evidence=[obs.detail])


@workflow.defn
class LogInvestigator:
    """Focused investigator: dig through error logs."""

    @workflow.run
    async def run(self, alert: Alert) -> Finding:
        return await _investigate(
            alert,
            "query_logs",
            {"service": alert.service, "level": "ERROR", "last_minutes": 15},
            "logs",
        )


@workflow.defn
class MetricsInvestigator:
    """Focused investigator: read error rate and latency."""

    @workflow.run
    async def run(self, alert: Alert) -> Finding:
        return await _investigate(
            alert,
            "query_metrics",
            {"service": alert.service, "window_minutes": 5},
            "metrics",
        )


@workflow.defn
class DeployInvestigator:
    """Focused investigator: check deploy history for a correlation."""

    @workflow.run
    async def run(self, alert: Alert) -> Finding:
        return await _investigate(
            alert,
            "get_recent_deploys",
            {"service": alert.service, "limit": 5},
            "deploys",
        )


async def fan_out(alert: Alert, workflow_id: str) -> list[Finding]:
    """Run all three investigators concurrently and merge their findings.

    Called from the parent workflow when parallel_investigators is enabled.
    """
    results = await asyncio.gather(
        workflow.execute_child_workflow(
            LogInvestigator.run,
            args=[alert],
            id=f"{workflow_id}-logs",
        ),
        workflow.execute_child_workflow(
            MetricsInvestigator.run,
            args=[alert],
            id=f"{workflow_id}-metrics",
        ),
        workflow.execute_child_workflow(
            DeployInvestigator.run,
            args=[alert],
            id=f"{workflow_id}-deploys",
        ),
    )
    return list(results)


from temporalio.exceptions import ActivityError  # noqa: E402
from oncall_hero.activities.tools import run_tool  # noqa: E402