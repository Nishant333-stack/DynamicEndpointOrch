"""Repository abstractions and in-memory seed data for MockMesh DEO.

Pipeline components access endpoint configuration only through the
``EndpointRepository`` interface. The in-memory implementation is deliberately
small and deterministic so tests can exercise route matching, rules, delays,
rendering, and logging without wiring a real database.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import uuid4

from deo.models import (
    Endpoint,
    EndpointCreateRequest,
    EndpointCreateResult,
    EndpointDelay,
    EndpointOverview,
    EndpointRule,
    ProjectOverview,
    RequestLogEntry,
    RequestLogOverview,
    ResponseDefinition,
    ResponseHeader,
    RuleCreateRequest,
    RuleCreateResult,
    RuleOverview,
)


class EndpointRepository(ABC):
    """Abstract access layer for all DEO configuration and request logs."""

    @abstractmethod
    async def get_project_overviews(self) -> list[ProjectOverview]:
        """Return projects available to the dashboard user."""

    @abstractmethod
    async def get_endpoints(self, project_id: str) -> list[Endpoint]:
        """Return all endpoints belonging to the project."""

    @abstractmethod
    async def get_active_endpoints(self, project_id: str) -> list[Endpoint]:
        """Return active endpoints belonging to the project."""

    @abstractmethod
    async def get_rules(self, endpoint_id: str) -> list[EndpointRule]:
        """Return ordered rules for the endpoint."""

    @abstractmethod
    async def get_responses(self, endpoint_id: str) -> list[ResponseDefinition]:
        """Return configured responses for the endpoint."""

    @abstractmethod
    async def get_response_headers(self, response_id: str) -> list[ResponseHeader]:
        """Return headers configured for a response."""

    @abstractmethod
    async def get_delay(self, endpoint_id: str) -> EndpointDelay | None:
        """Return delay configuration for the endpoint, if any."""

    @abstractmethod
    async def get_endpoint_overviews(self, project_id: str) -> list[EndpointOverview]:
        """Return dashboard-ready endpoint summaries for a project."""

    @abstractmethod
    async def get_rule_overviews(self, project_id: str) -> list[RuleOverview]:
        """Return dashboard-ready rule summaries for a project."""

    @abstractmethod
    async def create_rule(
        self,
        project_id: str,
        request: RuleCreateRequest,
    ) -> RuleCreateResult:
        """Create a rule and response action for an endpoint."""

    @abstractmethod
    async def get_request_log_overviews(
        self,
        project_id: str,
        limit: int = 50,
    ) -> list[RequestLogOverview]:
        """Return recent request logs for a project."""

    @abstractmethod
    async def endpoint_signature_exists(
        self,
        project_id: str,
        method: str,
        path: str,
    ) -> bool:
        """Return whether an endpoint with the exact method/path exists."""

    @abstractmethod
    async def create_endpoint(
        self,
        project_id: str,
        request: EndpointCreateRequest,
    ) -> EndpointCreateResult:
        """Create an endpoint with a default response and optional delay."""

    @abstractmethod
    async def save_request_log(self, log_entry: RequestLogEntry) -> None:
        """Persist a resolved request log entry."""


class InMemoryEndpointRepository(EndpointRepository):
    """In-memory repository seeded with representative payment endpoints."""

    def __init__(self) -> None:
        self.projects: list[ProjectOverview] = [
            ProjectOverview(
                id="demo",
                name="Demo",
                description="Primary payment mocks",
            ),
            ProjectOverview(
                id="checkout-lab",
                name="Checkout Lab",
                description="Card and checkout scenarios",
            ),
            ProjectOverview(
                id="refunds-qa",
                name="Refunds QA",
                description="Refund validation sandbox",
            ),
        ]
        self.endpoints: list[Endpoint] = [
            Endpoint(
                id="endpoint_payment_lookup",
                project_id="demo",
                name="Payment lookup",
                path="/payments/{payment_id}",
                method="GET",
                is_active=True,
            ),
            Endpoint(
                id="endpoint_payout_create",
                project_id="demo",
                name="Create payout",
                path="/payouts",
                method="POST",
                is_active=True,
            ),
            Endpoint(
                id="endpoint_health",
                project_id="demo",
                name="Health check",
                path="/health",
                method="GET",
                is_active=True,
            ),
            Endpoint(
                id="endpoint_checkout_card_create",
                project_id="checkout-lab",
                name="Create card",
                path="/cards",
                method="POST",
                is_active=True,
            ),
            Endpoint(
                id="endpoint_refund_status",
                project_id="refunds-qa",
                name="Refund status",
                path="/refunds/{refund_id}/status",
                method="GET",
                is_active=True,
            ),
        ]
        self.rules: list[EndpointRule] = [
            EndpointRule(
                id="rule_payment_failed",
                endpoint_id="endpoint_payment_lookup",
                condition_type="query",
                field="status",
                operator="equals",
                value="failed",
                action="response_payment_failed",
            )
        ]
        self.delays: list[EndpointDelay] = [
            EndpointDelay(
                id="delay_payout_create",
                endpoint_id="endpoint_payout_create",
                delay_ms=650,
                mode="fixed",
            )
        ]
        self.responses: list[ResponseDefinition] = [
            ResponseDefinition(
                id="response_payment_default",
                endpoint_id="endpoint_payment_lookup",
                status_code=200,
                body_template=(
                    '{"payment_id":"{{payment_id}}","status":"authorized",'
                    '"served_at":"{{now}}","trace_id":"{{uuid}}"}'
                ),
                is_default=True,
            ),
            ResponseDefinition(
                id="response_payment_failed",
                endpoint_id="endpoint_payment_lookup",
                status_code=402,
                body_template=(
                    '{"payment_id":"{{payment_id}}","status":"failed",'
                    '"reason":"{{query.reason}}"}'
                ),
                is_default=False,
            ),
            ResponseDefinition(
                id="response_payout_queued",
                endpoint_id="endpoint_payout_create",
                status_code=202,
                body_template=(
                    '{"state":"queued","amount":{{body.amount}},'
                    '"currency":"{{body.currency}}","payout_id":"{{uuid}}"}'
                ),
                is_default=True,
            ),
            ResponseDefinition(
                id="response_health",
                endpoint_id="endpoint_health",
                status_code=200,
                body_template='{"ok":true,"now":"{{now}}"}',
                is_default=True,
            ),
            ResponseDefinition(
                id="response_checkout_card_create",
                endpoint_id="endpoint_checkout_card_create",
                status_code=201,
                body_template=(
                    '{"card_id":"{{uuid}}","status":"valid",'
                    '"brand":"{{body.brand}}"}'
                ),
                is_default=True,
            ),
            ResponseDefinition(
                id="response_refund_status",
                endpoint_id="endpoint_refund_status",
                status_code=200,
                body_template=(
                    '{"refund_id":"{{refund_id}}","status":"processing",'
                    '"trace_id":"{{uuid}}"}'
                ),
                is_default=True,
            ),
        ]
        self.headers: list[ResponseHeader] = [
            ResponseHeader(
                id="header_payment_default_content_type",
                response_id="response_payment_default",
                key="content-type",
                value="application/json",
            ),
            ResponseHeader(
                id="header_payment_default_endpoint",
                response_id="response_payment_default",
                key="x-mockmesh-endpoint",
                value="{{payment_id}}",
            ),
            ResponseHeader(
                id="header_payment_failed_content_type",
                response_id="response_payment_failed",
                key="content-type",
                value="application/json",
            ),
            ResponseHeader(
                id="header_payment_failed_endpoint",
                response_id="response_payment_failed",
                key="x-mockmesh-endpoint",
                value="{{payment_id}}",
            ),
            ResponseHeader(
                id="header_payout_content_type",
                response_id="response_payout_queued",
                key="content-type",
                value="application/json",
            ),
            ResponseHeader(
                id="header_payout_delay",
                response_id="response_payout_queued",
                key="x-mockmesh-delay",
                value="fixed",
            ),
            ResponseHeader(
                id="header_health_content_type",
                response_id="response_health",
                key="content-type",
                value="application/json",
            ),
            ResponseHeader(
                id="header_checkout_card_create_content_type",
                response_id="response_checkout_card_create",
                key="content-type",
                value="application/json",
            ),
            ResponseHeader(
                id="header_refund_status_content_type",
                response_id="response_refund_status",
                key="content-type",
                value="application/json",
            ),
        ]
        self.request_logs: list[RequestLogEntry] = []

    async def get_project_overviews(self) -> list[ProjectOverview]:
        return list(self.projects)

    async def get_endpoints(self, project_id: str) -> list[Endpoint]:
        return [endpoint for endpoint in self.endpoints if endpoint.project_id == project_id]

    async def get_active_endpoints(self, project_id: str) -> list[Endpoint]:
        return [
            endpoint
            for endpoint in self.endpoints
            if endpoint.project_id == project_id and endpoint.is_active
        ]

    async def get_rules(self, endpoint_id: str) -> list[EndpointRule]:
        return [rule for rule in self.rules if rule.endpoint_id == endpoint_id]

    async def get_responses(self, endpoint_id: str) -> list[ResponseDefinition]:
        return [
            response for response in self.responses if response.endpoint_id == endpoint_id
        ]

    async def get_response_headers(self, response_id: str) -> list[ResponseHeader]:
        return [header for header in self.headers if header.response_id == response_id]

    async def get_delay(self, endpoint_id: str) -> EndpointDelay | None:
        return next(
            (delay for delay in self.delays if delay.endpoint_id == endpoint_id),
            None,
        )

    async def endpoint_signature_exists(
        self,
        project_id: str,
        method: str,
        path: str,
    ) -> bool:
        normalized_method = method.upper()
        normalized_path = self._normalize_path(path)
        return any(
            endpoint.project_id == project_id
            and endpoint.method.upper() == normalized_method
            and self._normalize_path(endpoint.path) == normalized_path
            for endpoint in self.endpoints
        )

    async def create_endpoint(
        self,
        project_id: str,
        request: EndpointCreateRequest,
    ) -> EndpointCreateResult:
        endpoint_id = f"endpoint_{uuid4().hex}"
        response_id = f"response_{uuid4().hex}"
        endpoint = Endpoint(
            id=endpoint_id,
            project_id=project_id,
            name=request.name,
            path=request.path,
            method=request.method,
            is_active=request.is_active,
        )
        response = ResponseDefinition(
            id=response_id,
            endpoint_id=endpoint_id,
            status_code=request.status_code,
            body_template=request.body_template,
            is_default=True,
        )
        response_headers = [
            ResponseHeader(
                id=f"header_{uuid4().hex}",
                response_id=response_id,
                key=key.lower(),
                value=value,
            )
            for key, value in request.headers.items()
            if key.strip()
        ]
        delay = None
        if request.delay_ms:
            delay = EndpointDelay(
                id=f"delay_{uuid4().hex}",
                endpoint_id=endpoint_id,
                delay_ms=request.delay_ms,
                mode=request.delay_mode,
            )
            self.delays.append(delay)

        self.endpoints.append(endpoint)
        self.responses.append(response)
        self.headers.extend(response_headers)

        return EndpointCreateResult(endpoint=endpoint, response=response, delay=delay)

    async def get_endpoint_overviews(self, project_id: str) -> list[EndpointOverview]:
        overviews: list[EndpointOverview] = []
        for endpoint in await self.get_endpoints(project_id):
            responses = await self.get_responses(endpoint.id)
            default_response = next(
                (response for response in responses if response.is_default),
                responses[0] if responses else None,
            )
            delay = await self.get_delay(endpoint.id)
            overviews.append(
                EndpointOverview(
                    id=endpoint.id,
                    name=endpoint.name,
                    path=endpoint.path,
                    method=endpoint.method,
                    is_active=endpoint.is_active,
                    default_status_code=(
                        default_response.status_code if default_response else None
                    ),
                    delay_ms=delay.delay_ms if delay else None,
                    delay_mode=delay.mode if delay else None,
                )
            )
        return overviews

    async def get_rule_overviews(self, project_id: str) -> list[RuleOverview]:
        endpoint_by_id = {
            endpoint.id: endpoint for endpoint in await self.get_endpoints(project_id)
        }
        response_by_id = {response.id: response for response in self.responses}
        overviews: list[RuleOverview] = []
        for rule in self.rules:
            endpoint = endpoint_by_id.get(rule.endpoint_id)
            if endpoint is None:
                continue
            action_response = response_by_id.get(rule.action or "")
            overviews.append(
                RuleOverview(
                    id=rule.id,
                    endpoint_id=rule.endpoint_id,
                    endpoint_name=endpoint.name,
                    endpoint_method=endpoint.method,
                    endpoint_path=endpoint.path,
                    condition_type=rule.condition_type,
                    field=rule.field,
                    operator=rule.operator,
                    value=rule.value,
                    action=rule.action,
                    action_status_code=(
                        action_response.status_code if action_response else None
                    ),
                )
            )
        return overviews

    async def create_rule(
        self,
        project_id: str,
        request: RuleCreateRequest,
    ) -> RuleCreateResult:
        endpoint = next(
            (
                endpoint
                for endpoint in self.endpoints
                if endpoint.project_id == project_id and endpoint.id == request.endpoint_id
            ),
            None,
        )
        if endpoint is None:
            raise ValueError("Endpoint does not exist for this project.")

        response_id = f"response_{uuid4().hex}"
        rule_id = f"rule_{uuid4().hex}"
        response = ResponseDefinition(
            id=response_id,
            endpoint_id=endpoint.id,
            status_code=request.status_code,
            body_template=request.body_template,
            is_default=False,
        )
        response_headers = [
            ResponseHeader(
                id=f"header_{uuid4().hex}",
                response_id=response_id,
                key=key.lower(),
                value=value,
            )
            for key, value in request.headers.items()
            if key.strip()
        ]
        rule = EndpointRule(
            id=rule_id,
            endpoint_id=endpoint.id,
            condition_type=request.condition_type,
            field=request.field,
            operator=request.operator,
            value=request.value,
            action=response_id,
        )
        self.responses.append(response)
        self.headers.extend(response_headers)
        self.rules.append(rule)
        return RuleCreateResult(rule=rule, response=response)

    async def get_request_log_overviews(
        self,
        project_id: str,
        limit: int = 50,
    ) -> list[RequestLogOverview]:
        endpoint_by_id = {
            endpoint.id: endpoint for endpoint in await self.get_endpoints(project_id)
        }
        logs = [
            log_entry
            for log_entry in self.request_logs
            if log_entry.project_id == project_id
            or (
                log_entry.project_id is None
                and log_entry.endpoint_id in endpoint_by_id
            )
        ]
        recent_logs = sorted(logs, key=lambda log_entry: log_entry.created_at, reverse=True)
        return [
            RequestLogOverview(
                id=log_entry.id,
                endpoint_id=log_entry.endpoint_id,
                endpoint_name=(
                    endpoint_by_id[log_entry.endpoint_id].name
                    if log_entry.endpoint_id in endpoint_by_id
                    else None
                ),
                method=log_entry.method,
                path=log_entry.path,
                response_code=log_entry.response_code,
                response_time_ms=log_entry.response_time_ms,
                created_at=log_entry.created_at,
            )
            for log_entry in recent_logs[:limit]
        ]

    async def save_request_log(self, log_entry: RequestLogEntry) -> None:
        self.request_logs.append(log_entry)

    @staticmethod
    def _normalize_path(path: str) -> str:
        stripped = path.strip()
        normalized = stripped if stripped.startswith("/") else f"/{stripped}"
        return normalized.rstrip("/") or "/"
