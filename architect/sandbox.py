"""Isolated sandbox simulation engine for generated MockMesh configs."""

from __future__ import annotations

from time import perf_counter

from architect.models import (
    ArchitectMetrics,
    GeneratedConfig,
    IntegrationScenario,
    SandboxCaseResult,
    SandboxTestResult,
)
from deo.models import EndpointCreateRequest, IncomingRequestContext, RuleCreateRequest
from deo.orchestrator import DEOOrchestrator
from deo.repository import InMemoryEndpointRepository


class SandboxSimulationEngine:
    """Run generated configs against an isolated DEO repository."""

    async def run(
        self,
        project_id: str,
        config: GeneratedConfig,
    ) -> SandboxTestResult:
        repository = InMemoryEndpointRepository()
        repository.endpoints = []
        repository.rules = []
        repository.delays = []
        repository.responses = []
        repository.headers = []
        repository.request_logs = []

        endpoint_id_by_key: dict[str, str] = {}
        for endpoint_config in config.endpoints:
            result = await repository.create_endpoint(
                project_id,
                endpoint_config.endpoint,
            )
            endpoint_id_by_key[endpoint_config.key] = result.endpoint.id

        for rule_config in config.rules:
            endpoint_id = endpoint_id_by_key[rule_config.endpoint_key]
            rule_request = self._rule_with_endpoint_id(rule_config.rule, endpoint_id)
            await repository.create_rule(project_id, rule_request)

        orchestrator = DEOOrchestrator(repository)
        cases = [
            await self._run_case(project_id, orchestrator, scenario)
            for scenario in config.scenarios
        ]
        return SandboxTestResult(
            passed=all(case.passed for case in cases),
            cases=cases,
        )

    async def _run_case(
        self,
        project_id: str,
        orchestrator: DEOOrchestrator,
        scenario: IntegrationScenario,
    ) -> SandboxCaseResult:
        started_at = perf_counter()
        final_response, _log = await orchestrator.resolve(
            project_id,
            IncomingRequestContext(
                method=scenario.method,
                raw_path=scenario.path,
                query_params=scenario.query_params,
                headers=scenario.headers,
                body=scenario.body,
            ),
        )
        elapsed_ms = (perf_counter() - started_at) * 1000
        deltas: list[str] = []
        if final_response.status_code != scenario.expected_status_code:
            deltas.append(
                f"Expected status {scenario.expected_status_code}, got {final_response.status_code}"
            )
        for expected_fragment in scenario.expected_body_contains:
            if expected_fragment not in final_response.body:
                deltas.append(f"Missing response fragment: {expected_fragment}")

        return SandboxCaseResult(
            scenario_name=scenario.name,
            passed=not deltas,
            expected_status_code=scenario.expected_status_code,
            actual_status_code=final_response.status_code,
            response_body=final_response.body,
            response_time_ms=elapsed_ms,
            deltas=deltas,
        )

    @staticmethod
    def _rule_with_endpoint_id(
        rule: RuleCreateRequest,
        endpoint_id: str,
    ) -> RuleCreateRequest:
        return RuleCreateRequest(
            endpoint_id=endpoint_id,
            condition_type=rule.condition_type,
            field=rule.field,
            operator=rule.operator,
            value=rule.value,
            status_code=rule.status_code,
            body_template=rule.body_template,
            headers=rule.headers,
        )


class MetricsEvaluator:
    """Compute quantitative quality metrics for architect results."""

    def evaluate(
        self,
        raw_spec: str,
        config: GeneratedConfig,
        sandbox_result: SandboxTestResult,
        iterations: int,
    ) -> ArchitectMetrics:
        spec_lower = raw_spec.lower()
        endpoint_mentions = sum(
            1
            for endpoint in config.endpoints
            if endpoint.endpoint.path.lower().strip("/") in spec_lower
            or endpoint.endpoint.method.lower() in spec_lower
        )
        specification_coverage = (
            endpoint_mentions / len(config.endpoints) if config.endpoints else 0
        )

        scenario_count = len(config.scenarios)
        matched_paths = sum(
            1
            for scenario in config.scenarios
            if any(
                self._path_matches(endpoint.endpoint.path, scenario.path)
                for endpoint in config.endpoints
            )
        )
        path_parsing_match_rate = matched_paths / scenario_count if scenario_count else 1
        pass_count = sum(1 for case in sandbox_result.cases if case.passed)
        simulation_pass_rate = (
            pass_count / len(sandbox_result.cases) if sandbox_result.cases else 1
        )
        parameter_accuracy = path_parsing_match_rate

        return ArchitectMetrics(
            specification_coverage=min(1.0, specification_coverage),
            parameter_mapping_accuracy=parameter_accuracy,
            path_parsing_match_rate=path_parsing_match_rate,
            simulation_pass_rate=simulation_pass_rate,
            iterations=iterations,
        )

    @staticmethod
    def _path_matches(template: str, concrete: str) -> bool:
        template_parts = template.strip("/").split("/")
        concrete_parts = concrete.strip("/").split("/")
        if len(template_parts) != len(concrete_parts):
            return False
        return all(
            part.startswith("{") and part.endswith("}") or part == concrete_part
            for part, concrete_part in zip(template_parts, concrete_parts)
        )
