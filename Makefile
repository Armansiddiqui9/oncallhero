.PHONY: help install up down dev-scripted dev-local demo models test test-int test-workflow soak eval lint clean kill-worker

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (uv sync or pip install -e .[dev])
	@if command -v uv >/dev/null 2>&1; then uv sync; else pip install -e ".[dev]"; fi

up: ## Start the gateway and full stack (ohero up)
	python -m oncall_hero.cli up

down: ## Stop everything (ohero down)
	python -m oncall_hero.cli down

dev-scripted: ## Stack with scripted model (no LLM needed)
	LLM_PROVIDER=scripted python -m oncall_hero.cli up --open-browser

dev-local: ## Stack with Ollama
	LLM_PROVIDER=ollama python -m oncall_hero.cli up --open-browser

demo: ## Stack with model chain + demo timers
	LLM_PROVIDER=chain DEMO_MODE=true python -m oncall_hero.cli up --open-browser

models: ## Check LLM providers (ollama reachability, model presence, JSON validity, latency)
	python -m oncall_hero.cli models

test: ## Unit + workflow + replay tests (no LLM, no network)
	python -m pytest tests/unit tests/workflow tests/replay -q

test-int: ## Integration tests (needs a running stack; scripted LLM)
	python -m pytest tests/integration -q

soak: ## Random worker kills during runs (durability soak)
	python scripts/soak.py

eval: ## Model scorecard (make eval MODELS="..." RUNS=5)
	python -m oncall_hero.eval.runner $(MODELS) --runs $(RUNS)

lint: ## Ruff lint + format check
	python -m ruff check .
	python -m ruff format --check .

kill-worker: ## Hard-kill the worker process
	python -m oncall_hero.cli kill worker

clean: ## Remove .run/ generated state
	rm -rf .run postmortems eval/results
