# Architecture

## Overview

On-Call Hero is a durable AI SRE agent built on Temporal. The agent loop is a
Temporal workflow; every LLM call and every tool call is an activity; the human
is an update; waiting is a durable timer. Kill any process at any moment and the
agent resumes from the exact step.

```
┌─────────────┐     HTTP/SSE      ┌──────────────────────────┐
│   Browser   │ ◄───────────────► │  Gateway (ohero)         │
│  (static UI)│                   │  FastAPI + supervisor    │
└─────────────┘                   └──────────┬───────────────┘
                                             │ start/signal/update/query
                                             ▼
                                   ┌───────────────────────┐
                                   │  Temporal dev server  │
                                   │  (SQLite persisted)   │
                                   └───────────┬───────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
              ┌────────────────┐                            ┌────────────────┐
              │    Worker      │                            │  Demo world    │
              │  workflows +   │ ── tool activities ───────► │  shop-api      │
              │  activities    │                            │  payments-mock │
              └───────┬────────┘                            └────────────────┘
                      │ LLM calls
                      ▼
              ┌────────────────┐
              │  LLM provider  │
              │ Ollama/Anthropic│
              │  /scripted     │
              └────────────────┘
```

## Components

| Component | Role | Port |
|---|---|---|
| Temporal dev server | Durable execution engine | 7233 (gRPC), 8233 (Web UI) |
| Gateway (`ohero`) | FastAPI + SSE + static UI + process supervisor | 8000 |
| Worker | Hosts workflows and activities | none |
| shop-api | Mock victim service | 9001 |
| payments-mock | Second mock service | 9002 |
| Ollama (optional) | Local LLM server | 11434 |

## The golden rule

- **Workflow code:** deterministic orchestration only. State, decisions on state, timers, waits, branching.
- **Activity code:** everything with side effects or non-determinism. LLM calls, HTTP, file reads, randomness, time.

## Incident state machine

```
TRIAGE → INVESTIGATE → PROPOSE → AWAITING_APPROVAL → EXECUTE → VERIFY → RESOLVED
                                    ↓                        ↓
                              CLOSED_NO_ACTION            ROLLBACK → ESCALATED
```

## Durability guarantees

1. **Crash-proof (G1):** the workflow survives `kill -9` of the worker at any point.
2. **Exactly-once (G2):** every mutation is keyed by `workflow_id:activity_id`; the
   demo world records executions per key and returns the stored result on retry.
3. **Human-safe (G3):** nothing mutates without approval; silence means no action.
4. **Self-undoing (G4):** if verification fails, the saga rolls back compensations in reverse order.

## Exactly-once design

```python
@activity.defn
async def execute_step(step: RemediationStep) -> StepResult:
    info = activity.info()
    key = f"{info.workflow_id}:{info.activity_id}"   # stable across retries
    return await world_client.apply(step, idempotency_key=key)
```

`shop-api` stores `key -> result`. A retried call returns the stored result and
the executions counter stays at 1.

## Safety model

1. Closed action space (the LLM picks from enums).
2. Read-only investigation; mutations only after approval.
3. Silence means no action.
4. Deterministic plan validation (kinds, targets, versions, compensation).
5. Edited plans are re-validated by the update validator.
6. Prompt-injection hardening: tool output wrapped in `<untrusted_data>`.
7. Idempotency keys from workflow ID + activity ID.
8. Budgets for steps, tokens, dollars, time.
9. Audit trail: the Temporal event history is the immutable record.
10. Supervisor isolation: platform services unreachable from agent actions.
11. Localhost only.
12. Secrets in `.env` (git-ignored); config endpoint redacts keys.
