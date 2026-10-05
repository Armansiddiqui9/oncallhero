"""Configuration loading: config.yaml + .env + DEMO_MODE flag."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from oncall_hero.workflow_config import WorkflowConfig


class Config:
    """Typed access to config.yaml with env overrides."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @property
    def temporal_address(self) -> str:
        return os.environ.get("TEMPORAL_ADDRESS", self._data.get("temporal", {}).get("address", "127.0.0.1:7233"))

    @property
    def task_queue(self) -> str:
        return os.environ.get("TEMPORAL_TASK_QUEUE", self._data.get("temporal", {}).get("task_queue", "oncall"))

    @property
    def namespace(self) -> str:
        return self._data.get("temporal", {}).get("namespace", "default")

    @property
    def db_filename(self) -> str:
        return self._data.get("temporal", {}).get("db_filename", ".run/temporal.db")

    @property
    def ui_port(self) -> int:
        return int(self._data.get("temporal", {}).get("ui_port", 8233))

    @property
    def demo_mode(self) -> bool:
        return os.environ.get("DEMO_MODE", "false").lower() in ("1", "true", "yes")

    @property
    def llm_provider(self) -> str:
        return os.environ.get("LLM_PROVIDER", "chain")

    @property
    def llm_chain(self) -> list[str]:
        chain = self._data.get("llm", {}).get("chain", ["scripted/auto"])
        if self.llm_provider == "scripted":
            return ["scripted/auto"]
        if self.llm_provider == "ollama":
            return [c for c in chain if c.startswith("ollama")] or ["scripted/auto"]
        if self.llm_provider == "anthropic":
            return [c for c in chain if c.startswith("anthropic")] or ["scripted/auto"]
        return chain

    @property
    def llm_timeout_s(self) -> int:
        return int(self._data.get("llm", {}).get("timeout_s", 120))

    @property
    def llm_temperature(self) -> float:
        return float(self._data.get("llm", {}).get("temperature", 0.1))

    @property
    def ollama_api_base(self) -> str:
        return os.environ.get("OLLAMA_API_BASE", self._data.get("llm", {}).get("ollama", {}).get("api_base", "http://127.0.0.1:11434"))

    @property
    def agent(self) -> dict[str, Any]:
        agent = self._data.get("agent", {})
        if not isinstance(agent, dict):
            return {"max_steps": 10}
        agent.setdefault("max_steps", 10)
        return agent

    @property
    def approval_chain(self) -> list[dict[str, Any]]:
        key = "demo" if self.demo_mode else "default"
        return self._data.get("approval", {}).get(key, {}).get("chain", [{"name": "primary", "timeout_s": 45}])

    @property
    def verify_delay_s(self) -> int:
        key = "delay_s_demo" if self.demo_mode else "delay_s_default"
        return int(self._data.get("verify", {}).get(key, 20))

    @property
    def gateway_host(self) -> str:
        return os.environ.get("GATEWAY_HOST", "127.0.0.1")

    @property
    def gateway_port(self) -> int:
        return int(os.environ.get("GATEWAY_PORT", "8000"))

    def as_dict(self) -> dict[str, Any]:
        """Effective config with secrets redacted."""
        data = json.loads(yaml.safe_dump(self._data))
        if "llm" in data and isinstance(data["llm"], dict):
            data["llm"].pop("api_key", None)
        return data

    def workflow_config(self) -> "WorkflowConfig":
        """Build the config the workflow needs, resolved outside the workflow.

        The workflow must not read config.yaml (that is file I/O). This is
        called by the gateway/CLI and passed in as a workflow argument.
        """
        from oncall_hero.workflow_config import ApprovalLevel, WorkflowConfig

        agent = self.agent
        return WorkflowConfig(
            task_queue=self.task_queue,
            model_chain=self.llm_chain,
            proposal_model=self._data.get("llm", {}).get("proposal_model") or None,
            llm_timeout_s=self.llm_timeout_s,
            tool_timeout_s=int(self._data.get("agent", {}).get("tool_timeout_s", 30)),
            mutation_timeout_s=int(self._data.get("agent", {}).get("mutation_timeout_s", 60)),
            verify_delay_s=self.verify_delay_s,
            approval_chain=[
                ApprovalLevel(name=lv.get("name", "primary"), timeout_s=int(lv.get("timeout_s", 45)))
                for lv in self.approval_chain
            ],
            max_steps=int(agent.get("max_steps", 10)),
        )


@lru_cache(maxsize=1)
def load_config() -> Config:
    path = Path("config.yaml")
    if not path.exists():
        path = Path(__file__).parent.parent.parent / "config.yaml"
    if path.exists():
        with path.open() as fh:
            data = yaml.safe_load(fh) or {}
    else:
        data = {}
    return Config(data)
