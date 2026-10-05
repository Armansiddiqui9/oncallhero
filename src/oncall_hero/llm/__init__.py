"""LLM package for On-Call Hero.

Shared exceptions used across the LLM layer:

  - SchemaError   - LLM output failed schema validation (after repair retry).
                    Non-retryable: the workflow falls back to the next model.
  - ProviderError - provider/transport failure (the call could not be made).
                    Retried by the LLM retry policy.
"""

from __future__ import annotations


class SchemaError(RuntimeError):
    """LLM output failed schema validation (after repair retry). Non-retryable."""


class ProviderError(RuntimeError):
    """Provider/transport-level failure: the LLM call could not be made."""

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider
