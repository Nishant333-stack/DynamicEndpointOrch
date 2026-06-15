import asyncio

import httpx
from fastapi import FastAPI

from architect.app import create_app as create_architect_app
from architect.critic_agent import CriticAgent
from architect.llm_client import JSONOnlyLLMClient
from architect.models import AgentRequest, GeneratedConfig, GeneratedEndpointConfig, GeneratedRuleConfig, TaskStatus
from architect.orchestrator import ArchitectOrchestrator
from architect.router import build_architect_router
from deo.models import EndpointCreateRequest, RuleCreateRequest
from deo.repository import InMemoryEndpointRepository


def test_architect_execute_generates_and_sandboxes_without_live_llm() -> None:
    async def scenario() -> None:
        repository = InMemoryEndpointRepository()
        orchestrator = ArchitectOrchestrator(repository)

        result = await orchestrator.execute(
            AgentRequest(
                project_id="demo",
                raw_spec="Build GET /widgets/{widget_id} status 200",
            )
        )

        assert result.status == TaskStatus.SUCCEEDED
        assert result.plan is not None
        assert result.generated_config is not None
        assert result.critic_report is not None
        assert result.critic_report.passed is True
        assert result.sandbox_result is not None
        assert result.sandbox_result.passed is True
        assert result.metrics is not None
        assert result.metrics.simulation_pass_rate == 1
        assert any(trace.agent == "PlannerAgent" for trace in result.traces)

    asyncio.run(scenario())


def test_critic_rejects_invalid_operator_and_delay_mode() -> None:
    async def scenario() -> None:
        critic = CriticAgent(JSONOnlyLLMClient())
        config = GeneratedConfig(
            endpoints=[
                GeneratedEndpointConfig(
                    key="payments",
                    endpoint=EndpointCreateRequest.model_construct(
                        name="Payment lookup",
                        path="/payments/{payment_id}",
                        method="GET",
                        is_active=True,
                        status_code=200,
                        body_template='{"ok":true}',
                        headers={"content-type": "application/json"},
                        delay_ms=1,
                        delay_mode="unsupported",
                    ),
                )
            ],
            rules=[
                GeneratedRuleConfig(
                    endpoint_key="payments",
                    rule=RuleCreateRequest.model_construct(
                        endpoint_id="payments",
                        condition_type="query",
                        field="status",
                        operator="bad_operator",
                        value="failed",
                        status_code=402,
                        body_template='{"failed":true}',
                    ),
                )
            ],
        )

        delta = await critic.run({"generated_config": config})

        report = delta["critic_report"]
        assert report.passed is False
        messages = [issue.message for issue in report.issues]
        assert any("Unsupported delay mode" in message for message in messages)
        assert any("Unsupported operator" in message for message in messages)

    asyncio.run(scenario())


def test_architect_router_queues_polls_and_commits() -> None:
    async def scenario() -> None:
        repository = InMemoryEndpointRepository()
        orchestrator = ArchitectOrchestrator(repository)
        app = FastAPI()
        app.include_router(build_architect_router(orchestrator))
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            generate_response = await client.post(
                "/architect/generate",
                json={
                    "project_id": "demo",
                    "raw_spec": "Create GET /architect-items/{item_id} status 200",
                },
            )
            assert generate_response.status_code == 202
            task_id = generate_response.json()["task_id"]

            task_payload = None
            for _ in range(20):
                task_response = await client.get(f"/architect/tasks/{task_id}")
                assert task_response.status_code == 200
                task_payload = task_response.json()
                if task_payload["status"] == TaskStatus.SUCCEEDED:
                    break
                await asyncio.sleep(0.01)

            assert task_payload is not None
            assert task_payload["status"] == TaskStatus.SUCCEEDED
            assert task_payload["result"]["metrics"]["simulation_pass_rate"] == 1

            commit_response = await client.post(
                "/architect/commit",
                json={"task_id": task_id, "project_id": "demo"},
            )
            assert commit_response.status_code == 200

        assert await repository.endpoint_signature_exists(
            "demo",
            "GET",
            "/architect-items/{item_id}",
        )

    asyncio.run(scenario())


def test_architect_router_enforces_project_rbac() -> None:
    async def scenario() -> None:
        repository = InMemoryEndpointRepository()
        orchestrator = ArchitectOrchestrator(repository)
        app = FastAPI()
        app.include_router(build_architect_router(orchestrator))
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/architect/generate",
                headers={"authorization": "Bearer dev-admin"},
                json={
                    "project_id": "other-project",
                    "raw_spec": "Create GET /blocked status 200",
                },
            )

        assert response.status_code == 403

    asyncio.run(scenario())


def test_standalone_architect_app_serves_deo_and_architect_routes() -> None:
    async def scenario() -> None:
        app = create_architect_app(InMemoryEndpointRepository())
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            dashboard_response = await client.get("/dashboard")
            architect_response = await client.post(
                "/architect/generate",
                json={
                    "project_id": "demo",
                    "raw_spec": "Create GET /combined/{id} status 200",
                },
            )

        assert dashboard_response.status_code == 200
        assert architect_response.status_code == 202

    asyncio.run(scenario())
