"""Pydantic contracts for the AI Endpoint Architect workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from deo.models import EndpointCreateRequest, RuleCreateRequest


class TaskStatus(StrEnum):
    """Lifecycle states for queued architect tasks."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"


class AgentRole(StrEnum):
    """Registered agent role names used by the DAG engine."""

    PLANNER = "planner"
    CODEGEN = "codegen"
    CRITIC = "critic"
    SANDBOX = "sandbox"


class ArchitectPhase(StrEnum):
    """State handler identifiers in the architect DAG."""

    PLAN = "plan"
    CODEGEN = "codegen"
    CRITIC = "critic"
    SANDBOX = "sandbox"
    COMPLETE = "complete"
    DEAD_LETTER = "dead_letter"


class Principal(BaseModel):
    """Authenticated user identity with project-scoped roles."""

    user_id: str
    project_roles: dict[str, set[str]] = Field(default_factory=dict)

    def has_role(self, project_id: str, allowed_roles: set[str]) -> bool:
        return bool(self.project_roles.get(project_id, set()) & allowed_roles)


class AgentRequest(BaseModel):
    """Request accepted by the architect generation API."""

    project_id: str = Field(min_length=1)
    raw_spec: str = Field(min_length=1)
    requested_by: str = Field(default="anonymous")
    commit_on_success: bool = False


class CanonicalContext(BaseModel):
    """RAG-like canonical guidance injected into agent prompts."""

    project_id: str
    naming_standards: list[str] = Field(default_factory=list)
    standard_objects: dict[str, Any] = Field(default_factory=dict)
    previous_patterns: list[str] = Field(default_factory=list)


class IntegrationScenario(BaseModel):
    """Expected behavior used by the sandbox simulation engine."""

    name: str
    method: str
    path: str
    query_params: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any = None
    expected_status_code: int = Field(ge=100, le=599)
    expected_body_contains: list[str] = Field(default_factory=list)

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        path = value.strip()
        return path if path.startswith("/") else f"/{path}"


class PlannedEndpoint(BaseModel):
    """Planner output for one endpoint intention."""

    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    method: str
    default_status_code: int = Field(default=200, ge=100, le=599)
    body_template: str = Field(default='{"ok":true}', min_length=1)
    delay_ms: int | None = Field(default=None, ge=0)
    delay_mode: str = "fixed"

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        path = value.strip()
        return path if path.startswith("/") else f"/{path}"


class PlannedRule(BaseModel):
    """Planner output for conditional response behavior."""

    endpoint_key: str
    condition_type: str = "query"
    field: str
    operator: str = "equals"
    value: Any = None
    status_code: int = Field(default=200, ge=100, le=599)
    body_template: str = Field(default='{"matched":true}', min_length=1)


class EndpointPlan(BaseModel):
    """Structured plan produced from a natural-language API specification."""

    summary: str
    endpoints: list[PlannedEndpoint] = Field(default_factory=list)
    rules: list[PlannedRule] = Field(default_factory=list)
    scenarios: list[IntegrationScenario] = Field(default_factory=list)
    canonical_context: CanonicalContext | None = None


class GeneratedEndpointConfig(BaseModel):
    """CodeGen endpoint config bound to an architect-local key."""

    key: str
    endpoint: EndpointCreateRequest


class GeneratedRuleConfig(BaseModel):
    """CodeGen rule config referencing a generated endpoint key."""

    endpoint_key: str
    rule: RuleCreateRequest


class GeneratedConfig(BaseModel):
    """Pydantic-valid MockMesh configuration candidate."""

    endpoints: list[GeneratedEndpointConfig] = Field(default_factory=list)
    rules: list[GeneratedRuleConfig] = Field(default_factory=list)
    scenarios: list[IntegrationScenario] = Field(default_factory=list)


class CriticIssue(BaseModel):
    """Deterministic or semantic validation issue."""

    severity: str
    message: str
    location: str | None = None


class CriticReport(BaseModel):
    """Validation report for a generated configuration."""

    passed: bool
    issues: list[CriticIssue] = Field(default_factory=list)
    semantic_notes: list[str] = Field(default_factory=list)


class SandboxCaseResult(BaseModel):
    """Result for one sandboxed request simulation."""

    scenario_name: str
    passed: bool
    expected_status_code: int
    actual_status_code: int
    response_body: str
    response_time_ms: float
    deltas: list[str] = Field(default_factory=list)


class SandboxTestResult(BaseModel):
    """Aggregate sandbox execution report."""

    passed: bool
    cases: list[SandboxCaseResult] = Field(default_factory=list)


class ArchitectMetrics(BaseModel):
    """Quantitative evaluation metrics for one generation cycle."""

    specification_coverage: float = Field(ge=0, le=1)
    parameter_mapping_accuracy: float = Field(ge=0, le=1)
    path_parsing_match_rate: float = Field(ge=0, le=1)
    simulation_pass_rate: float = Field(ge=0, le=1)
    iterations: int = Field(ge=0)


class AgentStepTrace(BaseModel):
    """Observable trace for one DAG/agent transition."""

    step: str
    agent: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    response_tokens: int = Field(default=0, ge=0)
    state_delta: dict[str, Any] = Field(default_factory=dict)
    reasoning_trace: str | None = None


class ArchitectResult(BaseModel):
    """Final response returned by the architect workflow."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    status: TaskStatus
    plan: EndpointPlan | None = None
    generated_config: GeneratedConfig | None = None
    critic_report: CriticReport | None = None
    sandbox_result: SandboxTestResult | None = None
    metrics: ArchitectMetrics | None = None
    traces: list[AgentStepTrace] = Field(default_factory=list)
    error: str | None = None


class ArchitectTask(BaseModel):
    """Queued task state exposed by polling routes."""

    task_id: str
    request: AgentRequest
    status: TaskStatus = TaskStatus.QUEUED
    result: ArchitectResult | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CommitRequest(BaseModel):
    """Request to commit a successful architect result to the live repository."""

    task_id: str
    project_id: str


class CommitResult(BaseModel):
    """Summary of committed endpoint and rule counts."""

    task_id: str
    project_id: str
    committed_endpoints: int
    committed_rules: int
