# Demo Script

Target: **2:30**. Rehearse twice. Have the Temporal Web UI open in a second tab.

| Time | Action | Say |
|---|---|---|
| 0:00 | Show UI with everything stopped | "Nothing is running. Most agents die with their process. Let's see this one not die." |
| 0:10 | Click **S1 Bad deploy** | "One click boots Temporal, the worker and the demo services, then fires an alert." |
| 0:25 | Timeline fills in | "The agent loop is a Temporal workflow. Every LLM and tool call is an activity." |
| 0:40 | Toggle **Chaos: everything on fire** | "Now tools throw 429s and time out." Point at retry badges |
| 0:55 | Click **Kill worker** | "I just killed the process running the agent." Banner appears |
| 1:05 | Open Temporal Web UI | "The workflow is still running on the server. Nothing was lost." |
| 1:15 | Click **Start worker** | "It resumes at the exact step, no re-doing finished work." |
| 1:25 | Plan appears, countdown visible | "It proposed rolling back to 2.4.0, and now it waits. This timer survives restarts. It could wait for hours." |
| 1:40 | Edit plan, click **Approve** | "Update with a validator. A bad edit would be rejected before it entered history." |
| 1:55 | Execute, verify, resolved. Show `executions: 1` | "Retries and chaos, still exactly one rollback." |
| 2:05 | Trigger **S5 Fix fails** (fast-forward) | "When verification fails, the saga undoes everything." |
| 2:20 | Show post-mortem and event history | "Everything is the event history. It is auditable and replayable." |

## Backup plan

If the live model misbehaves, the chain falls through to scripted. Say so honestly
and keep going, since the durability story does not depend on model quality.

## Terminal fallback commands

```bash
ohero kill worker    # hard-kill the worker (psutil, cross-platform)
ohero start worker   # bring it back
ohero status         # service table
ohero trigger s1_bad_deploy
ohero approve <incident-id>
```

## Recording

Record the demo as a 2–3 minute video and export a short GIF (kill worker → resume)
for the README.
