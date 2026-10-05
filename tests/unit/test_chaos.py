"""Unit tests for chaos settings."""

from __future__ import annotations

import json
from pathlib import Path

from oncall_hero.chaos import chaos, preset, set_chaos


class TestChaos:
    def test_defaults(self):
        settings = chaos()
        assert settings["tool_error_rate"] == 0.0
        assert settings["tool_latency_ms"] == 0

    def test_set_and_read(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        Path(".run").mkdir()
        set_chaos({"tool_error_rate": 0.5})
        assert chaos()["tool_error_rate"] == 0.5

    def test_presets(self):
        p = preset("everything_on_fire")
        assert p["tool_error_rate"] == 0.3
        assert p["tool_latency_ms"] == 3000
        assert preset("nonexistent") is None

    def test_corrupted_file_falls_back(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        Path(".run").mkdir()
        Path(".run/chaos.json").write_text("not json")
        assert chaos()["tool_error_rate"] == 0.0
