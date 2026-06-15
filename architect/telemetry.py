"""Structured telemetry hooks for architect workflow execution."""

from __future__ import annotations

from collections.abc import MutableSequence
from time import perf_counter
from typing import Any

from architect.models import AgentStepTrace


class InMemoryTelemetryRecorder:
    """Simple test-friendly telemetry recorder.

    Production deployments can replace this with OpenTelemetry or another
    exporter without changing agent and DAG code.
    """

    def __init__(self, sink: MutableSequence[AgentStepTrace] | None = None) -> None:
        self.events: MutableSequence[AgentStepTrace] = sink if sink is not None else []

    def record(self, event: AgentStepTrace) -> None:
        self.events.append(event)

    def span(self, step: str, agent: str | None = None) -> "TelemetrySpan":
        return TelemetrySpan(self, step, agent)


class TelemetrySpan:
    """Context manager that records latency and state deltas."""

    def __init__(
        self,
        recorder: InMemoryTelemetryRecorder,
        step: str,
        agent: str | None,
    ) -> None:
        self.recorder = recorder
        self.event = AgentStepTrace(step=step, agent=agent)
        self._started = 0.0

    def __enter__(self) -> "TelemetrySpan":
        self._started = perf_counter()
        return self

    def set_delta(self, **delta: Any) -> None:
        self.event.state_delta.update(delta)

    def set_tokens(self, prompt_tokens: int, response_tokens: int) -> None:
        self.event.prompt_tokens = prompt_tokens
        self.event.response_tokens = response_tokens

    def set_reasoning(self, reasoning_trace: str | None) -> None:
        self.event.reasoning_trace = reasoning_trace

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.event.latency_ms = (perf_counter() - self._started) * 1000
        if exc is not None:
            self.event.state_delta["error"] = str(exc)
        self.recorder.record(self.event)
