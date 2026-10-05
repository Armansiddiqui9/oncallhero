"""Unit tests for models and state compaction."""

from __future__ import annotations

import pytest

from oncall_hero.models import (
    Action,
    Alert,
    Budget,
    IncidentState,
    Observation,
    Plan,
    RemediationStep,
    TimelineEvent,
)


def _state() -> IncidentState:
    alert = Alert(alert_id="a1", service="shop-api", summary="5xx high")
    return IncidentState(incident_id="i1", alert=alert)


class TestIncidentState:
    def test_record_appends_observation_and_timeline(self):
        s = _state()
        action = Action(reasoning="r", kind="query_logs", args={})
        obs = Observation(action_kind="query_logs", summary="found logs", detail="detail")
        s.record(action, obs)
        assert len(s.observations) == 1
        assert s.budget.steps_used == 1
        assert len(s.timeline) == 1
        assert s.timeline[0].message == "query_logs: found logs"

    def test_prompt_view_includes_budget(self):
        s = _state()
        view = s.prompt_view()
        assert "steps left: 10" in view
        assert "tokens left: 40000" in view

    def test_prompt_view_compacts_history(self):
        s = _state()
        for i in range(6):
            s.record(
                Action(reasoning="r", kind="query_logs", args={}),
                Observation(action_kind="query_logs", summary=f"obs {i}", detail=f"detail {i}"),
            )
        view = s.prompt_view()
        # Older observations are summarized (one line), last 3 detailed
        assert "obs 0" in view
        assert "obs 5" in view
        assert view.count("detail") == 3  # only last 3 detailed

    def test_log_appends_timeline(self):
        s = _state()
        s.log("hello", extra="data")
        assert s.timeline[-1].message == "hello"
        assert s.timeline[-1].detail == {"extra": "data"}


class TestBudget:
    def test_budget_defaults(self):
        b = Budget()
        assert b.max_steps == 10
        assert b.max_tokens == 40000
        assert b.max_cost_usd == 0.25

    def test_budget_exhaustion(self):
        s = _state()
        s.budget.steps_used = 10
        assert s.budget.steps_used >= s.budget.max_steps


class TestPlan:
    def test_plan_model(self):
        plan = Plan(
            diagnosis="d",
            evidence=["e"],
            steps=[
                RemediationStep(
                    kind="rollback_deploy",
                    target="shop-api",
                    params={"to_version": "2.4.0"},
                    risk="low",
                    rationale="r",
                )
            ],
        )
        assert plan.steps[0].kind == "rollback_deploy"

    def test_action_schema(self):
        action = Action(reasoning="because", kind="finish", args={"diagnosis": "x"})
        assert action.kind == "finish"

    def test_action_reasoning_max_length(self):
        with pytest.raises(Exception):
            Action(reasoning="x" * 700, kind="finish", args={})
