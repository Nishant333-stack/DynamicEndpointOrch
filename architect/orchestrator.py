"""Asynchronous DAG workflow orchestrator for the AI Endpoint Architect."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from architect.codegen_agent import register_agents as register_codegen
from architect.context import CanonicalContextRegistry
from architect.critic_agent import register_agents as register_critic
from architect.llm_client import JSONOnlyLLMClient
from architect.models import (
    AgentRequest,
    AgentRole,
    ArchitectPhase,
    ArchitectResult,
    ArchitectTask,
    CommitResult,
    GeneratedConfig,
    TaskStatus,
)
from architect.planner_agent import register_agents as register_planner
from architect.registry import AgentRegistry
from architect.sandbox import MetricsEvaluator, SandboxSimulationEngine
from architect.telemetry import InMemoryTelemetryRecorder
from deo.models import EndpointCreateRequest, RuleCreateRequest
from deo.repository import EndpointRepository


class DeadLetterQueue:
    """In-memory DLQ for failed architect workflow requests."""

    def __init__(self) -> None:
        self.items: list[ArchitectResult] = []

    def append(self, result: ArchitectResult) -> None:
        self.items.append(result)


class ArchitectOrchestrator:
    """Run planner -> codegen -> critic -> sandbox through a DAG engine."""

    def __init__(
        self,
        repository: EndpointRepository,
        llm_client: JSONOnlyLLMClient | None = None,
        registry: AgentRegistry | None = None,
        context_registry: CanonicalContextRegistry | None = None,
        telemetry: InMemoryTelemetryRecorder | None = None,
        sandbox: SandboxSimulationEngine | None = None,
        metrics: MetricsEvaluator | None = None,
    ) -> None:
        self.repository = repository
        self.telemetry = telemetry or InMemoryTelemetryRecorder()
        self.llm_client = llm_client or JSONOnlyLLMClient(telemetry=self.telemetry)
        self.context_registry = context_registry or CanonicalContextRegistry()
        self.registry = registry or AgentRegistry()
        self.sandbox = sandbox or SandboxSimulationEngine()
        self.metrics = metrics or MetricsEvaluator()
        self.dlq = DeadLetterQueue()
        self.tasks: dict[str, ArchitectTask] = {}
        register_planner(self.registry, self.llm_client, self.context_registry)
        register_codegen(self.registry, self.llm_client)
        register_critic(self.registry, self.llm_client)

    async def submit(self, request: AgentRequest) -> ArchitectTask:
        """Queue an architect generation task and return immediately."""

        task_id = str(uuid4())
        task = ArchitectTask(task_id=task_id, request=request)
        self.tasks[task_id] = task
        asyncio.create_task(self._run_task(task_id))
        return task

    def get_task(self, task_id: str) -> ArchitectTask | None:
        return self.tasks.get(task_id)

    async def execute(self, request: AgentRequest) -> ArchitectResult:
        """Execute the full DAG synchronously for tests and workers."""

        state: dict[str, Any] = {
            "request": request,
            "phase": ArchitectPhase.PLAN,
            "iteration": 1,
        }
        max_iterations = 3

        try:
            while True:
                phase = state["phase"]
                if phase == ArchitectPhase.PLAN:
                    state.update(
                        await self._run_agent(AgentRole.PLANNER.value, state)
                    )
                    state["phase"] = ArchitectPhase.CODEGEN
                    continue

                if phase == ArchitectPhase.CODEGEN:
                    state.update(
                        await self._run_agent(AgentRole.CODEGEN.value, state)
                    )
                    state["phase"] = ArchitectPhase.CRITIC
                    continue

                if phase == ArchitectPhase.CRITIC:
                    state.update(
                        await self._run_agent(AgentRole.CRITIC.value, state)
                    )
                    critic_report = state["critic_report"]
                    if critic_report.passed:
                        state["phase"] = ArchitectPhase.SANDBOX
                    elif state["iteration"] < max_iterations:
                        state["iteration"] += 1
                        state["phase"] = ArchitectPhase.CODEGEN
                    else:
                        state["phase"] = ArchitectPhase.DEAD_LETTER
                    continue

                if phase == ArchitectPhase.SANDBOX:
                    with self.telemetry.span("sandbox", AgentRole.SANDBOX.value) as span:
                        sandbox_result = await self.sandbox.run(
                            request.project_id,
                            state["generated_config"],
                        )
                        span.set_delta(passed=sandbox_result.passed)
                    state["sandbox_result"] = sandbox_result
                    if sandbox_result.passed:
                        state["phase"] = ArchitectPhase.COMPLETE
                    elif state["iteration"] < max_iterations:
                        state["iteration"] += 1
                        state["repair_feedback"] = [
                            delta
                            for case in sandbox_result.cases
                            for delta in case.deltas
                        ]
                        state["phase"] = ArchitectPhase.CODEGEN
                    else:
                        state["phase"] = ArchitectPhase.DEAD_LETTER
                    continue

                if phase == ArchitectPhase.COMPLETE:
                    metrics = self.metrics.evaluate(
                        request.raw_spec,
                        state["generated_config"],
                        state["sandbox_result"],
                        state["iteration"],
                    )
                    return ArchitectResult(
                        project_id=request.project_id,
                        status=TaskStatus.SUCCEEDED,
                        plan=state.get("plan"),
                        generated_config=state.get("generated_config"),
                        critic_report=state.get("critic_report"),
                        sandbox_result=state.get("sandbox_result"),
                        metrics=metrics,
                        traces=list(self.telemetry.events),
                    )

                if phase == ArchitectPhase.DEAD_LETTER:
                    result = ArchitectResult(
                        project_id=request.project_id,
                        status=TaskStatus.DEAD_LETTERED,
                        plan=state.get("plan"),
                        generated_config=state.get("generated_config"),
                        critic_report=state.get("critic_report"),
                        sandbox_result=state.get("sandbox_result"),
                        traces=list(self.telemetry.events),
                        error="Architect workflow exhausted retry budget.",
                    )
                    self.dlq.append(result)
                    return result
        except Exception as error:
            result = ArchitectResult(
                project_id=request.project_id,
                status=TaskStatus.DEAD_LETTERED,
                traces=list(self.telemetry.events),
                error=str(error),
            )
            self.dlq.append(result)
            return result

    async def commit(self, task_id: str, project_id: str) -> CommitResult:
        """Commit a successful generated config to the live repository."""

        task = self.tasks.get(task_id)
        if task is None or task.result is None:
            raise ValueError("Task result is not available.")
        if task.result.status != TaskStatus.SUCCEEDED:
            raise ValueError("Only successful architect results can be committed.")
        config = task.result.generated_config
        if config is None:
            raise ValueError("Task has no generated config.")

        endpoint_id_by_key: dict[str, str] = {}
        committed_endpoints = 0
        committed_rules = 0
        for endpoint_config in config.endpoints:
            endpoint = endpoint_config.endpoint
            exists = await self.repository.endpoint_signature_exists(
                project_id,
                endpoint.method,
                endpoint.path,
            )
            if exists:
                continue
            result = await self.repository.create_endpoint(project_id, endpoint)
            endpoint_id_by_key[endpoint_config.key] = result.endpoint.id
            committed_endpoints += 1

        for rule_config in config.rules:
            endpoint_id = endpoint_id_by_key.get(rule_config.endpoint_key)
            if endpoint_id is None:
                continue
            await self.repository.create_rule(
                project_id,
                self._rule_with_endpoint_id(rule_config.rule, endpoint_id),
            )
            committed_rules += 1

        return CommitResult(
            task_id=task_id,
            project_id=project_id,
            committed_endpoints=committed_endpoints,
            committed_rules=committed_rules,
        )

    async def _run_task(self, task_id: str) -> None:
        task = self.tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now(timezone.utc)
        result = await self.execute(task.request)
        task.result = result
        task.status = result.status
        task.error = result.error
        task.updated_at = datetime.now(timezone.utc)

    async def _run_agent(self, role: str, state: dict[str, Any]) -> dict[str, Any]:
        agent = self.registry.get(role)
        with self.telemetry.span(role, agent.metadata.name) as span:
            delta = await agent.run(state)
            span.set_delta(**{key: self._summarize(value) for key, value in delta.items()})
            return delta

    @staticmethod
    def _summarize(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if hasattr(value, "model_dump"):
            return value.__class__.__name__
        if isinstance(value, list):
            return f"list[{len(value)}]"
        return value.__class__.__name__

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
