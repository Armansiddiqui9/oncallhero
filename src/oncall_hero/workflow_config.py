"""Workflow configuration, passed INTO the workflow as data.

The workflow must not read config.yaml itself (that is file I/O, which is
non-deterministic and forbidden in workflow code). The launcher reads the
config and passes it as a workflow argument, so it is recorded in history.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApprovalLevel(BaseModel):
    name: str
    timeout_s: int


class WorkflowConfig(BaseModel):
    """Everything the workflow needs, resolved before the workflow starts."""

    task_queue: str = "oncall"
    model_chain: list[str] = Field(default_factory=lambda: ["scripted/auto"])
    proposal_model: str | None = None
    llm_timeout_s: int = 120
    tool_timeout_s: int = 30
    mutation_timeout_s: int = 60
    verify_delay_s: int = 20
    approval_chain: list[ApprovalLevel] = Field(
        default_factory=lambda: [ApprovalLevel(name="primary", timeout_s=45)]
    )
    max_steps: int = 10