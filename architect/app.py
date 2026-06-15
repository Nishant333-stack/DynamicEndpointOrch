"""Standalone FastAPI app factory for serving DEO plus Architect routes."""

from __future__ import annotations

from fastapi import FastAPI

from architect.orchestrator import ArchitectOrchestrator
from architect.router import build_architect_router
from deo.repository import EndpointRepository, InMemoryEndpointRepository
from deo.router import build_deo_router


def create_app(repository: EndpointRepository | None = None) -> FastAPI:
    """Create an app exposing both DEO mock routes and architect routes."""

    endpoint_repository = repository or InMemoryEndpointRepository()
    app = FastAPI(title="MockMesh AI Endpoint Architect")
    app.include_router(build_deo_router(endpoint_repository))
    app.include_router(
        build_architect_router(ArchitectOrchestrator(endpoint_repository))
    )
    return app
