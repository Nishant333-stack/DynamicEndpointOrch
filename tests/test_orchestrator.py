import asyncio
import json
from time import perf_counter

import httpx

from deo.models import IncomingRequestContext
from deo.orchestrator import DEOOrchestrator
from deo.repository import InMemoryEndpointRepository
from deo.router import create_app


def test_orchestrator_returns_conditional_rendered_response() -> None:
    async def scenario() -> None:
        repository = InMemoryEndpointRepository()
        orchestrator = DEOOrchestrator(repository)
        request_ctx = IncomingRequestContext(
            method="GET",
            raw_path="/payments/pay_123",
            query_params={"status": "failed", "reason": "insufficient_funds"},
            headers={"accept": "application/json"},
        )

        final, log_entry = await orchestrator.resolve("demo", request_ctx)

        assert final.status_code == 402
        assert final.headers["x-mockmesh-endpoint"] == "pay_123"
        assert json.loads(final.body) == {
            "payment_id": "pay_123",
            "status": "failed",
            "reason": "insufficient_funds",
        }
        assert log_entry.endpoint_id == "endpoint_payment_lookup"
        assert log_entry.response_code == 402
        assert log_entry.response_time_ms >= 0

    asyncio.run(scenario())


def test_orchestrator_applies_delay_and_renders_body_values() -> None:
    async def scenario() -> None:
        repository = InMemoryEndpointRepository()
        orchestrator = DEOOrchestrator(repository)
        request_ctx = IncomingRequestContext(
            method="POST",
            raw_path="/payouts",
            headers={"content-type": "application/json"},
            body={"amount": 25, "currency": "USD"},
        )

        final, log_entry = await orchestrator.resolve("demo", request_ctx)

        assert final.status_code == 202
        assert final.headers["x-mockmesh-delay"] == "fixed"
        body = json.loads(final.body)
        assert body["state"] == "queued"
        assert body["amount"] == 25
        assert body["currency"] == "USD"
        assert body["payout_id"]
        assert log_entry.endpoint_id == "endpoint_payout_create"
        assert log_entry.response_time_ms >= 15

    asyncio.run(scenario())


def test_fastapi_catch_all_route_resolves_and_logs_request() -> None:
    async def scenario() -> None:
        repository = InMemoryEndpointRepository()
        app = create_app(repository)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            started_at = perf_counter()
            response = await client.post(
                "/mock/demo/payouts",
                json={"amount": 99, "currency": "EUR"},
            )
            elapsed_ms = (perf_counter() - started_at) * 1000

        assert response.status_code == 202
        assert response.headers["x-mockmesh-delay"] == "fixed"
        assert response.json()["amount"] == 99
        assert response.json()["currency"] == "EUR"
        assert elapsed_ms >= 15
        assert len(repository.request_logs) == 1
        assert repository.request_logs[0].path == "/payouts"
        assert repository.request_logs[0].response_code == 202

    asyncio.run(scenario())


def test_dashboard_page_and_assets_are_served() -> None:
    async def scenario() -> None:
        repository = InMemoryEndpointRepository()
        app = create_app(repository)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            page_response = await client.get("/dashboard")
            css_response = await client.get("/dashboard/assets/dashboard.css")
            relative_css_response = await client.get("/dashboard.css")
            js_response = await client.get("/dashboard/assets/dashboard.js")
            relative_js_response = await client.get("/dashboard.js")

        assert page_response.status_code == 200
        assert "MockMesh DEO Dashboard" in page_response.text
        assert 'href="./dashboard.css"' in page_response.text
        assert 'src="./dashboard.js"' in page_response.text
        assert css_response.status_code == 200
        assert "text/css" in css_response.headers["content-type"]
        assert relative_css_response.status_code == 200
        assert js_response.status_code == 200
        assert "application/javascript" in js_response.headers["content-type"]
        assert relative_js_response.status_code == 200

    asyncio.run(scenario())


def test_dashboard_api_creates_and_checks_dynamic_endpoint() -> None:
    async def scenario() -> None:
        repository = InMemoryEndpointRepository()
        app = create_app(repository)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            create_response = await client.post(
                "/api/projects/demo/endpoints",
                json={
                    "name": "Refund lookup",
                    "method": "GET",
                    "path": "/refunds/{refund_id}",
                    "status_code": 200,
                    "body_template": (
                        '{"refund_id":"{{refund_id}}","trace_id":"{{uuid}}"}'
                    ),
                    "headers": {"content-type": "application/json"},
                    "is_active": True,
                },
            )
            check_response = await client.post(
                "/api/projects/demo/endpoints/check",
                json={"method": "GET", "path": "/refunds/ref_123"},
            )
            delayed_check_response = await client.post(
                "/api/projects/demo/endpoints/check",
                json={"method": "POST", "path": "/payouts"},
            )
            mock_response = await client.get("/mock/demo/refunds/ref_123")
            inventory_response = await client.get("/api/projects/demo/endpoints")

        assert create_response.status_code == 201
        assert create_response.json()["endpoint"]["path"] == "/refunds/{refund_id}"
        assert check_response.status_code == 200
        check_payload = check_response.json()
        assert check_payload["exists"] is True
        assert check_payload["endpoint"]["name"] == "Refund lookup"
        assert check_payload["path_params"] == {"refund_id": "ref_123"}
        delayed_check_payload = delayed_check_response.json()
        assert delayed_check_payload["exists"] is True
        assert delayed_check_payload["delay_ms"] == 20
        assert delayed_check_payload["delay_mode"] == "fixed"
        assert mock_response.status_code == 200
        assert mock_response.json()["refund_id"] == "ref_123"
        assert any(
            endpoint["path"] == "/refunds/{refund_id}"
            for endpoint in inventory_response.json()["endpoints"]
        )

    asyncio.run(scenario())


def test_dashboard_rules_api_creates_conditional_response() -> None:
    async def scenario() -> None:
        repository = InMemoryEndpointRepository()
        app = create_app(repository)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            endpoints_response = await client.get("/api/projects/demo/endpoints")
            payment_endpoint = next(
                endpoint
                for endpoint in endpoints_response.json()["endpoints"]
                if endpoint["path"] == "/payments/{payment_id}"
            )
            create_rule_response = await client.post(
                "/api/projects/demo/rules",
                json={
                    "endpoint_id": payment_endpoint["id"],
                    "condition_type": "query",
                    "field": "mode",
                    "operator": "equals",
                    "value": "review",
                    "status_code": 409,
                    "body_template": '{"payment_id":"{{payment_id}}","mode":"review"}',
                    "headers": {"content-type": "application/json"},
                },
            )
            rules_response = await client.get("/api/projects/demo/rules")
            mock_response = await client.get(
                "/mock/demo/payments/pay_777",
                params={"mode": "review"},
            )

        assert create_rule_response.status_code == 201
        assert create_rule_response.json()["rule"]["field"] == "mode"
        assert any(rule["field"] == "mode" for rule in rules_response.json()["rules"])
        assert mock_response.status_code == 409
        assert mock_response.json() == {"payment_id": "pay_777", "mode": "review"}

    asyncio.run(scenario())


def test_dashboard_logs_api_returns_mock_request_logs() -> None:
    async def scenario() -> None:
        repository = InMemoryEndpointRepository()
        app = create_app(repository)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            await client.get("/mock/demo/health")
            logs_response = await client.get("/api/projects/demo/logs")

        assert logs_response.status_code == 200
        logs = logs_response.json()["logs"]
        assert len(logs) == 1
        assert logs[0]["path"] == "/health"
        assert logs[0]["endpoint_name"] == "Health check"
        assert logs[0]["response_code"] == 200

    asyncio.run(scenario())


def test_orchestrator_returns_404_for_unmatched_endpoint() -> None:
    async def scenario() -> None:
        repository = InMemoryEndpointRepository()
        orchestrator = DEOOrchestrator(repository)
        request_ctx = IncomingRequestContext(method="GET", raw_path="/missing")

        final, log_entry = await orchestrator.resolve("demo", request_ctx)

        assert final.status_code == 404
        assert json.loads(final.body) == {"error": "endpoint_not_found"}
        assert log_entry.endpoint_id is None
        assert log_entry.response_code == 404

    asyncio.run(scenario())
