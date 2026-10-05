"""Temporal client helper.

Connects to the dev server with the Pydantic data converter so all
workflow/activity payloads are typed.
"""

from __future__ import annotations

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from oncall_hero.config import load_config

config = load_config()


async def client() -> Client:
    """Create a Temporal client with the Pydantic data converter."""
    return await Client.connect(
        config.temporal_address,
        namespace=config.namespace,
        data_converter=pydantic_data_converter,
    )


async def worker(client: Client, workflows: list[type], activities: list[object]) -> Worker:
    """Create a worker registering workflows and activities."""
    return Worker(
        client,
        task_queue=config.task_queue,
        workflows=workflows,
        activities=activities,
    )


async def pydantic_client() -> Client:
    """Create a client with the Pydantic converter for direct API calls."""
    return await Client.connect(
        config.temporal_address,
        namespace=config.namespace,
        data_converter=pydantic_data_converter,
    )
