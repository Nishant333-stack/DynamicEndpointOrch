"""Delay stage for MockMesh DEO.

``DELAY_STRATEGY_REGISTRY`` maps configured delay modes to async functions.
The built-in strategies are ``fixed`` and ``random``.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

from deo.models import EndpointDelay

DelayStrategy = Callable[[int], Awaitable[None]]


async def _fixed_delay(delay_ms: int) -> None:
    await asyncio.sleep(delay_ms / 1000)


async def _random_delay(delay_ms: int) -> None:
    await asyncio.sleep(random.uniform(0, delay_ms) / 1000)


DELAY_STRATEGY_REGISTRY: dict[str, DelayStrategy] = {
    "fixed": _fixed_delay,
    "random": _random_delay,
}
"""Registry of async delay strategies keyed by endpoint delay mode."""


class DelayEngine:
    """Apply configured endpoint latency before rendering the final response."""

    def __init__(self, delay_strategy_registry: dict[str, DelayStrategy] | None = None) -> None:
        self.delay_strategy_registry = delay_strategy_registry or DELAY_STRATEGY_REGISTRY

    async def apply(self, delay: EndpointDelay | None) -> None:
        """Sleep according to the endpoint delay configuration, if present."""

        if delay is None or delay.delay_ms <= 0:
            return

        strategy = self.delay_strategy_registry.get(delay.mode.lower())
        if strategy is None:
            raise ValueError(f"Unsupported delay mode: {delay.mode}")

        await strategy(delay.delay_ms)
