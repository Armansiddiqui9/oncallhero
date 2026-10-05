"""Unit tests for config loading."""

from __future__ import annotations

import os
from pathlib import Path

from oncall_hero.config import Config, load_config


class TestConfig:
    def test_defaults(self):
        cfg = load_config()
        assert cfg.temporal_address == "127.0.0.1:7233"
        assert cfg.task_queue == "oncall"
        assert cfg.gateway_port == 8000

    def test_demo_mode(self):
        cfg = load_config()
        # DEMO_MODE env not set in tests by default
        assert isinstance(cfg.demo_mode, bool)

    def test_approval_chain(self):
        cfg = load_config()
        chain = cfg.approval_chain
        assert isinstance(chain, list)
        assert "name" in chain[0]
        assert "timeout_s" in chain[0]

    def test_llm_chain(self):
        cfg = load_config()
        chain = cfg.llm_chain
        assert isinstance(chain, list)
        assert len(chain) >= 1

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("TEMPORAL_ADDRESS", "127.0.0.1:9999")
        cfg = load_config()
        assert cfg.temporal_address == "127.0.0.1:9999"

    def test_config_object(self):
        cfg = Config({"temporal": {"address": "x"}, "agent": {"max_steps": 5}})
        assert cfg.temporal_address == "x"
        assert cfg.agent["max_steps"] == 5
