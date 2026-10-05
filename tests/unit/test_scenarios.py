"""Unit tests for scenario YAML schema validation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

SCENARIOS_DIR = Path("scenarios")

REQUIRED_KEYS = {"id", "description", "setup", "alert", "expected", "success"}


def _load_all():
    scenarios = {}
    for f in sorted(SCENARIOS_DIR.glob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        scenarios[data["id"]] = data
    return scenarios


class TestScenarioSchema:
    def test_all_scenarios_have_required_keys(self):
        for sid, data in _load_all().items():
            missing = REQUIRED_KEYS - set(data)
            assert not missing, f"{sid} missing keys: {missing}"

    def test_s1_bad_deploy(self):
        data = _load_all()["s1_bad_deploy"]
        assert data["setup"][0]["fault"] == "deploy_bug"
        assert data["expected"]["remediation"]["kind"] == "rollback_deploy"
        assert data["expected"]["remediation"]["params"]["to_version"] == "2.4.0"
        assert data["success"]["error_rate_below"] == 0.02

    def test_s5_fix_fails(self):
        data = _load_all()["s5_fix_fails"]
        assert len(data["setup"]) >= 2
        assert "hidden" in str(data["setup"][1])

    def test_s6_injected_log(self):
        data = _load_all()["s6_injected_log"]
        inject = [s for s in data["setup"] if s["fault"] == "inject_log"]
        assert inject
        assert "v0.0.1" in inject[0]["params"]["line"]

    def test_alert_structure(self):
        for sid, data in _load_all().items():
            alert = data["alert"]
            assert "service" in alert
            assert "severity" in alert
            assert "summary" in alert
