"""History -> timeline conversion.

The UI builds its timeline from the Temporal event history (works while
the worker is offline) rather than from queries. This module turns
history events into `TimelineEvent` records.
"""

from __future__ import annotations

import re
from typing import Any

from temporalio.api.enums.v1 import EventType as _EventType
from temporalio.api.workflowservice.v1 import GetWorkflowExecutionHistoryResponse as History


def _attribute_name(event_type: int) -> str:
    """Map an EventType to its oneof attribute field (e.g. timer_fired_event_attributes)."""
    name = _EventType.GetName(event_type).replace("EVENT_TYPE_", "")
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return f"{snake}_event_attributes"


def history_to_timeline(history: History) -> list[dict[str, Any]]:
    """Turn a Temporal workflow history into a TimelineEvent[] for the UI."""
    events = []
    for event in history.history.events:
        kind = _EventType.GetName(event.event_type)
        attrs = getattr(event, _attribute_name(event.event_type), None)

        if event.event_type == _EventType.EVENT_TYPE_WORKFLOW_EXECUTION_STARTED:
            msg = "workflow started"
            detail = {}
        elif event.event_type == _EventType.EVENT_TYPE_ACTIVITY_TASK_STARTED:
            msg = f"activity started: {attrs.activity_type}"
            detail = {"attempt": getattr(attrs, "attempt", 1)}
        elif event.event_type == _EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED:
            detail = {"result": (attrs.result.decode()[:300] if attrs and attrs.result else "")}
            msg = f"activity completed: {attrs.activity_type}"
        elif event.event_type == _EventType.EVENT_TYPE_ACTIVITY_TASK_FAILED:
            detail = {
                "failure": attrs.failure.failure_message if attrs and attrs.failure else "",
                "attempt": getattr(attrs, "attempt", 1),
            }
            msg = f"activity failed: {attrs.activity_type}"
        elif event.event_type == _EventType.EVENT_TYPE_TIMER_FIRED:
            detail = {"started_event_id": attrs.started_event_id}
            msg = "durable timer fired"
        elif event.event_type == _EventType.EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED:
            detail = {"result": (attrs.result.decode()[:300] if attrs and attrs.result else "")}
            msg = "workflow completed"
        elif event.event_type == _EventType.EVENT_TYPE_WORKFLOW_EXECUTION_FAILED:
            detail = {"failure": attrs.failure.failure_message if attrs and attrs.failure else ""}
            msg = "workflow failed"
        else:
            continue

        events.append({"kind": kind, "message": msg, "detail": detail, "event_id": event.event_id})
    return events