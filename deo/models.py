"""Pydantic contracts for the MockMesh DEO pipeline.

The models in this module represent both table-shaped repository records and
the objects passed between pipeline stages:

Request -> Route Match -> Rule Evaluation -> Response Selection -> Delay ->
Render -> Final Response.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
DELAY_MODES = {"fixed", "random"}
RULE_OPERATORS = {"equals", "not_equals", "contains", "exists", "gt", "lt", "regex"}
RULE_CONDITION_TYPES = {"query", "headers", "body", "path", "request"}


class Endpoint(BaseModel):
    """Repository record for an active or inactive virtual endpoint."""

    id: str
    project_id: str
    name: str
    path: str
    method: str
    is_active: bool = True


class EndpointRule(BaseModel):
    """Repository record describing one ordered endpoint rule.

    ``action`` is intentionally opaque to the rule engine. The response
    selector interprets it as a response identifier for this implementation.
    """

    id: str
    endpoint_id: str
    condition_type: str
    field: str
    operator: str
    value: Any = None
    action: str | None = None


class EndpointDelay(BaseModel):
    """Repository record for an endpoint delay configuration."""

    id: str
    endpoint_id: str
    delay_ms: int = Field(ge=0)
    mode: str


class ResponseDefinition(BaseModel):
    """Repository record for a configured mock response."""

    id: str
    endpoint_id: str
    status_code: int = Field(ge=100, le=599)
    body_template: str
    is_default: bool = False


class ResponseHeader(BaseModel):
    """Repository record for one configured response header."""

    id: str
    response_id: str
    key: str
    value: str


class IncomingRequestContext(BaseModel):
    """Normalized HTTP request data consumed by the orchestrator."""

    method: str
    raw_path: str
    query_params: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any = None


class MatchedEndpoint(BaseModel):
    """Route matching result containing the endpoint and extracted params."""

    endpoint: Endpoint
    path_params: dict[str, str] = Field(default_factory=dict)


class RuleEvaluationResult(BaseModel):
    """Rule engine result for the first matching rule, if any."""

    matched_rule: EndpointRule | None = None
    action: str | None = None


class SelectedResponse(BaseModel):
    """Response selected before delay and template rendering."""

    status_code: int = Field(ge=100, le=599)
    body_template: str
    headers: dict[str, str] = Field(default_factory=dict)


class FinalResponse(BaseModel):
    """Fully rendered HTTP response returned by the orchestrator."""

    status_code: int = Field(ge=100, le=599)
    headers: dict[str, str] = Field(default_factory=dict)
    body: str


class RequestLogEntry(BaseModel):
    """Repository record for one resolved request/response exchange."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str | None = None
    endpoint_id: str | None = None
    method: str
    path: str
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_body: Any = None
    response_code: int
    response_time_ms: float = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EndpointCreateRequest(BaseModel):
    """Dashboard request for creating a new in-memory endpoint config."""

    name: str = Field(min_length=1, max_length=120)
    path: str = Field(min_length=1, max_length=256)
    method: str
    is_active: bool = True
    status_code: int = Field(default=200, ge=100, le=599)
    body_template: str = Field(default='{"ok":true}', min_length=1)
    headers: dict[str, str] = Field(
        default_factory=lambda: {"content-type": "application/json"}
    )
    delay_ms: int | None = Field(default=None, ge=0)
    delay_mode: str = "fixed"

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        method = value.strip().upper()
        if method not in HTTP_METHODS:
            allowed = ", ".join(sorted(HTTP_METHODS))
            raise ValueError(f"method must be one of: {allowed}")
        return method

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        path = value.strip()
        if not path:
            raise ValueError("path is required")
        return path if path.startswith("/") else f"/{path}"

    @field_validator("delay_mode")
    @classmethod
    def normalize_delay_mode(cls, value: str) -> str:
        delay_mode = value.strip().lower()
        if delay_mode not in DELAY_MODES:
            allowed = ", ".join(sorted(DELAY_MODES))
            raise ValueError(f"delay_mode must be one of: {allowed}")
        return delay_mode


class ProjectOverview(BaseModel):
    """Project option available to the logged-in dashboard user."""

    id: str
    name: str
    description: str | None = None


class LoginRequest(BaseModel):
    """Demo login request used by the dashboard control plane."""

    email: str = Field(min_length=3, max_length=160)
    project_id: str | None = None


class LoginResult(BaseModel):
    """Demo login result with scoped project options."""

    user_id: str
    display_name: str
    token: str
    projects: list[ProjectOverview]
    default_project_id: str


class EndpointCreateResult(BaseModel):
    """Dashboard response after creating an endpoint and default response."""

    endpoint: Endpoint
    response: ResponseDefinition
    delay: EndpointDelay | None = None


class EndpointCheckRequest(BaseModel):
    """Dashboard request for checking whether a method/path can resolve."""

    method: str
    path: str

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        method = value.strip().upper()
        if method not in HTTP_METHODS:
            allowed = ", ".join(sorted(HTTP_METHODS))
            raise ValueError(f"method must be one of: {allowed}")
        return method

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        path = value.strip()
        if not path:
            raise ValueError("path is required")
        return path if path.startswith("/") else f"/{path}"


class EndpointCheckResult(BaseModel):
    """Dashboard response for route-existence checks."""

    exists: bool
    exact_signature_exists: bool = False
    endpoint: Endpoint | None = None
    path_params: dict[str, str] = Field(default_factory=dict)
    delay_ms: int | None = None
    delay_mode: str | None = None


class EndpointOverview(BaseModel):
    """Compact endpoint summary used by the dashboard inventory table."""

    id: str
    name: str
    path: str
    method: str
    is_active: bool
    default_status_code: int | None = None
    delay_ms: int | None = None
    delay_mode: str | None = None


class RuleCreateRequest(BaseModel):
    """Dashboard request for creating a rule and its response action."""

    endpoint_id: str = Field(min_length=1)
    condition_type: str
    field: str = Field(min_length=1, max_length=120)
    operator: str
    value: Any = None
    status_code: int = Field(default=200, ge=100, le=599)
    body_template: str = Field(default='{"matched":true}', min_length=1)
    headers: dict[str, str] = Field(
        default_factory=lambda: {"content-type": "application/json"}
    )

    @field_validator("condition_type")
    @classmethod
    def normalize_condition_type(cls, value: str) -> str:
        condition_type = value.strip().lower()
        if condition_type not in RULE_CONDITION_TYPES:
            allowed = ", ".join(sorted(RULE_CONDITION_TYPES))
            raise ValueError(f"condition_type must be one of: {allowed}")
        return condition_type

    @field_validator("operator")
    @classmethod
    def normalize_operator(cls, value: str) -> str:
        operator = value.strip().lower()
        if operator not in RULE_OPERATORS:
            allowed = ", ".join(sorted(RULE_OPERATORS))
            raise ValueError(f"operator must be one of: {allowed}")
        return operator


class RuleCreateResult(BaseModel):
    """Dashboard response after creating a rule and response action."""

    rule: EndpointRule
    response: ResponseDefinition


class RuleOverview(BaseModel):
    """Compact rule summary used by the dashboard rules table."""

    id: str
    endpoint_id: str
    endpoint_name: str
    endpoint_method: str
    endpoint_path: str
    condition_type: str
    field: str
    operator: str
    value: Any = None
    action: str | None = None
    action_status_code: int | None = None


class RequestLogOverview(BaseModel):
    """Compact request log summary used by the dashboard logs table."""

    id: str
    endpoint_id: str | None = None
    endpoint_name: str | None = None
    method: str
    path: str
    response_code: int
    response_time_ms: float
    created_at: datetime
