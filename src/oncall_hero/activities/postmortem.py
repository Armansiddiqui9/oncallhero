"""Post-mortem activity: write postmortems/<incident_id>.md from the timeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from temporalio import activity

from oncall_hero.models import IncidentState


@activity.defn
async def write_postmortem(state_json: str) -> str:
    """Produce postmortems/<incident_id>.md from the incident timeline."""
    state = IncidentState.model_validate_json(state_json)

    now = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# Post-mortem: {state.incident_id}",
        "",
        f"Generated: {now}",
        f"Alert: {state.alert.summary}",
        f"Service: {state.alert.service}",
        f"Severity: {state.alert.severity}",
        f"Status: {state.phase.value}",
        "",
        "## Diagnosis",
        state.plan.diagnosis if state.plan else state.observations[-1].summary if state.observations else "",
        "",
        "## Evidence",
    ]
    for ev in state.plan.evidence if state.plan else []:
        lines.append(f"- {ev}")
    lines.append("")
    lines.append("## Timeline")
    for event in state.timeline[-50:]:
        lines.append(f"- [{event.phase}] {event.message}")
    lines.append("")
    lines.append("## Actions taken")
    if state.plan and state.plan.steps:
        for step in state.plan.steps:
            comp = f" (compensated by {step.compensation.kind} {step.compensation.target})" if step.compensation else " (non-compensable)"
            lines.append(f"- {step.kind} {step.target} {step.params}{comp}")
    else:
        lines.append("- none (silence means no action)")
    lines.append("")
    if state.human_edits:
        lines.append("## Human edits")
        for edit in state.human_edits:
            lines.append(f"- {edit}")
        lines.append("")
    lines.append("## Follow-ups")
    lines.append("- [ ] Review deploy process for the failing version")
    lines.append("- [ ] Add automated alert on 5xx rate")
    lines.append("")

    out_dir = Path("postmortems")
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"{state.incident_id}.md"
    path.write_text("\n".join(lines))
    state.postmortem = path.name
    return path.name
