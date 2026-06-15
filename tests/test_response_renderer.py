import json

from deo.models import IncomingRequestContext, SelectedResponse
from deo.response_renderer import ResponseRenderer, TEMPLATE_FUNCTIONS_REGISTRY


def test_response_renderer_substitutes_sources_and_functions(monkeypatch) -> None:
    monkeypatch.setitem(TEMPLATE_FUNCTIONS_REGISTRY, "now", lambda: "2026-06-15T00:00:00+00:00")
    monkeypatch.setitem(TEMPLATE_FUNCTIONS_REGISTRY, "uuid", lambda: "uuid-fixed")
    renderer = ResponseRenderer()
    request_ctx = IncomingRequestContext(
        method="POST",
        raw_path="/payments/pay_123",
        query_params={"status": "authorized"},
        body={"amount": 42, "currency": "USD"},
    )
    selected = SelectedResponse(
        status_code=200,
        body_template=(
            '{"id":"{{payment_id}}","status":"{{query.status}}",'
            '"amount":{{body.amount}},"now":"{{now}}","trace":"{{uuid}}"}'
        ),
        headers={
            "content-type": "application/json",
            "x-payment-id": "{{path.payment_id}}",
            "x-currency": "{{body.currency}}",
        },
    )

    final = renderer.render(selected, request_ctx, {"payment_id": "pay_123"})

    assert final.status_code == 200
    assert final.headers["x-payment-id"] == "pay_123"
    assert final.headers["x-currency"] == "USD"
    assert json.loads(final.body) == {
        "id": "pay_123",
        "status": "authorized",
        "amount": 42,
        "now": "2026-06-15T00:00:00+00:00",
        "trace": "uuid-fixed",
    }
