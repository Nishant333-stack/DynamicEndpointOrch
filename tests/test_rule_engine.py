from deo.models import EndpointRule, IncomingRequestContext
from deo.rule_engine import RuleEngine


def test_rule_engine_returns_first_matching_rule_action() -> None:
    rules = [
        EndpointRule(
            id="rule_1",
            endpoint_id="endpoint_1",
            condition_type="query",
            field="status",
            operator="equals",
            value="failed",
            action="response_failed",
        ),
        EndpointRule(
            id="rule_2",
            endpoint_id="endpoint_1",
            condition_type="query",
            field="status",
            operator="exists",
            action="response_any_status",
        ),
    ]
    request_ctx = IncomingRequestContext(
        method="GET",
        raw_path="/payments/pay_123",
        query_params={"status": "failed"},
    )

    result = RuleEngine().evaluate(rules, request_ctx)

    assert result.matched_rule == rules[0]
    assert result.action == "response_failed"


def test_rule_engine_supports_body_numeric_and_header_regex() -> None:
    rules = [
        EndpointRule(
            id="rule_amount",
            endpoint_id="endpoint_1",
            condition_type="body",
            field="amount",
            operator="gt",
            value=100,
            action="response_large",
        ),
        EndpointRule(
            id="rule_header",
            endpoint_id="endpoint_1",
            condition_type="headers",
            field="x-request-id",
            operator="regex",
            value=r"^req_",
            action="response_request_id",
        ),
    ]
    request_ctx = IncomingRequestContext(
        method="POST",
        raw_path="/payouts",
        headers={"x-request-id": "req_123"},
        body={"amount": 50},
    )

    result = RuleEngine().evaluate(rules, request_ctx)

    assert result.matched_rule == rules[1]
    assert result.action == "response_request_id"


def test_rule_engine_returns_empty_result_when_no_rule_matches() -> None:
    rules = [
        EndpointRule(
            id="rule_1",
            endpoint_id="endpoint_1",
            condition_type="path",
            field="payment_id",
            operator="equals",
            value="pay_999",
            action="response_special",
        )
    ]
    request_ctx = IncomingRequestContext(method="GET", raw_path="/payments/pay_123")

    result = RuleEngine().evaluate(
        rules,
        request_ctx,
        path_params={"payment_id": "pay_123"},
    )

    assert result.matched_rule is None
    assert result.action is None
