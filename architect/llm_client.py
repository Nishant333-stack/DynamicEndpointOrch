"""JSON-only LLM gateway with telemetry and circuit breaker protection."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any

from architect.telemetry import InMemoryTelemetryRecorder

LLMTransport = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class CircuitState(StrEnum):
    """Circuit breaker state."""

    CLOSED = "closed"
    OPEN = "open"


class CircuitBreakerOpen(RuntimeError):
    """Raised when an LLM call is attempted while the circuit is open."""


class CircuitBreaker:
    """Small async-safe circuit breaker for downstream LLM calls."""

    def __init__(self, failure_threshold: int = 3) -> None:
        self.failure_threshold = failure_threshold
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def before_call(self) -> None:
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerOpen("LLM circuit breaker is open.")

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN


class JSONOnlyLLMClient:
    """Encapsulates all LLM interactions behind one mockable interface."""

    def __init__(
        self,
        transport: LLMTransport | None = None,
        telemetry: InMemoryTelemetryRecorder | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        timeout_seconds: float = 20,
    ) -> None:
        self.transport = transport
        self.telemetry = telemetry or InMemoryTelemetryRecorder()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.timeout_seconds = timeout_seconds

    async def complete_json(
        self,
        *,
        agent_name: str,
        prompt: str,
        schema_hint: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a JSON dictionary from the configured LLM transport.

        Tests pass a deterministic transport. If no transport is configured,
        the method fails cleanly and increments the circuit breaker rather than
        making a live network call.
        """

        self.circuit_breaker.before_call()
        if self.transport is None:
            self.circuit_breaker.record_failure()
            raise RuntimeError("No LLM transport configured.")

        with self.telemetry.span("llm_call", agent_name) as span:
            try:
                result = await asyncio.wait_for(
                    self.transport(
                        prompt,
                        {"schema_hint": schema_hint, "agent_name": agent_name},
                    ),
                    timeout=self.timeout_seconds,
                )
            except Exception:
                self.circuit_breaker.record_failure()
                raise

            self.circuit_breaker.record_success()
            span.set_tokens(
                prompt_tokens=len(prompt.split()),
                response_tokens=len(str(result).split()),
            )
            return result
