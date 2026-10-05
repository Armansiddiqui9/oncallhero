"""Contributing guidelines."""

# On-Call Hero

Contributions are welcome! This is a hackathon project built to demonstrate
durable execution with Temporal.

## Development setup

```bash
git clone https://github.com/<you>/oncall-hero && cd oncall-hero
uv sync                 # or: pip install -e ".[dev]"
make install            # installs dependencies
make up                 # starts the full stack
```

## Project structure

- `src/oncall_hero/` — the agent (workflows, activities, gateway, supervisor)
- `world/` — the demo world (shop-api, payments-mock)
- `scenarios/` — incident scenarios (YAML)
- `runbooks/` — plain-text runbooks the agent can search
- `tests/` — unit, workflow (time-skipping), replay, integration

## The golden rule

**Workflow code is deterministic orchestration only.** State, decisions on state,
timers, waits, branching. Everything with side effects or non-determinism
(LLM calls, HTTP, file reads, randomness, time) lives in **activities**.

Never call `datetime.now()`, `random`, `uuid4`, network, or file I/O in
workflow code. Use `workflow.now()`, `workflow.random()`, `workflow.uuid4()`.

## Testing

```bash
make test        # unit + workflow + replay (no LLM, no network)
make test-int    # integration (needs a running stack)
```

## Adding a scenario

1. Add `scenarios/sN_name.yaml` (see `scenarios/s1_bad_deploy.yaml` for shape).
2. Add the fault handling to `world/shop_api/__main__.py` if it needs a new fault type.
3. Add a scripted replay to `src/oncall_hero/llm/scripted.py` so CI can run it with no model.
4. Add a runbook to `runbooks/` if the diagnosis path is new.

## Code style

- Ruff for linting and formatting (`make lint`).
- Type hints everywhere; mypy optional but encouraged.
- Keep the workflow file pure: no I/O, no time, no randomness.

## License

Apache-2.0 or MIT (see LICENSE).
