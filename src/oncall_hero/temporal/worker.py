"""Worker entry point: registers workflows and activities.

Run with: python -m oncall_hero.temporal.worker
"""

from __future__ import annotations

import asyncio

from temporalio.worker import Worker

from oncall_hero.activities.llm import llm_decide, propose_remediation
from oncall_hero.activities.notify import notify_human
from oncall_hero.activities.postmortem import write_postmortem
from oncall_hero.activities.remediation import check_health, execute_step, run_compensation
from oncall_hero.activities.tools import (
    finish,
    get_recent_deploys,
    get_service_status,
    query_logs,
    query_metrics,
    run_tool,
    search_runbooks,
)
from oncall_hero.config import load_config
from oncall_hero.temporal.client import client as temporal_client
from oncall_hero.workflows.incident import IncidentWorkflow
from oncall_hero.workflows.patrol import HealthPatrolWorkflow

config = load_config()


async def main() -> None:
    client = await temporal_client()
    async with Worker(
        client,
        task_queue=config.task_queue,
        workflows=[IncidentWorkflow, HealthPatrolWorkflow],
        activities=[
            llm_decide,
            propose_remediation,
            notify_human,
            write_postmortem,
            check_health,
            execute_step,
            run_compensation,
            query_logs,
            query_metrics,
            get_recent_deploys,
            get_service_status,
            search_runbooks,
            run_tool,
            finish,
        ],
    ) as worker:
        print(f"Worker started on task queue {config.task_queue}", flush=True)
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
