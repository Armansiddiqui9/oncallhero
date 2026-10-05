"""Chaos settings: read .run/chaos.json on every call so changes apply instantly."""

from __future__ import annotations

import json
from pathlib import Path

_CHAOS_FILE = Path(".run/chaos.json")
_DEFAULTS: dict = {
    "tool_error_rate": 0.0,
    "tool_latency_ms": 0,
    "tool_timeout_rate": 0.0,
    "llm_outage": False,
    "llm_garbage_rate": 0.0,
    "duplicate_mutation": False,
}


def chaos() -> dict:
    """Return current chaos settings (defaults when file missing)."""
    try:
        if _CHAOS_FILE.exists():
            data = json.loads(_CHAOS_FILE.read_text())
            merged = {**_DEFAULTS, **data}
            return merged
    except Exception:  # noqa: BLE001 - corrupted chaos file falls back to defaults
        pass
    return dict(_DEFAULTS)


def set_chaos(settings: dict) -> dict:
    """Write chaos settings; take effect on the next tool/LLM call."""
    _CHAOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged = {**_DEFAULTS, **settings}
    _CHAOS_FILE.write_text(json.dumps(merged, indent=2))
    return merged


def preset(name: str) -> dict | None:
    presets = {
        "everything_on_fire": {
            "tool_error_rate": 0.3,
            "tool_latency_ms": 3000,
            "llm_garbage_rate": 0.1,
        },
        "flaky_tools": {"tool_error_rate": 0.5, "tool_latency_ms": 1000},
        "slow_tools": {"tool_latency_ms": 5000},
        "garbage_llm": {"llm_garbage_rate": 0.5},
        "llm_outage": {"llm_outage": True},
        "duplicate_mutation": {"duplicate_mutation": True},
    }
    return presets.get(name)
