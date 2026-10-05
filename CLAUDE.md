# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: On-Call Hero (Durable AI SRE Agent)

Built on Temporal. Investigates incidents via a durable `IncidentWorkflow` (TRIAGE → INVESTIGATE → PROPOSE → AWAITING_APPROVAL → EXECUTE → VERIFY → ROLLBACK → RESOLVED) with human-in-the-loop approvals via signals/updates.

## Commands

- Install: `pip install -e ".[dev]"` (or `uv sync --system-certs`); fix `pyproject.toml` classifier line 33 (`Distributed Applications` → valid classifier)
- Build/test: `make test` (unit + workflow + replay, scripted LLM, no network), `make test-int` (needs running stack), `make lint`, `make models`
- Start stack (Windows PowerShell): `make up` → `http://127.0.0.1:8000`; `make dev-scripted` (scripted LLM, offline); `make dev-local` (Ollama); `make down`
- CLI: `python -m oncall_hero.cli up|down|status|trigger <scenario>|approve|reject <incident>|chaos --preset ...`
- Single test: `python -m pytest tests/unit/test_safety.py -q -k <name>`; replay tests: `python -m pytest tests/replay -q`
- Lint/format: `python -m ruff check .` and `python -m ruff format --check .`
- Verify import: `python -c "import sys; sys.path.insert(0,'src'); import oncall_hero.workflows.incident; print('OK')"`

## Architecture (multi-file understanding required)

- **Workflow determinism**: `src/oncall_hero/workflows/incident.py` has the golden rule — only deterministic orchestration here; all I/O, LLM, randomness, time live in activities (`src/oncall_hero/activities/`). Config arrives as `WorkflowConfig` argument, never read from disk inside workflow.
- **Safety layer** (`src/oncall_hero/safety/`): allowlist (`validate_plan_against_allowlist`), sanitize (`<untrusted_data>`), validators, prompt-injection hardening (S6 automated test), idempotency keys (`workflow_id:activity_id`).
- **LLM layer** (`src/oncall_hero/llm/`): `scripted.py` is deterministic replay for CI/demo (labelled clearly), `provider.py` routes to ollama/anthropic/chain, `prompts.py`. Scripted replays scenarios S1–S6 from `config.yaml`.
- **Temporal setup**: `temporal/client.py`, `temporal/worker.py`, `temporal/setup.py`; server on 7233 (gRPC) / 8233 (Web UI); task queue `oncall`; namespace `default`.
- **Gateway** (`gateway/app.py` + `routes_stack.py`/`routes_incidents.py` + `sse.py`): FastAPI on 8000; SSE stream; dark-theme static UI (`gateway/static/index.html`); supervisor health checks (`supervisor/`).
- **Mock world**: `shop-api` (9001), `payments-mock` (9002), scenarios S1–S6, runbooks in `runbooks/`.
- **Config**: `config.yaml` (scenarios, LLM settings, timeouts); `.env.example` (secrets never committed); `workflow_config.py` defines `WorkflowConfig`/`ApprovalLevel` passed into workflows.
- **Durability**: Retry policies (`TOOL_RETRY`, `LLM_RETRY`, `MUTATION_RETRY`) defined once; signals (`pause`/`resume`/`cancel`); Updates with validator (`approve`/`reject`); Query (`status`/`timeline`/`budget`); Durable timer; Saga rollback; Search attributes; Workflow-ID dedup; Replay + time-skipping tests (`tests/replay/test_replay.py`).

## Key constraints

- All workflow code must be deterministic; no file I/O, no `random`, no `time.time()` inside `@workflow.run`. Use `workflow.sleep` / `timer`.
- LLM calls go through activities (`activities/llm.py`); never call LLM directly in workflow.
- Safety rules: allowlist (world group only), sanitize untrusted data, plan validator, edited-plan re-validation, 11 rules total.
- Tests must work with `LLM_PROVIDER=scripted`; `make dev-scripted` runs fully offline.

## Importable foreign-agent configs

Found `~/.codex/config.toml` (Codex). Reply `/import` to scan importable items (MCP servers, slash commands, subagents, skills, instructions), then `/import --yes=<digest>` to apply user-level items safely.
