"""Phase 0 discovery map for DEO source-of-truth primitives.

This module intentionally references existing ``deo`` contracts instead of
copying or redefining them. It gives the architect package a stable place to
report what it discovered about the current DEO integration surface.
"""

from __future__ import annotations

from typing import Any

from deo.delay_engine import DELAY_STRATEGY_REGISTRY
from deo.models import (
    Endpoint,
    EndpointDelay,
    EndpointRule,
    IncomingRequestContext,
    ResponseDefinition,
    ResponseHeader,
)
from deo.orchestrator import DEOOrchestrator
from deo.repository import EndpointRepository
from deo.rule_engine import OPERATOR_REGISTRY


def discovery_report() -> dict[str, Any]:
    """Return a structured summary of current DEO source-of-truth contracts."""

    return {
        "models": {
            "Endpoint": list(Endpoint.model_fields),
            "ResponseDefinition": list(ResponseDefinition.model_fields),
            "ResponseHeader": list(ResponseHeader.model_fields),
            "EndpointRule": list(EndpointRule.model_fields),
            "EndpointDelay": list(EndpointDelay.model_fields),
            "IncomingRequestContext": list(IncomingRequestContext.model_fields),
        },
        "repository_methods": [
            name
            for name in EndpointRepository.__dict__
            if not name.startswith("_")
        ],
        "orchestrator": {
            "class": DEOOrchestrator.__name__,
            "resolve_contract": "resolve(project_id, request_ctx) -> tuple[FinalResponse, RequestLogEntry]",
        },
        "registries": {
            "operators": sorted(OPERATOR_REGISTRY),
            "delay_modes": sorted(DELAY_STRATEGY_REGISTRY),
        },
    }
