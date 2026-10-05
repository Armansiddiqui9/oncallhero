# On-Call Hero — Durable AI SRE Agent

> **What it is:** A crash-resistant AI incident-response agent built on Temporal. It investigates outages, asks a human before acting, waits as long as needed, executes fixes, verifies results, and rolls back safely — resuming from the exact step after any kill or crash.
>
> **Port:** `http://127.0.0.1:8000` (gateway + dark UI + SSE stream)

---

## Why use this?

| Advantage | What you get |
|---|---|
| **Durable execution** | Temporal workflows survive process kills, server restarts, and network drops — no lost progress |
| **Human-in-the-loop** | Every action requires approval (or edit/reject) before execution — safe for production |
| **Crash recovery proof** | `make kill-worker` → banner "offline, safe" → restart → resumes exact step |
| **Dark, projector-ready UI** | High-contrast theme at `:8000`; runs directly on your laptop (localhost only) |
| **Scripted / offline tests** | `make test` runs replay + scripted LLM — no external API needed |
| **Safety rules (11)** | Allowlist (world group only), sanitize `<untrusted_data>`, plan validator, prompt-injection hardening (S6), idempotency keys, budgets, audit trail |

---

## Quickstart (Windows PowerShell)

```powershell
# 1. Install
pip install --upgrade hatchling build pip
pip install -e ".[dev]"

# 2. Start everything + open UI
make up              # gateway on http://127.0.0.1:8000

# 3. Try a scenario
# Open http://127.0.0.1:8000 → click "S1 Bad deploy"
# Timeline fills; use Approve / Edit / Reject buttons

# 4. Test durability
make kill-worker     # worker dies
# Banner shows "offline, safe"
make up              # restart → resumes exact workflow step

# 5. Chaos / resilience
make chaos --preset everything_on_fire
```

---

## Ports

| Service | Port | Note |
|---|---|---|
| Gateway (UI + API + SSE) | **8000** | `ohero up` starts this |
| Temporal server (gRPC) | 7233 | Durable state (SQLite) |
| Temporal Web UI | 8233 | Inspect workflows |
| `shop-api` | 9001 | Mock service |
| `payments-mock` | 9002 | Mock service |
| Ollama (optional) | 11434 | Local LLM |

---

## Commands

```powershell
# Start / stop
make up / make down

# Full stack control
make stack up | down | status

# CLI (after gateway running)
ohero status
ohero trigger s1_bad_deploy
ohero approve <incident-id>
ohero chaos --preset everything_on_fire

# Tests
make test        # unit + replay + scripted LLM (offline)
make test-int    # needs running stack
make lint
make models      # check Ollama / Anthropic / LiteLLM
```

---

## Requirements

- Python 3.11+
- `uv` or `pip`
- Temporal CLI (`brew install temporal` or install script)
- Optionally Ollama (`ollama pull qwen2.5:14b`)

Install dependencies: `pip install -r requirements.txt`

---

## Project structure

- `src/oncall_hero/cli.py` — CLI (`ohero`)
- `src/oncall_hero/gateway/app.py` — FastAPI gateway (`:8000`)
- `src/oncall_hero/gateway/static/` — Dark UI (`index.html`, `app.js`, `style.css`)
- `src/oncall_hero/workflows/incident.py` — `IncidentWorkflow`
- `runbooks/` — Incident response guides
- `scenarios/` — S1–S6 failure scenarios
- `tests/` — Replay / scripted tests

---

## Full usage guide (from original README)

**What it provides**
- Durable `IncidentWorkflow` (TRIAGE → INVESTIGATE → PROPOSE → AWAITING_APPROVAL → EXECUTE → VERIFY → ROLLBACK → RESOLVED) with agent loop via activities
- FastAPI gateway + SSE stream + static dark-theme UI (`localhost:8000`) — projector-readable, high-contrast
- Mock world: `shop-api` (9001), `payments-mock` (9002), scenarios S1–S6, runbooks in `runbooks/`
- LLM layer: LiteLLM wrapper — scripted deterministic replay (CI/tests), Ollama local (11434), Anthropic fallback
- Safety (11 rules): allowlist (world group only), sanitize (`<untrusted_data>`), plan validator, edited-plan re-validation, prompt-injection hardening (S6 automated test), idempotency keys (`workflow_id:activity_id`), budgets, audit trail via Temporal event history, supervisor isolation, localhost only
- Temporal primitives: Workflow, Activities, Retry + backoff, Non-retryable errors, Timeouts, Heartbeat, Signal (`pause`/`resume`/`cancel`), Update + validator (`approve`/`reject`), Query (`status`/`timeline`/`budget`), Durable timer, Saga rollback, Search attributes, Workflow-ID dedup, Pydantic converter, Replay + time-skipping tests

**Quickstart (5 min)**
`git clone ...; pip install -r requirements.txt; make up; click "S1 Bad deploy"`

---
