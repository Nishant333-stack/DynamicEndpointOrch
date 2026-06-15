"""FastAPI router for the MockMesh DEO catch-all endpoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from deo.models import (
    EndpointCheckRequest,
    EndpointCheckResult,
    EndpointCreateRequest,
    IncomingRequestContext,
    LoginRequest,
    LoginResult,
    RuleCreateRequest,
)
from deo.orchestrator import DEOOrchestrator
from deo.repository import EndpointRepository, InMemoryEndpointRepository
from deo.route_matcher import RouteMatcher

STATIC_DIR = Path(__file__).with_name("static")
repository: EndpointRepository = InMemoryEndpointRepository()
orchestrator = DEOOrchestrator(repository)


async def build_request_context(request: Request, full_path: str) -> IncomingRequestContext:
    """Build an ``IncomingRequestContext`` from a FastAPI request."""

    body: Any = None
    raw_body = await request.body()
    if raw_body:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body = await request.json()
            except ValueError:
                body = raw_body.decode("utf-8", errors="replace")
        else:
            body = raw_body.decode("utf-8", errors="replace")

    return IncomingRequestContext(
        method=request.method,
        raw_path=f"/{full_path.strip('/')}" if full_path else "/",
        query_params=dict(request.query_params),
        headers={key.lower(): value for key, value in request.headers.items()},
        body=body,
    )


def _read_static_asset(filename: str) -> str:
    path = STATIC_DIR / filename
    if path.parent != STATIC_DIR or not path.exists():
        raise HTTPException(status_code=404, detail="asset not found")
    return path.read_text(encoding="utf-8")


def build_deo_router(endpoint_repository: EndpointRepository) -> APIRouter:
    """Build routes for the DEO mock API and dashboard control plane."""

    api_router = APIRouter()
    endpoint_orchestrator = DEOOrchestrator(endpoint_repository)
    route_matcher = RouteMatcher()

    @api_router.get("/", include_in_schema=False)
    async def index() -> HTMLResponse:
        return HTMLResponse(
            '<meta http-equiv="refresh" content="0; url=/dashboard">',
            headers={"Cache-Control": "no-store"},
        )

    @api_router.get("/dashboard", include_in_schema=False)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(
            _read_static_asset("dashboard.html"),
            headers={"Cache-Control": "no-store"},
        )

    @api_router.get("/dashboard/assets/{asset_name}", include_in_schema=False)
    async def dashboard_asset(asset_name: str) -> Response:
        media_types = {
            "dashboard.css": "text/css",
            "dashboard.js": "application/javascript",
        }
        if asset_name not in media_types:
            raise HTTPException(status_code=404, detail="asset not found")
        return Response(
            _read_static_asset(asset_name),
            media_type=media_types[asset_name],
            headers={"Cache-Control": "no-store"},
        )

    @api_router.get("/{asset_name}", include_in_schema=False)
    async def dashboard_relative_asset(asset_name: str) -> Response:
        media_types = {
            "dashboard.css": "text/css",
            "dashboard.js": "application/javascript",
        }
        if asset_name not in media_types:
            raise HTTPException(status_code=404, detail="asset not found")
        return Response(
            _read_static_asset(asset_name),
            media_type=media_types[asset_name],
            headers={"Cache-Control": "no-store"},
        )

    @api_router.get("/api/projects")
    async def list_projects() -> dict[str, Any]:
        projects = await endpoint_repository.get_project_overviews()
        return {"projects": [project.model_dump() for project in projects]}

    @api_router.post("/api/auth/login")
    async def login(login_request: LoginRequest) -> LoginResult:
        projects = await endpoint_repository.get_project_overviews()
        if not projects:
            raise HTTPException(status_code=503, detail="No projects are configured.")
        project_ids = {project.id for project in projects}
        default_project_id = (
            login_request.project_id
            if login_request.project_id in project_ids
            else projects[0].id
        )
        display_name = login_request.email.split("@", 1)[0].replace(".", " ").title()
        return LoginResult(
            user_id=login_request.email,
            display_name=display_name,
            token="dev-admin",
            projects=projects,
            default_project_id=default_project_id,
        )

    @api_router.get("/api/projects/{project_id}/endpoints")
    async def list_endpoints(project_id: str) -> dict[str, Any]:
        overviews = await endpoint_repository.get_endpoint_overviews(project_id)
        return {"endpoints": [overview.model_dump() for overview in overviews]}

    @api_router.post("/api/projects/{project_id}/endpoints", status_code=201)
    async def create_endpoint(
        project_id: str,
        create_request: EndpointCreateRequest,
    ) -> dict[str, Any]:
        exists = await endpoint_repository.endpoint_signature_exists(
            project_id,
            create_request.method,
            create_request.path,
        )
        if exists:
            raise HTTPException(
                status_code=409,
                detail="An endpoint with this method and path already exists.",
            )

        result = await endpoint_repository.create_endpoint(project_id, create_request)
        return result.model_dump()

    @api_router.post("/api/projects/{project_id}/endpoints/check")
    async def check_endpoint(
        project_id: str,
        check_request: EndpointCheckRequest,
    ) -> EndpointCheckResult:
        endpoints = await endpoint_repository.get_active_endpoints(project_id)
        request_ctx = IncomingRequestContext(
            method=check_request.method,
            raw_path=check_request.path,
        )
        matched = route_matcher.match(endpoints, request_ctx)
        exact_signature_exists = await endpoint_repository.endpoint_signature_exists(
            project_id,
            check_request.method,
            check_request.path,
        )
        if matched is None:
            return EndpointCheckResult(
                exists=False,
                exact_signature_exists=exact_signature_exists,
            )
        delay = await endpoint_repository.get_delay(matched.endpoint.id)
        return EndpointCheckResult(
            exists=True,
            exact_signature_exists=exact_signature_exists,
            endpoint=matched.endpoint,
            path_params=matched.path_params,
            delay_ms=delay.delay_ms if delay else None,
            delay_mode=delay.mode if delay else None,
        )

    @api_router.get("/api/projects/{project_id}/rules")
    async def list_rules(project_id: str) -> dict[str, Any]:
        overviews = await endpoint_repository.get_rule_overviews(project_id)
        return {"rules": [overview.model_dump() for overview in overviews]}

    @api_router.post("/api/projects/{project_id}/rules", status_code=201)
    async def create_rule(
        project_id: str,
        create_request: RuleCreateRequest,
    ) -> dict[str, Any]:
        try:
            result = await endpoint_repository.create_rule(project_id, create_request)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return result.model_dump()

    @api_router.get("/api/projects/{project_id}/logs")
    async def list_logs(project_id: str, limit: int = 50) -> dict[str, Any]:
        overviews = await endpoint_repository.get_request_log_overviews(
            project_id,
            limit=max(1, min(limit, 200)),
        )
        return {"logs": [overview.model_dump() for overview in overviews]}

    @api_router.api_route(
        "/mock/{project_id}/{full_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    )
    async def mock_endpoint(
        project_id: str,
        full_path: str,
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> Response:
        """Resolve mock requests through the DEO pipeline and log asynchronously."""

        request_ctx = await build_request_context(request, full_path)
        final_response, log_entry = await endpoint_orchestrator.resolve(
            project_id,
            request_ctx,
        )
        background_tasks.add_task(endpoint_repository.save_request_log, log_entry)
        return Response(
            content=final_response.body,
            status_code=final_response.status_code,
            headers=final_response.headers,
        )

    return api_router


router = build_deo_router(repository)


def create_app(
    endpoint_repository: EndpointRepository | None = None,
) -> FastAPI:
    """Create a FastAPI app with a configured DEO router.

    Tests and embedding applications can pass their own repository without
    changing the module-level demo router.
    """

    app = FastAPI(title="MockMesh DEO")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    if endpoint_repository is None:
        app.include_router(router)
        _include_architect_router(app, repository)
        return app

    app.include_router(build_deo_router(endpoint_repository))
    _include_architect_router(app, endpoint_repository)
    return app


def _include_architect_router(
    app: FastAPI,
    endpoint_repository: EndpointRepository,
) -> None:
    """Mount the AI Architect routes against the same endpoint repository."""

    from architect.orchestrator import ArchitectOrchestrator
    from architect.router import build_architect_router

    app.include_router(
        build_architect_router(ArchitectOrchestrator(endpoint_repository))
    )
