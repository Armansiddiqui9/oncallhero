"""Replay tests: saved histories replay without non-determinism errors."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.workflow import Replayer

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_replay_saved_histories() -> None:
    """All recorded histories replay cleanly."""
    from oncall_hero.workflows.incident import IncidentWorkflow
    from temporalio.client import Client

    client = await Client.connect("127.0.0.1:7233")

    histories_dir = Path("tests/histories")
    if not histories_dir.exists():
        pytest.skip("no saved histories yet (record with python scripts/record_history.py)")
    hist_files = list(histories_dir.glob("*.json"))
    if not hist_files:
        pytest.skip("no history files found")

    replayer = Replayer(
        workflows=[IncidentWorkflow],
        task_queue="oncall",
        data_converter=client.data_converter,
    )
    for f in hist_files:
        await replayer.replay_from_json(f)
