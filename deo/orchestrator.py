"""DEO orchestration stage for resolving incoming requests.

``DEOOrchestrator.resolve`` runs the full pipeline:

Request -> Route Match -> Rule Evaluation -> Response Selection -> Delay ->
Render -> Final Response.
"""

from __future__ import annotations

from time import perf_counter

from deo.delay_engine import DelayEngine
from deo.models import FinalResponse, IncomingRequestContext, RequestLogEntry
from deo.repository import EndpointRepository
from deo.response_renderer import ResponseRenderer
from deo.response_selector import ResponseSelector
from deo.route_matcher import RouteMatcher
from deo.rule_engine import RuleEngine


class DEOOrchestrator:
    """Coordinate all DEO pipeline stages for a project request."""

    def __init__(
        self,
        repository: EndpointRepository,
        route_matcher: RouteMatcher | None = None,
        rule_engine: RuleEngine | None = None,
        response_selector: ResponseSelector | None = None,
        delay_engine: DelayEngine | None = None,
        response_renderer: ResponseRenderer | None = None,
    ) -> None:
        self.repository = repository
        self.route_matcher = route_matcher or RouteMatcher()
        self.rule_engine = rule_engine or RuleEngine()
        self.response_selector = response_selector or ResponseSelector(repository)
        self.delay_engine = delay_engine or DelayEngine()
        self.response_renderer = response_renderer or ResponseRenderer()

    async def resolve(
        self,
        project_id: str,
        request_ctx: IncomingRequestContext,
    ) -> tuple[FinalResponse, RequestLogEntry]:
        """Resolve a request into a final response and request log entry."""

        started_at = perf_counter()
        endpoint_id: str | None = None

        endpoints = await self.repository.get_active_endpoints(project_id)
        matched_endpoint = self.route_matcher.match(endpoints, request_ctx)

        if matched_endpoint is None:
            final_response = FinalResponse(
                status_code=404,
                headers={"content-type": "application/json"},
                body='{"error":"endpoint_not_found"}',
            )
        else:
            endpoint = matched_endpoint.endpoint
            endpoint_id = endpoint.id
            rules = await self.repository.get_rules(endpoint.id)
            rule_result = self.rule_engine.evaluate(
                rules,
                request_ctx,
                matched_endpoint.path_params,
            )
            selected_response = await self.response_selector.select(
                endpoint.id,
                rule_result.action,
            )
            delay = await self.repository.get_delay(endpoint.id)
            await self.delay_engine.apply(delay)
            final_response = self.response_renderer.render(
                selected_response,
                request_ctx,
                matched_endpoint.path_params,
            )

            # TODO: Add endpoint_logic script execution here if the product
            # explicitly reintroduces scriptable endpoint behaviors.

        response_time_ms = (perf_counter() - started_at) * 1000
        log_entry = RequestLogEntry(
            endpoint_id=endpoint_id,
            method=request_ctx.method.upper(),
            path=request_ctx.raw_path,
            request_headers=request_ctx.headers,
            request_body=request_ctx.body,
            response_code=final_response.status_code,
            response_time_ms=response_time_ms,
        )
        return final_response, log_entry
