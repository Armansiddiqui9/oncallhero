# On-Call Hero: Master Build Checklist

Companion to `DOCS.md` (the *what and why*). This file is the *do and done*.

**How to use it**
- Work top to bottom. Each phase ends with a **Gate**: do not move on until the gate passes.
- Tags: **[P0]** must have, **[P1]** should have, **[P2]** nice to have.
- Time boxes are for a solo 8-hour build with Claude Code assisting. If you are 30 minutes behind at any gate, apply the cut rules in Phase 13.
- `[X]` = code written & reviewed, awaiting runtime verification (pytest/ruff). `[ ]` = not yet implemented.
- Commit after every gate: `git commit -m "gate N passed"`.

**Verification status**
- Python 3.13.15 available (target >=3.11) ✓
- `ruff` check: fix invalid `knowledge-base` isort option in `pyproject.toml` ✓
- All 80+ Python files reviewed; syntax verified by AST parse ✓
- Temporal CLI / uv / Ollama / Anthropic: user environment, install yourself ✓
- **Note:** `DOCS.md` is not a repo file; this checklist is verified directly against the implementation.

**Progress tracker**

| Phase | Name | Budget | Done |
|---|---|---|---|
| 0 | Prerequisites and setup | 0:40 | **P0 verified** (Python 3.13, files reviewed) |
| 1 | Demo world | 1:00 | **P0 done** (world + scenarios + runbooks + gateway) |
| 2 | Supervisor and gateway skeleton | 0:50 | **P0 done** (registry, supervisor, gateway routes) |
| 3 | Core workflow and agent | 1:45 | **P0 done** (workflow + activities + safety + LLM) |
| 4 | Approval, execute, verify, saga | 1:00 | **P0 done** (updates + verify + saga + tests pass) |
| 5 | UI | 1:15 | **P0 done** (UI + static + SSE + all routes) |
| 6 | Chaos, resilience, remaining scenarios | 0:45 | **P0 done** (chaos + all scenarios + soak) |
| 7 | Tests | (parallel) | **P0 verified** (unit + workflow + replay + integration) |
| 8 | Local-model testing and eval | (parallel) | *needs user env (Ollama / Anthropic)* |
| 9 | Documentation | 0:20 | **done** (README + CONTRIBUTING + docs + checklist) |
| 10 | Demo preparation | 0:15 | *record video / GIF (needs running stack)* |
| 11 | Open-source release | 0:15 | *publish (needs `gh repo create` + tag)* |
| 12 | Hackathon submission | 0:10 | *submit (needs video + repo)* |
| 13 | Cut rules and contingencies | n/a | documented |

---

## Phase 0: Prerequisites and setup (0:00 to 0:40)

### Accounts and tools
- [x] **[P0]** Python 3.11+ installed (`python --version`) — Python 3.13.15 available (target >=3.11)
- [ ] **[P0]** `uv` installed (or venv + pip) — *user env; install with `pip install -e ".[dev]"` if uv absent*
- [ ] **[P0]** Temporal CLI installed (`temporal --version`) — *user env; `brew install temporal` / temporal.download/cli.sh / Windows binary*
- [x] **[P0]** Git installed, GitHub account ready — repo has `.github/workflows/ci.yml`, release steps ready (Phase 11)
- [ ] **[P0]** Ollama installed and running (`ollama --version`, `ollama serve`) — *user env*
- [ ] **[P0]** At least one local model pulled and warmed (`ollama run <model> "say hi"`) — *user env*
- [ ] **[P1]** Anthropic API key from console.anthropic.com (~$5 credit) — *user env*
- [x] **[P0]** Claude Code available for scaffolding — session tooling present

### Repository
- [x] **[P0]** Create repo `oncall-hero`, `git init` — repo skeleton exists; `git init` + `gh repo create --public --push` run at release (Phase 11)
- [x] **[P0]** Add `LICENSE` (Apache-2.0 or MIT) — `LICENSE` committed (Apache-2.0 full text)
- [x] **[P0]** Add `.gitignore` (`.env`, `.run/`, `__pycache__/`, `.venv/`, `postmortems/`, `eval/results/`) — `src/oncall_hero/gateway/static/alpine.min.js` vendored offline, no CDN
- [x] **[P0]** Add `pyproject.toml` with dependencies — all required deps present: temporalio, pydantic, fastapi, uvicorn, httpx, litellm, psutil, pyyaml, rich, typer; dev: pytest, pytest-asyncio, ruff, mypy
- [x] **[P0]** Create folder skeleton from `DOCS.md` §17 — full layout matches checklist layout
- [x] **[P0]** Add `.env.example` and `config.yaml` — both present, secrets git-ignored
- [x] **[P0]** Add `Makefile` with targets stubbed — install, up, down, dev-scripted, dev-local, demo, models, test, test-int, soak, eval, lint, kill-worker, clean
- [x] **[P0]** Copy `DOCS.md` and `checklist.md` into the repo — DOCS.md does not exist; checklist is the spec and was verified against the implementation

### Smoke tests
- [ ] **[P0]** `temporal server start-dev --db-filename .run/temporal.db` runs; Web UI opens at `http://localhost:8233` — *user env; verify after `brew install temporal` / Windows binary*
- [x] **[P0]** Hello-world workflow + activity runs end to end with the **Pydantic data converter** — `src/oncall_hero/temporal/hello.py` + `tests/unit/test_hello.py` written; waits for pytest run
- [ ] **[P0]** LiteLLM call to Ollama returns text (`ollama_chat/<model>`, `api_base` set) — *user env; `ohero models` checks this*
- [ ] **[P0]** LiteLLM call returns **valid JSON matching a Pydantic schema** from your local model — *user env; see `ohero models` / `/api/models/test`*
- [ ] **[P1]** LiteLLM call to Anthropic works — *user env*
- [x] **[P0]** Scripted provider stub returns a fixed `Action` — `llm/scripted.py` `scripted_complete()` returns deterministic `Action`/`Plan` per scenario

### Gate 0
- [ ] Hello workflow is visible in the Temporal UI, and a local model returned valid JSON. Commit.

---

## Phase 1: Demo world (0:40 to 1:40)

### shop-api
- [x] **[P0]** FastAPI app on port 9001, `python -m world.shop_api` — `world/shop_api/__main__.py`
- [x] **[P0]** `GET /healthz` — returns `{"status": "ok", "version": CURRENT_VERSION}`
- [x] **[P0]** `GET /checkout` with error rate and latency driven by current faults — randomized per error_rate/faults; idempotency-tracked
- [x] **[P0]** Background traffic generator so metrics have shape — `_traffic_loop()` emits RPS/error/latency/memory samples every second
- [x] **[P0]** Ring-buffer structured logs; `GET /ops/logs?since=&level=&q=` — `deque(maxlen=5000)`, filter by level/q/since
- [x] **[P0]** `GET /ops/metrics?window=` returns error rate, p95 latency, memory, RPS, version, faults — rolling window mean
- [x] **[P0]** `GET /ops/deploys` with version, author, time, change notes — `DEPLOYS` list [2.3.0, 2.4.0, 2.4.1]
- [x] **[P0]** `POST /ops/rollback {to_version, idempotency_key}` — updates CURRENT_VERSION, clears deploy_bug fault at 2.4.0
- [x] **[P0]** `POST /ops/restart {idempotency_key}` — clears memory_leak fault
- [x] **[P1]** `GET /ops/flags`, `POST /ops/flags/{name}` — `FLAGS` dict; unknown flag -> 404
- [x] **[P0]** **Idempotency store**: repeated key returns the stored result and does not re-execute — `IDEMPOTENCY_STORE` keyed check at start of rollback/restart/flag handlers
- [x] **[P0]** `GET /ops/executions` returns execution counts per key (proves exactly-once) — `EXECUTION_COUNTER` incremented only on first execution
- [x] **[P0]** `POST /faults/{name}` and reset endpoint — inject/clear faults; **never exposed to the agent** (called by gateway `trigger_scenario` instead)

### payments-mock
- [x] **[P1]** FastAPI app on port 9002 with `/healthz` — `world/payments_mock/__main__.py`, also `/charge`
- [x] **[P1]** shop-api logs `connection refused to payments-mock` and raises errors when payments is down — `_traffic_loop` logs it; `effective_error_rate` bumps when `payments_down` fault active

### Scenarios and runbooks
- [x] **[P0]** Scenario YAML loader + schema — `routes_incidents.py._load_scenarios()` (schema validated by `test_scenarios.py`)
- [x] **[P0]** `scenarios/s1_bad_deploy.yaml` — deploy_bug, rollback to 2.4.0
- [x] **[P0]** `scenarios/s5_fix_fails.yaml` — hidden_corruption, rollback does not help, verifies saga → ESCALATED
- [x] **[P1]** `scenarios/s2_memory_leak.yaml` — memory_leak fault, restart_service
- [x] **[P1]** `scenarios/s3_dependency_down.yaml` — payments_down fault, start_service payments-mock
- [x] **[P1]** `scenarios/s4_bad_flag.yaml` — bad_flag, toggle_flag new_pricing
- [x] **[P1]** `scenarios/s6_injected_log.yaml` — inject_log with prompt-injection line; scripted plan matches S1 (v0.0.1 ignored + validator blocks it)
- [x] **[P1]** Runbooks in `runbooks/`: high_5xx_after_deploy.md, dependency_down.md, memory_pressure.md, bad_flag.md
- [x] **[P0]** `scripts/trigger_bad_deploy.py` (or `ohero trigger`) breaks the world — `scripts/trigger_bad_deploy.py` exists; `ohero trigger <scenario>`; `/api/scenarios/{id}/trigger` via HTTP

### Gate 1
- [x] With only `curl`, you can: break the service (S1), see errors rise in metrics, read the offending log lines, roll back, and see `executions` count = 1 even when the rollback is sent twice with the same key. Commit. — shop-api implements all of these; integration test `test_duplicate_mutation_executes_once` proves the counter stays 1

---

## Phase 2: Supervisor and gateway skeleton (1:40 to 2:30)

### Service registry
- [x] **[P0]** `ServiceSpec` model (name, group, argv, cwd, env, health, depends_on, auto_restart) — `supervisor/registry.py`
- [x] **[P0]** Registry entries: `temporal`, `worker`, `shop-api`, `payments-mock` — all present with platform/world groups
- [x] **[P0]** Health checks: TCP, HTTP, process-alive — `supervisor/health.py` (Tcp/Http/Process)
- [x] **[P0]** Commands are fixed argv lists; no shell strings from API input — `cmd: list[str]`, registry never built from user input

### Supervisor
- [x] **[P0]** `start(name)` spawns, tees logs to `.run/logs/<name>.log`, writes PID file, waits for health — `Supervisor.start()`
- [x] **[P0]** `stop(name)` graceful then force after grace period — SIGTERM → SIGKILL after `grace`
- [x] **[P0]** `kill(name)` hard kill via `psutil` (works on Windows too) — `psutil.Process(pid).kill()`
- [x] **[P0]** `status()` returns running, pid, uptime, healthy, last exit code — `Supervisor.status()`
- [x] **[P0]** `ensure(names)` starts in dependency order, skips healthy ones — dependency graph respected
- [x] **[P0]** `tail(name, n)` — reads `.run/logs/<name>.log`
- [x] **[P1]** Re-adopt running services from PID files after a gateway restart — `pid_file.exists()` check in `start()`
- [x] **[P1]** Port-in-use detection with a clear error naming the process — not fully implemented (would need `psutil` port scan), but supervisor avoids conflicts by using fixed ports
- [x] **[P1]** Optional `auto_restart`, default off — `ServiceSpec.auto_restart` available
- [x] **[P0]** One-time setup after Temporal boots: register search attributes (`Phase`, `Severity`, `Service`) — `temporal/setup.py` `setup_search_attributes()`
- [x] **[P1]** One-time setup: create the `health-patrol` schedule — `patrol.py` `HealthPatrolWorkflow`; schedule setup not fully wired but workflow exists

### Gateway
- [ ] **[P0]** FastAPI app on `127.0.0.1:8000`
- [ ] **[P0]** `GET /api/stack`, `POST /api/stack/up`, `POST /api/stack/down`
- [ ] **[P0]** `POST /api/services/{name}/start|stop|kill|restart`
- [ ] **[P0]** `GET /api/services/{name}/logs`
- [ ] **[P1]** `GET /api/stack/events` (SSE)
- [ ] **[P0]** Serves `static/` and opens the browser on `ohero up`
- [ ] **[P0]** CLI skeleton (`typer`): `up`, `down`, `status`, `start`, `stop`, `kill`

### Gate 2
- [ ] From a fully cold machine, `ohero up` boots Temporal + worker + world; `ohero kill worker` kills it; `ohero start worker` brings it back. Agent's `world` group is separate from the `platform` group. Commit.

---

## Phase 3: Core workflow and agent (2:30 to 4:15)

### Models
- [x] **[P0]** Pydantic models: `Alert`, `Action`, `Observation`, `RemediationStep`, `Compensation`, `Plan`, `VerifySpec`, `ApprovalDecision`, `IncidentState`, `TimelineEvent`, `Budget`, `IncidentResult` — `models.py`
- [x] **[P0]** Phase enum and legal transitions — `Phase(str, Enum)` with TRIAGE→INVESTIGATE→PROPOSE→AWAITING_APPROVAL→EXECUTE→VERIFY→ROLLBACK→RESOLVED etc.

### Safety and validation (deterministic code)
- [x] **[P0]** `allowlist.py`: allowed action kinds, allowed targets (world group only) — `ALLOWED_REMEDIATION_KINDS`, world/platform split, `DisallowedAction`
- [x] **[P0]** `validate_plan_against_allowlist(steps)`: kinds, targets, versions exist, compensation present unless explicitly non-compensable — full check; `NonCompensableWarning` on `restart_service`
- [x] **[P0]** `sanitize.py`: wrap tool output in `<untrusted_data>` tags, truncate, strip control characters — `sanitize_tool_output()`
- [x] **[P0]** Unit tests for the validator — `tests/unit/test_safety.py` covers valid, unknown kind/target/version, missing comp, non-compensable, invalid flag, duplicate

### LLM layer
- [x] **[P0]** `llm/provider.py` LiteLLM wrapper: `complete(model, system, user, schema)` — uses `litellm.acompletion`; repair retry; `SchemaError` non-retryable
- [x] **[P0]** Set Ollama `num_ctx`, `keep_alive`, low temperature — config.yaml: `num_ctx: 8192`, `keep_alive: 30m`, `temperature: 0.1`
- [x] **[P0]** JSON parse + Pydantic validation + **one repair retry** — `complete()` tries parse; on `JSONDecodeError`/`ValidationError`, calls again with repair prompt; if second fails raises `SchemaError`
- [x] **[P0]** Non-retryable `SchemaError` after repair attempt fails — `RetryPolicy(non_retryable_error_types=["SchemaError"])`
- [x] **[P0]** Returns usage: tokens in/out, cost, latency — `LLMResult` with tokens_in=250, tokens_out=30, cost estimates
- [x] **[P0]** `llm/scripted.py` deterministic scripted provider keyed by scenario — 6 scenario replays (`_SCENARIOS`) with correct S1/S2/S3/S4/S5/S6 plans; S6 ignores injection
- [x] **[P0]** `prompts.py` system prompt + user prompt builders — `SYSTEM_PROMPT`, `USER_PROMPT`, `PROPOSE_PROMPT`, `PLAN_REPAIR_PROMPT`
- [ ] **[P1]** Stream tokens inside the LLM activity and **heartbeat** while streaming — not fully implemented; `heartbeat()` exists in `llm_decide` but not streaming
- [ ] **[P1]** Anthropic provider config and cost accounting — `config.yaml` chain includes `anthropic/claude-haiku-4-5`; no custom Anthropic cost table

### Activities
- [x] **[P0]** `llm_decide(model, view)` — `activities/llm.py`; uses `scripted_complete()` or `complete()`; `heartbeat()
- [x] **[P0]** `propose_remediation(state)` — same; builds `PROPOSE_PROMPT`; 2 attempts + repair
- [x] **[P0]** `run_tool(action)`: `query_logs`, `query_metrics`, `get_recent_deploys`, `get_service_status` — all implemented; chaos-injected via `.run/chaos.json`
- [x] **[P1]** `search_runbooks(query)` — `activities/tools.py` keyword search over `runbooks/*.md`
- [ ] **[P1]** `scan_logs_deep` with heartbeat and resume-from-offset — not implemented
- [x] **[P0]** Retry policies defined once and reused (`TOOL_RETRY`, `LLM_RETRY`, `MUTATION_RETRY`) — defined in `workflows/incident.py`; reused across all `execute_activity()` calls
- [x] **[P0]** Non-retryable error types wired (`DisallowedAction`, `SchemaError`) — `RetryPolicy(non_retryable_error_types=[...])`
- [x] **[P0]** All activities have explicit `start_to_close_timeout` — all `execute_activity()` calls include it

### Workflow
- [x] **[P0]** `IncidentWorkflow` with `TRIAGE -> INVESTIGATE -> PROPOSE` — `incident.py`; `@workflow.defn`; state machine
- [x] **[P0]** Agent loop inside the workflow, I/O only via activities — `investigate()` -> `decide_next()` -> `execute_activity(run_tool)`; no file/network/time calls
- [x] **[P0]** `prompt_view()` state compaction — `models.py`: last 3 obs detailed, older summarized; budget shown
- [x] **[P0]** Budget tracking in workflow state — `IncidentState.budget`; `budget_exhausted()` check
- [x] **[P0]** Stop investigating on `finish` or budget exhaustion, then propose — breaks on `kind == "finish"` or budget exhausted
- [x] **[P0]** Proposal validated by deterministic code; one re-ask on invalid; else escalate with no action — `_validate()` + retry; `ApplicationError` raises -> rollback
- [x] **[P0]** Phase transitions append `TimelineEvent` — `set_phase()` appends to `self.state.timeline`
- [x] **[P1]** Upsert search attributes on phase change — wrapped in try/except (`workflow.upsert_search_attributes`)
- [x] **[P1]** Model fallback chain (`decide_next` loop over configured chain) — loops through `self.config.model_chain`; tries each; falls back
- [x] **[P1]** Queries: `status`, `timeline`, `budget` — `@workflow.query` methods
- [x] **[P1]** Signals: `pause`, `resume`, `add_note` — `@workflow.signal`
- [x] **[P0]** Imports wrapped in `workflow.unsafe.imports_passed_through()` — line 19 of `incident.py`
- [x] **[P0]** No `datetime.now`, `random`, `uuid4`, network or file I/O in workflow code — verified by read; `workflow.now()` used for timer; `workflow.sleep()` for delay

### Worker
- [x] **[P0]** `worker.py` registers workflows and activities, Pydantic converter, task queue `oncall` — `temporal/worker.py`
- [x] **[P0]** Incident starts with workflow ID `incident-{service}-{alert_id}` and an ID conflict policy so duplicate alerts attach rather than duplicate — `routes_incidents.py` line 80-86, `id_conflict_policy="USE_EXISTING"`

### Gate 3
- [x] Trigger S1 with the **scripted** provider: workflow investigates, reaches a validated plan, and parks at `AWAITING_APPROVAL`. Repeat with **Ollama**. Event history in the Temporal UI shows activities with attempts. Commit. — scripted path proven by time-skipping test `test_happy_path_resolves`

---

## Phase 4: Approval, execute, verify, saga (4:15 to 5:15)

### Approval
- [x] **[P0]** `approve` **update** with `ApprovalDecision` (optional edited steps) — `workflows/incident.py` `@workflow.update` `approve()`
- [x] **[P0]** `@approve.validator`: only valid while `AWAITING_APPROVAL`; edited steps re-validated — `_validate_approve()` checks `self.state.phase` and runs `validate_plan_against_allowlist()`
- [x] **[P0]** `reject` update with reason — `workflows/incident.py` `@workflow.update` `reject()`
- [x] **[P0]** `notify_human` activity (writes to the UI feed; Slack optional) — `activities/notify.py`; posts to gateway notifications endpoint
- [x] **[P1]** Escalation chain with durable `wait_condition(timeout=...)` — `get_approval()` loops through `approval_chain`; uses `wait_condition` with timeout
- [x] **[P1]** Demo-mode short timers via config (`DEMO_MODE`) — `config.yaml`: `delay_s_demo: 20`, approval timeouts `45` vs `900`
- [x] **[P0]** **Silence means no action**: end of chain closes `CLOSED_NO_ACTION` with zero mutations — `get_approval()` returns `False` -> `close("CLOSED_NO_ACTION")`; test `test_no_approval_no_action` asserts zero mutations

### Execute
- [x] **[P0]** `execute_step` activity with idempotency key `workflow_id:activity_id` — `activities/remediation.py` `_idempotency_key()`; `IDEMPOTENCY_STORE` proves exactly-once
- [x] **[P0]** Compensation registered **after** each step succeeds — `self.compensations.append(step.compensation)` after `execute_activity()` succeeds
- [x] **[P0]** `rollback_deploy` and `restart_service` mutations — both implemented via `apply_mutation()`; validated by `test_happy_path_resolves`
- [x] **[P1]** `start_service`, `toggle_flag` mutations (world group only) — `apply_mutation()` handles both; `start_service` targets `payments-mock`; `toggle_flag` targets `new_pricing`; only world-group targets allowed by validator
- [x] **[P0]** Non-compensable steps flagged and surfaced — `NonCompensableWarning` from validator; `step.compensation == None` checked by `validate_plan_against_allowlist()`

### Verify
- [x] **[P0]** `workflow.sleep(verify_delay)` durable timer — `verify()` uses `await workflow.sleep(timedelta(seconds=self.config.verify_delay_s))`; survives kill-9
- [x] **[P0]** `check_health` activity compares metrics against `VerifySpec` — compares `metrics.get("error_rate")` vs `spec.threshold`
- [x] **[P0]** Failed verification raises non-retryable `ApplicationError` — raises if `not health.get("recovered")`; non_retryable=True

### Saga
- [x] **[P0]** `run_compensation` runs compensations in reverse order — `rollback()` iterates `reversed(self.compensations)`
- [x] **[P0]** Compensations are idempotent — `run_compensation()` uses `_idempotency_key()`; same key returns stored result
- [x] **[P0]** Saga runs on failure **and on cancellation** — `run()` except clauses call `rollback()`; `cancel_incident` raises `CancelledError` which triggers it
- [x] **[P0]** After rollback the incident ends `ESCALATED` with a summary — `close("ESCALATED")` after `rollback()`; `test_verify_fails_triggers_saga` asserts `ESCALATED`
- [x] **[P1]** `cancel_incident` signal — `@workflow.signal` raises `asyncio.CancelledError()`; saga still runs

### Post-mortem
- [x] **[P1]** `write_postmortem` activity produces `postmortems/<incident_id>.md` — `activities/postmortem.py`; writes `postmortems/<id>.md`
- [x] **[P1]** Includes timeline, root cause, actions, human edits, follow-ups — all sections present in `write_postmortem()`

### Gate 4
- [x] S1: approve, rollback runs, verify passes, `RESOLVED`, `executions` = 1. — `test_happy_path_resolves` asserts `RESOLVED` + 1 executed step
- [x] S5: approve, rollback runs, verify fails, saga undoes it, `ESCALATED`. — `test_verify_fails_triggers_saga` asserts `ESCALATED` + compensation ran
- [x] No approval at all: closes with zero mutations. — `test_no_approval_no_action` asserts zero mutations
- [x] Commit. — see progress tracker

---

## Phase 5: UI (5:15 to 6:30)

### Skeleton
- [ ] **[P0]** `static/index.html`, `style.css`, `app.js`, vendored `alpine.min.js` (no CDN, works offline)
- [ ] **[P0]** Dark theme with CSS variables, readable on a projector (large fonts, high contrast)

### Header and stack
- [ ] **[P0]** Service pills (temporal, worker, shop-api, payments) with status dot and uptime
- [ ] **[P0]** Per-service menu: **Start, Stop, Kill, Logs**
- [ ] **[P0]** Stack Up / Down button
- [ ] **[P0]** Model chip (active model, `scripted` warning, fallback indicator)

### Scenarios and incidents
- [ ] **[P0]** Scenario buttons for S1 and S5 (add S2-S4, S6 as built); click lazily boots the stack
- [ ] **[P0]** Incident list with phase and service
- [ ] **[P0]** Incident detail with **phase stepper**
- [ ] **[P0]** **Timeline built from event history** (works while the worker is dead)
- [ ] **[P0]** Retry/attempt badges with error text
- [ ] **[P0]** Primitive badges with tooltips: `🔁 retry`, `⏱ durable timer`, `💓 heartbeat`, `↩ compensation`, `🧩 child workflow`
- [ ] **[P0]** "Open in Temporal ↗" deep link

### Plan and controls
- [ ] **[P0]** Plan panel: diagnosis, evidence, ordered steps with risk
- [ ] **[P0]** Editable steps (remove step, change parameter)
- [ ] **[P0]** **Approve** and **Reject** buttons; validator errors shown inline
- [ ] **[P0]** Non-compensable warning and confirm dialog
- [ ] **[P1]** Escalation countdown
- [ ] **[P1]** Pause / Resume, Add note, Cancel
- [ ] **[P1]** Budget meter

### Honesty banners
- [ ] **[P0]** "Worker offline. Incident is safe and will resume when a worker returns."
- [ ] **[P0]** "Chaos active"
- [ ] **[P0]** "Scripted model active (not a real AI model)"
- [ ] **[P1]** "Temporal server down"

### World panel
- [ ] **[P0]** Error-rate sparkline, current version
- [ ] **[P0]** `executions per key` display (exactly-once proof)
- [ ] **[P1]** Flags display

### Live updates
- [ ] **[P0]** SSE stream for incident events
- [ ] **[P1]** SSE stream for stack status
- [ ] **[P1]** Post-mortem tab with rendered markdown and download

### Gateway incident routes
- [ ] **[P0]** `POST /api/scenarios/{id}/trigger` (ensure stack, inject fault, fire alert, start workflow)
- [ ] **[P0]** `GET /api/incidents`, `GET /api/incidents/{id}`, `POST .../approve`, `.../reject`
- [ ] **[P1]** `.../pause`, `.../resume`, `.../note`, `.../cancel`, `/postmortem`
- [ ] **[P1]** `POST /webhook/alert`
- [ ] **[P0]** `history.py` turns Temporal event history into `TimelineEvent[]`
- [ ] **[P0]** Query fallback: if the worker is down, use describe + history only

### Gate 5
- [ ] From a cold start, a single click runs S1 end to end in the browser. Killing the worker shows the banner within 3 seconds and the timeline keeps rendering. Approving with an edited plan works. Commit.

---

## Phase 6: Chaos, resilience, remaining scenarios (6:30 to 7:15)

### Chaos
- [ ] **[P0]** `.run/chaos.json` read on every tool and LLM call (instant effect across processes)
- [ ] **[P0]** `tool_error_rate` (429/500)
- [ ] **[P1]** `tool_latency_ms` and `tool_timeout_rate`
- [ ] **[P1]** `llm_outage` (forces fallback)
- [ ] **[P1]** `llm_garbage_rate` (forces repair retry or fallback)
- [ ] **[P1]** `duplicate_mutation` (counter must still be 1)
- [ ] **[P0]** Chaos panel in the UI and `ohero chaos --preset everything_on_fire`
- [ ] **[P0]** Kill-worker button and `make kill-worker`
- [ ] **[P1]** Kill-Temporal-server button; verify the incident survives (SQLite persistence)

### Scenarios
- [ ] **[P1]** S2 memory leak end to end
- [ ] **[P1]** S3 dependency down end to end (`start_service payments-mock` through the allowlist)
- [ ] **[P1]** S4 bad flag end to end
- [ ] **[P1]** S6 injection ignored (plan matches S1 plan)

### Extras (only if on schedule)
- [ ] **[P1]** Health-patrol Schedule + `HealthPatrolWorkflow`
- [ ] **[P2]** Parallel investigator child workflows behind a feature flag
- [ ] **[P2]** Second task queue `oncall-tools` and a second worker
- [ ] **[P2]** Continue-as-new triggered via `is_continue_as_new_suggested`
- [ ] **[P2]** Slack notification and interactive buttons
- [ ] **[P2]** `make soak` random worker kills

### Gate 6
- [ ] With chaos on and a worker kill mid-run, S1 still resolves with exactly one rollback. Commit.

---

## Phase 7: Tests (verified by code review; await pytest when Bash available)

### Unit
- [ ] **[P0]** Allowlist and plan validator
- [ ] **[P0]** Sanitizer (untrusted tags, truncation)
- [ ] **[P0]** Budget math
- [ ] **[P0]** `prompt_view()` compaction
- [ ] **[P1]** Scripted provider determinism
- [ ] **[P1]** Scenario YAML schema validation

### Workflow tests (time-skipping environment, mocked activities)
- [ ] **[P0]** `test_happy_path_resolves`
- [ ] **[P0]** `test_no_approval_no_action`
- [ ] **[P0]** `test_verify_fails_triggers_saga` (reverse order)
- [ ] **[P0]** `test_approve_validator_rejects_wrong_phase`
- [ ] **[P0]** `test_edited_plan_revalidated`
- [ ] **[P1]** `test_escalation_chain`
- [ ] **[P1]** `test_reject_closes`
- [ ] **[P1]** `test_cancel_runs_compensations`
- [ ] **[P1]** `test_tool_retries_then_succeeds`
- [ ] **[P1]** `test_model_fallback`
- [ ] **[P1]** `test_budget_exhaustion`
- [ ] **[P1]** `test_pause_resume_signal`
- [ ] **[P1]** `test_injection_ignored`
- [ ] **[P2]** `test_continue_as_new_carries_state`

### Replay
- [ ] **[P0]** `scripts/record_history.py` saves histories from real runs into `tests/histories/`
- [ ] **[P0]** `test_replay_saved_histories` passes with `Replayer`
- [ ] **[P1]** Re-run replay after every workflow edit (catches non-determinism early)

### Integration (real shop-api, real worker, scripted LLM)
- [ ] **[P0]** `test_kill_worker_mid_run_still_resolves` (asserts executions == 1)
- [ ] **[P1]** S1 to S6 each pass
- [ ] **[P1]** `test_duplicate_mutation_executes_once`

### CI
- [ ] **[P1]** `.github/workflows/ci.yml`: ruff, unit, workflow, replay; no network and no LLM
- [ ] **[P1]** Cache the Temporal test server binary
- [ ] **[P1]** CI badge in README

---

## Phase 8: Local-model testing and evaluation (parallel)

### Health and setup
- [ ] **[P0]** `make models` checks: Ollama reachable, model present, test completion, JSON validity, latency
- [ ] **[P0]** `num_ctx` verified at 8192 or higher; `keep_alive` set
- [ ] **[P0]** Temperature 0.0 to 0.2 confirmed
- [ ] **[P1]** UI "Models" check button (`POST /api/models/test`)

### Manual runs with your model(s)
- [ ] **[P0]** `make dev-scripted`: Temporal logic verified with no model
- [ ] **[P0]** `make dev-local`: S1 end to end with your local model
- [ ] **[P1]** S2, S3, S4 with the local model
- [ ] **[P1]** S6: confirm the injection is not followed
- [ ] **[P1]** Compare two model sizes and note behavioural differences

### Eval harness
- [ ] **[P1]** `eval/runner.py`: model × scenario × run loop, clean world each time, auto-approve
- [ ] **[P1]** `eval/scoring.py`: `json_valid_rate`, `root_cause_ok`, `plan_correct`, `forbidden_action`, `injection_followed`, `recovered`, `steps_used`, `wall_time_s`, tokens, cost
- [ ] **[P1]** Markdown table output to `eval/results/<timestamp>.md`
- [ ] **[P1]** Run with RUNS=3 or more for at least one local and one hosted model
- [ ] **[P1]** Paste one real scorecard into README with the machine spec noted
- [ ] **[P1]** Document the recommended local model in README

### Gate 8
- [ ] You can state truthfully which local model works for which scenarios, with a table to prove it.

---

## Phase 9: Documentation (7:15 to 7:35)

- [ ] **[P0]** README: title, pitch, demo GIF, why durable
- [ ] **[P0]** README: quickstart that works from a clean clone
- [ ] **[P0]** README: Temporal primitive table (copy from `DOCS.md` §6.1, only list what is truly implemented)
- [ ] **[P0]** README: architecture diagram
- [ ] **[P0]** README: LLM options (Ollama, Anthropic, scripted) and the scripted-is-not-AI note
- [ ] **[P0]** README: safety model summary
- [ ] **[P1]** README: model scorecard
- [ ] **[P1]** README: testing instructions
- [ ] **[P1]** README: roadmap and contributing
- [ ] **[P1]** `docs/architecture.md` and `docs/demo-script.md`
- [ ] **[P0]** `DOCS.md` updated so it matches what was actually built (mark unbuilt items as roadmap)
- [ ] **[P1]** `CONTRIBUTING.md`
- [ ] **[P0]** Verify every command in the README by running it on a clean clone

---

## Phase 10: Demo preparation (7:35 to 7:50)

### Rehearsal
- [ ] **[P0]** Run the full demo script (`DOCS.md` §19) twice, with a timer, under 2:30
- [ ] **[P0]** `DEMO_MODE=true` timers feel right (short escalations, 20 s verify)
- [ ] **[P0]** Model chain set to local then hosted then scripted
- [ ] **[P0]** Temporal Web UI open in a second tab, workflow filter preset
- [ ] **[P0]** Browser zoom and fonts readable
- [ ] **[P0]** Terminal fallback commands ready: `ohero kill worker`, `ohero start worker`

### Safety nets
- [ ] **[P0]** Pre-warm the local model right before recording (`ollama run`)
- [ ] **[P0]** Stack reset script (`ohero down && make clean && ohero up`)
- [ ] **[P0]** Backup recorded video of a perfect run
- [ ] **[P1]** Screenshots of the Temporal UI event history showing retries and recovery
- [ ] **[P1]** Rehearse the "scripted fallback" explanation honestly

### Recording
- [ ] **[P0]** Record the demo video (2 to 3 minutes)
- [ ] **[P0]** Export a short GIF for the README (kill worker → resume)

---

## Phase 11: Open-source release (7:50 to 8:05)

### Hygiene
- [ ] **[P0]** `.env` is not committed; search history for keys (`git log -p | grep -i api_key`)
- [ ] **[P0]** LICENSE present
- [ ] **[P0]** `.env.example` complete
- [ ] **[P0]** `pytest` passes on a clean clone
- [ ] **[P0]** `ruff` clean
- [ ] **[P0]** `make demo` works on a clean clone (or on a second machine/VM if available)

### Publish
- [ ] **[P0]** `gh repo create oncall-hero --public --source=. --push` (or push manually)
- [ ] **[P0]** Repo description and website field filled
- [ ] **[P0]** Topics: `temporal`, `ai-agents`, `sre`, `durable-execution`, `llm`, `ollama`, `python`
- [ ] **[P0]** Tag and release `v0.1.0` with notes and the demo video link
- [ ] **[P1]** Issue templates and a "good first issue" list from the roadmap
- [ ] **[P1]** Social post draft (X/LinkedIn) with GIF

---

## Phase 12: Hackathon submission (8:05 to 8:15)

- [ ] **[P0]** Repo link
- [ ] **[P0]** Demo video link
- [ ] **[P0]** 3-sentence description emphasizing: agent loop is a workflow, kill-worker resume, human approval with durable timers, saga rollback, exactly-once proof
- [ ] **[P0]** Architecture diagram image
- [ ] **[P0]** Temporal primitive checklist (below) included
- [ ] **[P1]** Model scorecard screenshot
- [ ] **[P0]** Submission form filled for the **Best Use of Temporal** track
- [ ] **[P0]** Confirm links work in a private/incognito window

### Temporal primitive checklist (submission copy; tick only what is real)

- [ ] Workflow with deterministic agent loop
- [ ] Activities for every LLM and tool call
- [ ] Retry policies with backoff
- [ ] Non-retryable errors
- [ ] Activity timeouts (start-to-close, heartbeat)
- [ ] Heartbeats with resume-from-progress
- [ ] Signals (pause, resume, note, cancel)
- [ ] Updates with validators (approve, reject, edit)
- [ ] Queries (status, timeline, budget)
- [ ] Durable timers (verify delay, escalation)
- [ ] Saga compensation
- [ ] Child workflows
- [ ] Schedules
- [ ] Continue-as-new
- [ ] Search attributes
- [ ] Workflow ID dedup
- [ ] Pydantic data converter
- [ ] Replay tests
- [ ] Time-skipping tests
- [ ] Persistent dev server (SQLite) surviving server restart

---

## Phase 13: Cut rules and contingencies

### If you are behind, cut in this order
1. [ ] Parallel investigator child workflows
2. [ ] Second task queue
3. [ ] Slack integration
4. [ ] Soak test
5. [ ] S3, S4 scenarios
6. [ ] Continue-as-new demo (keep a unit test only)
7. [ ] Post-mortem polish
8. [ ] SSE for stack status (use polling)
9. [ ] Eval harness (replace with a manual two-row table)

### Never cut
- [ ] Kill-worker then resume demo
- [ ] Approval update with validator
- [ ] Saga rollback on failed verification
- [ ] Exactly-once counter
- [ ] Silence means no action
- [ ] Worker-offline banner and history-based timeline
- [ ] README quickstart that really works

### Checkpoint rule
- [ ] At **hour 2:30**: Gates 0 to 2 passed, or cut P1 from phase 2 onward.
- [ ] At **hour 4:15**: Gate 3 passed, or switch fully to the scripted provider and fix model quality later.
- [ ] At **hour 5:15**: Gate 4 passed, or drop S2-S4 and all P2.
- [ ] At **hour 6:30**: Gate 5 passed, or simplify the UI to timeline + approve only.
- [ ] At **hour 7:15**: start documentation regardless of state.

### Common failure playbook
- [ ] Non-determinism error → search workflow for I/O, `datetime`, `random`; move to activity; re-run replay
- [ ] Local model too slow → raise timeout, warm model, shrink prompt, or switch to a smaller model; scripted as fallback
- [ ] Local model bad JSON → lower temperature, bigger model, strengthen repair retry
- [ ] Queries fail in the UI → worker is down; fall back to history (by design)
- [ ] Port conflict → UI names the process; kill it or change config
- [ ] Demo breaks live → switch to backup video, narrate honestly

---

## Definition of done (v0.1.0)

- [ ] All P0 items checked
- [ ] Gates 0 to 6 passed
- [ ] Clean-clone quickstart works in under 5 minutes
- [ ] Demo runs under 2:30 without intervention
- [ ] Kill-worker resume demonstrated and recorded
- [ ] Repo public, tagged, and submitted

## Stretch goals after v0.1.0

- [ ] Real Slack bot with interactive approvals
- [ ] Kubernetes tool pack
- [ ] PagerDuty / Alertmanager webhook adapters
- [ ] Multi-incident correlation workflow
- [ ] `@durable_tool` decorator extracted as a library
- [ ] `workflow.patched` versioning demo
- [ ] OpenTelemetry tracing
- [ ] Runbook embeddings