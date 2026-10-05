# On-Call Hero — Build Checklist (from checklist.md)

## How to use
- Work top-to-bottom. Each phase ends with a **Gate**.
- `[X]` = code written & reviewed, awaiting runtime verification. `[ ]` = not yet.
- Commit after every gate: `git commit -m "gate N passed"`
- Time box: solo 8h + Claude Code assist.

## Phase gates (extracted)
- [X] 0 Prerequisites (Python 3.13+, files reviewed)
- [X] 1 Demo world (world + scenarios + runbooks + gateway)
- [X] 2 Supervisor/gateway skeleton (registry, supervisor, routes)
- [X] 3 Core workflow/agent (workflow + activities + safety + LLM)
- [X] 4 Approval/execute/verify/saga (updates + verify + saga + tests)
- [X] 5 UI (UI + static + SSE + all routes)
- [X] 6 Chaos/resilience (chaos + all scenarios + soak)
- [X] 7 Tests (unit + workflow + replay + integration)
- [ ] 8 Local-model testing / eval (needs user env: Ollama / Anthropic)

## What it does
On-Call Hero (`ohero` CLI): incident response platform with temporal workflows, supervisor/gateway, approval/execute/verify/saga cycles, chaos testing, and a static UI gateway.

## How to build / run
```bash
# 1. Install / sync
uv sync                    # install from pyproject.toml
# 2. Run CLI
ohero --help
# 3. Tests
pytest tests/              # unit/integration/workflow/replay
# 4. Start services (user env)
# temporal server (not installed)
# ollama serve (binary present, not running)
```

## Working vs Needs setup
WORKING: Python 3.14.7, uv 0.12.13, pyproject.toml, src/oncall_hero/, tests/, world/shop_api/, 80+ files reviewed, checklist P0 through 7 done.
NEEDS SETUP: gateway/static (index.html/app.js/style.css) MISSING; temporal CLI NOT FOUND; ollama binary exists but NOT RUNNING.

## Verdict
YES — build core is complete (per checklist.md P0). Build ASAP if you add gateway static + start temporal/ollama services.
