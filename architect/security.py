"""Authentication, tenant isolation, and RBAC helpers."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from architect.models import Principal


class RBACService:
    """Minimal project-scoped RBAC service for architect routes."""

    def __init__(self, token_map: dict[str, Principal] | None = None) -> None:
        self.token_map = token_map or {
            "dev-admin": Principal(
                user_id="dev-admin",
                project_roles={
                    "demo": {"architect", "admin", "viewer"},
                    "checkout-lab": {"architect", "admin", "viewer"},
                    "refunds-qa": {"architect", "admin", "viewer"},
                },
            )
        }

    def authenticate(self, authorization: str | None) -> Principal:
        if not authorization:
            return self.token_map["dev-admin"]
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header.",
            )
        principal = self.token_map.get(token)
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown bearer token.",
            )
        return principal

    def require_project_role(
        self,
        principal: Principal,
        project_id: str,
        allowed_roles: set[str],
    ) -> None:
        if not principal.has_role(project_id, allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Principal is not authorized for this project.",
            )

    def principal_from_request(self, request: Request) -> Principal:
        return self.authenticate(request.headers.get("authorization"))
