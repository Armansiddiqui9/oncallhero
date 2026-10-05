"""LLM provider: LiteLLM wrapper with JSON schema validation.

Wraps LiteLLM for Ollama/Anthropic/OpenAI-compatible servers.
The scripted provider (scripted.py) is the zero-model fallback.
"""

from __future__ import annotations

import json
import logging
import time

import litellm
from litellm import acompletion
from pydantic import BaseModel, ValidationError

from oncall_hero.llm import ProviderError, SchemaError
from oncall_hero.models import Budget
from oncall_hero.safety.sanitize import MAX_DETAIL_LENGTH

log = logging.getLogger("llm")

# Flat cost estimate so budgets work with or without a real provider.
ESTIMATE_COST_PER_K_TOKEN = 0.0001


class LLMResult(BaseModel):
    raw: str
    parsed: BaseModel
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_s: float


async def _call(model: str, system: str, user: str, temperature: float) -> str:
    """One provider call; raises ProviderError on transport failure."""
    resp = await acompletion(
        model=model,
        messages=[
            {"role": "system", "content": system[:4000]},
            {"role": "user", "content": user[:MAX_DETAIL_LENGTH]},
        ],
        temperature=temperature,
        timeout=180.0,
    )
    return resp["choices"][0]["message"]["content"]


def _parse(raw: str, schema: type[BaseModel]) -> BaseModel:
    obj = json.loads(raw)
    return schema(**obj)


async def complete(
    model: str,
    system: str,
    user: str,
    schema: type[BaseModel],
    budget: Budget,
    temperature: float = 0.1,
) -> LLMResult:
    """Call the LLM and validate output against a Pydantic schema.

    Flow:
      1. Call provider
      2. Parse + validate JSON; if it fails, one repair retry
      3. Update budget (tokens, cost, call count)
      4. Return usage so the workflow can enforce limits
    """
    # Pre-call guard for tokens/cost (root cause fix, not just log).
    if budget.tokens_used >= budget.max_tokens:
        raise ValueError("max tokens exceeded")
    if budget.cost_usd >= budget.max_cost_usd:
        raise ValueError("max cost exceeded")

    if budget.llm_calls >= budget.max_llm_calls:
        raise ValueError("max LLM calls exceeded")

    start = time.perf_counter()

    # Initial call (ProviderError propagates -> retry policy -> model fallback)
    raw = await _call(model, system, user, temperature)

    # Parse and validate; one repair retry with the error message.
    try:
        parsed = _parse(raw, schema)
    except (json.JSONDecodeError, ValidationError) as exc:
        log.warning("LLM output invalid, repairing: %s", exc)
        repair_prompt = (
            f"Your JSON did not match the schema. Error: {exc}. "
            f"Return ONE JSON object that matches the schema. Fix only what is invalid."
        )
        raw = await _call(model, system, user + "\n\n" + repair_prompt, temperature)
        budget.llm_calls += 1
        try:
            parsed = _parse(raw, schema)
        except (json.JSONDecodeError, ValidationError) as exc2:
            log.error("LLM output invalid after repair: %s", exc2)
            raise SchemaError(str(exc2)) from exc2

    elapsed = time.perf_counter() - start

    # Usage from provider response when available; else estimate.
    usage = resp.get("usage") if isinstance(resp, dict) else None
    if usage and isinstance(usage, dict):
        tokens_in = usage.get("prompt_tokens", 250)
        tokens_out = usage.get("completion_tokens", 30)
    else:
        tokens_in = 250
        tokens_out = 30
    cost = (tokens_in + tokens_out) * ESTIMATE_COST_PER_K_TOKEN / 1000.0

    budget.llm_calls += 1
    budget.tokens_used += tokens_in + tokens_out
    budget.cost_usd += cost

    if budget.tokens_used > budget.max_tokens:
        log.warning("LLM tokens over budget: %d > %d", budget.tokens_used, budget.max_tokens)
    if budget.cost_usd > budget.max_cost_usd:
        log.warning("LLM cost over budget: $%.4f > $%.2f", budget.cost_usd, budget.max_cost_usd)

    return LLMResult(
        raw=raw,
        parsed=parsed,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        latency_s=round(elapsed, 2),
    )
