"""Planner agent that converts raw specs into structured endpoint plans."""

from __future__ import annotations

import re
from typing import Any

from architect.context import CanonicalContextRegistry
from architect.llm_client import JSONOnlyLLMClient
from architect.models import (
    AgentRole,
    CanonicalContext,
    EndpointPlan,
    IntegrationScenario,
    PlannedEndpoint,
    PlannedRule,
)
from architect.registry import AgentMetadata, AgentRegistry, BaseAgent


class PlannerAgent(BaseAgent):
    """Plan endpoints, rules, and sandbox scenarios from natural language."""

    metadata = AgentMetadata(
        name="PlannerAgent",
        role=AgentRole.PLANNER.value,
        model_fallbacks=["mockmesh-planner-primary", "mockmesh-planner-small"],
        prompt_variant="canonical_schema_injection",
        temperature=0.1,
        capabilities=["endpoint_planning", "scenario_generation"],
    )

    def __init__(
        self,
        llm_client: JSONOnlyLLMClient,
        context_registry: CanonicalContextRegistry,
    ) -> None:
        self.llm_client = llm_client
        self.context_registry = context_registry

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        request = state["request"]
        context = self.context_registry.query(request.project_id, request.raw_spec)
        prompt = self._build_prompt(request.raw_spec, context)
        try:
            payload = await self.llm_client.complete_json(
                agent_name=self.metadata.name,
                prompt=prompt,
                schema_hint=EndpointPlan.model_json_schema(),
            )
            plan = EndpointPlan.model_validate(payload)
        except Exception as error:
            plan = self._fallback_plan(request.raw_spec, context)
            return {
                "plan": plan,
                "planner_fallback": str(error),
            }
        return {"plan": plan}

    def _build_prompt(self, raw_spec: str, context: CanonicalContext) -> str:
        return (
            "Return JSON matching EndpointPlan. "
            f"Spec: {raw_spec}\n"
            f"Naming standards: {context.naming_standards}\n"
            f"Standard objects: {context.standard_objects}\n"
            f"Previous patterns: {context.previous_patterns}"
        )

    def _fallback_plan(
        self,
        raw_spec: str,
        context: CanonicalContext,
    ) -> EndpointPlan:
        endpoints: list[PlannedEndpoint] = []
        rules: list[PlannedRule] = []
        scenarios: list[IntegrationScenario] = []
        for index, match in enumerate(
            re.finditer(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[^\s,;]+)", raw_spec, re.I),
            start=1,
        ):
            method = match.group(1).upper()
            path = match.group(2).strip(".")
            segment = self._endpoint_segment(raw_spec, match.start(), match.end())
            key = f"endpoint_{index}"
            status_match = re.search(r"status\s+(\d{3})", segment, re.I)
            delay_match = re.search(
                r"delay\s+(\d+)\s*(?:ms|milliseconds?)?",
                segment,
                re.I,
            )
            status_code = (
                int(status_match.group(1))
                if status_match
                else 202
                if "payout" in path and method == "POST"
                else 200
            )
            endpoint = PlannedEndpoint(
                key=key,
                name=self._name_from_path(method, path),
                path=path,
                method=method,
                default_status_code=status_code,
                body_template=self._body_template(path),
                delay_ms=int(delay_match.group(1)) if delay_match else None,
            )
            endpoints.append(endpoint)
            concrete_path = re.sub(r"{([^}]+)}", lambda m: f"sample_{m.group(1)}", path)
            scenarios.append(
                IntegrationScenario(
                    name=f"{endpoint.name} default",
                    method=method,
                    path=concrete_path,
                    body={"amount": 25, "currency": "USD"} if method in {"POST", "PUT", "PATCH"} else None,
                    expected_status_code=status_code,
                    expected_body_contains=[],
                )
            )

        failed_rule = re.search(r"query\s+([A-Za-z0-9_.-]+)\s*(?:==|equals|=)\s*([A-Za-z0-9_.-]+)", raw_spec, re.I)
        if endpoints and failed_rule:
            rules.append(
                PlannedRule(
                    endpoint_key=endpoints[0].key,
                    condition_type="query",
                    field=failed_rule.group(1),
                    operator="equals",
                    value=failed_rule.group(2),
                    status_code=409,
                    body_template='{"matched":true,"reason":"{{query.reason}}"}',
                )
            )
        if not endpoints:
            endpoints.append(
                PlannedEndpoint(
                    key="endpoint_1",
                    name="Generated health",
                    path="/generated-health",
                    method="GET",
                    body_template='{"ok":true,"trace_id":"{{uuid}}"}',
                )
            )
            scenarios.append(
                IntegrationScenario(
                    name="Generated health default",
                    method="GET",
                    path="/generated-health",
                    expected_status_code=200,
                )
            )

        return EndpointPlan(
            summary="Fallback plan generated without live LLM.",
            endpoints=endpoints,
            rules=rules,
            scenarios=scenarios,
            canonical_context=context,
        )

    @staticmethod
    def _name_from_path(method: str, path: str) -> str:
        resource = path.strip("/").split("/")[0] or "endpoint"
        return f"{method} {resource}".replace("-", " ").title()

    @staticmethod
    def _endpoint_segment(raw_spec: str, start: int, end: int) -> str:
        remainder = raw_spec[end:]
        next_endpoint = re.search(r"\b(GET|POST|PUT|PATCH|DELETE)\s+/", remainder, re.I)
        segment_end = end + next_endpoint.start() if next_endpoint else len(raw_spec)
        return raw_spec[start:segment_end]

    @staticmethod
    def _body_template(path: str) -> str:
        params = re.findall(r"{([^}]+)}", path)
        if params:
            fields = ",".join(f'"{param}":"{{{{{param}}}}}"' for param in params)
            return "{" + fields + ',"trace_id":"{{uuid}}"}'
        return '{"ok":true,"trace_id":"{{uuid}}"}'


def register_agents(
    registry: AgentRegistry,
    llm_client: JSONOnlyLLMClient,
    context_registry: CanonicalContextRegistry,
) -> None:
    registry.register(PlannerAgent(llm_client, context_registry))
