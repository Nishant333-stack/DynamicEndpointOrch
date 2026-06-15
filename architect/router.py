"""Protected FastAPI routes for AI Endpoint Architect workflows."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from architect.models import AgentRequest, ArchitectTask, CommitRequest, CommitResult
from architect.orchestrator import ArchitectOrchestrator
from architect.security import RBACService
from deo.repository import EndpointRepository


def build_architect_router(
    orchestrator: ArchitectOrchestrator,
    rbac: RBACService | None = None,
) -> APIRouter:
    """Build protected architect routes bound to an orchestrator instance."""

    router = APIRouter(prefix="/architect", tags=["architect"])
    rbac_service = rbac or RBACService()

    @router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
    async def generate(request: Request, payload: AgentRequest) -> dict[str, str]:
        principal = rbac_service.principal_from_request(request)
        rbac_service.require_project_role(
            principal,
            payload.project_id,
            {"architect", "admin"},
        )
        task = await orchestrator.submit(
            payload.model_copy(update={"requested_by": principal.user_id})
        )
        return {"task_id": task.task_id, "status": task.status}

    @router.get("/tasks/{task_id}")
    async def get_task(request: Request, task_id: str) -> ArchitectTask:
        principal = rbac_service.principal_from_request(request)
        task = orchestrator.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        rbac_service.require_project_role(
            principal,
            task.request.project_id,
            {"architect", "admin", "viewer"},
        )
        return task

    @router.post("/commit")
    async def commit(request: Request, payload: CommitRequest) -> CommitResult:
        principal = rbac_service.principal_from_request(request)
        rbac_service.require_project_role(
            principal,
            payload.project_id,
            {"architect", "admin"},
        )
        try:
            return await orchestrator.commit(payload.task_id, payload.project_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    return router


def create_architect_orchestrator(
    repository: EndpointRepository,
) -> ArchitectOrchestrator:
    """Factory used by embedding applications."""

    return ArchitectOrchestrator(repository)
