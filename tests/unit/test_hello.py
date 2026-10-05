"""Hello world workflow smoke test (Phase 0 Gate 0).

Validates: dev server connects, Pydantic data converter round-trips, workflow +
activity execute end-to-end, result visible via handle.result().
"""

from __future__ import annotations

import pytest
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment

from oncall_hero.temporal.hello import HelloWorkflow, hello_world

pytestmark = pytest.mark.asyncio


async def test_hello_world_pyndantic_converter() -> None:
    """Hello workflow + activity runs end to end with Pydantic converter."""
    async with WorkflowEnvironment(start_time_skipping=False) as env:
        client = await Client.connect(
            env.service_client.config.target_host,
            data_converter=pydantic_data_converter,
        )
        handle = await client.start_workflow(
            HelloWorkflow.run,
            args=["Temporal"],
            id="hello-world-smoke-test",
            task_queue="oncall",
        )
        result = await handle.result()
        assert result == "Hello, Temporal!"
