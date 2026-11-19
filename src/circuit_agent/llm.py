"""Provider-neutral structured generation support.

No network provider is enabled by default. Hosts register one explicitly after
credentials and output-schema handling have been configured.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Protocol

from .domain import SchemaValidationError

class LLMProvider(Protocol):
    async def generate(self, *, system_prompt: str, user_payload: dict, response_schema: dict, model: str | None = None, timeout_s: float = 60) -> dict: ...

@dataclass(frozen=True)
class GenerationResult:
    content: dict
    provider: str
    model: str | None
    latency_ms: int
    retries: int

class ProviderRegistry:
    def __init__(self) -> None: self._providers: dict[str, LLMProvider] = {}
    def register(self, name: str, provider: LLMProvider) -> None:
        if not name or name in self._providers: raise ValueError(f"provider name is invalid or already registered: {name!r}")
        self._providers[name] = provider
    async def generate(self, provider_name: str, *, system_prompt: str, user_payload: dict, response_schema: dict, model: str | None = None, timeout_s: float = 60, max_retries: int = 1) -> GenerationResult:
        provider = self._providers.get(provider_name)
        if provider is None: raise KeyError(f"provider not registered: {provider_name}")
        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            started = time.monotonic()
            try:
                content = await asyncio.wait_for(provider.generate(system_prompt=system_prompt, user_payload=user_payload, response_schema=response_schema, model=model, timeout_s=timeout_s), timeout=timeout_s)
                _validate_required_fields(content, response_schema)
                return GenerationResult(content, provider_name, model, int((time.monotonic()-started)*1000), attempt)
            except (TimeoutError, SchemaValidationError) as exc: last_error = exc
        raise RuntimeError(f"provider generation failed after {max_retries + 1} attempt(s): {last_error}")

class MockProvider:
    """Test provider returning a registered fixture for a named response schema."""
    def __init__(self, fixtures: dict[str, dict]): self.fixtures = fixtures
    async def generate(self, *, system_prompt: str, user_payload: dict, response_schema: dict, model: str | None = None, timeout_s: float = 60) -> dict:
        key = response_schema.get("title", "default")
        if key not in self.fixtures: raise SchemaValidationError(f"mock fixture unavailable for {key}")
        return dict(self.fixtures[key])

def _validate_required_fields(content: dict, schema: dict) -> None:
    if not isinstance(content, dict): raise SchemaValidationError("provider output must be an object")
    missing = set(schema.get("required", [])) - set(content)
    if missing: raise SchemaValidationError(f"provider output missing required fields: {sorted(missing)}")
