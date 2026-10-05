"""Hello world workflow + activity for sanity checks (Phase 0 smoke test).

Runs end to end with the Pydantic data converter. Delete after confirming
the dev server + converter work.
"""

from __future__ import annotations

from temporalio import activity, workflow


@activity.defn
async def hello_world(name: str) -> str:
    """A trivial activity that does not talk to Temporal internals."""
    return f"Hello, {name}!"


@workflow.defn
class HelloWorkflow:
    """Hello world workflow using Pydantic-converted payloads."""

    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            hello_world,
            args=[name],
            start_to_close_timeout=workflow.timedelta(seconds=30),
        )
