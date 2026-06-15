from deo.models import Endpoint, IncomingRequestContext
from deo.route_matcher import RouteMatcher


def test_route_matcher_extracts_path_params() -> None:
    matcher = RouteMatcher()
    endpoints = [
        Endpoint(
            id="endpoint_1",
            project_id="demo",
            name="Payment lookup",
            path="/payments/{payment_id}",
            method="GET",
            is_active=True,
        )
    ]
    request_ctx = IncomingRequestContext(method="GET", raw_path="/payments/pay_123")

    matched = matcher.match(endpoints, request_ctx)

    assert matched is not None
    assert matched.endpoint.id == "endpoint_1"
    assert matched.path_params == {"payment_id": "pay_123"}


def test_route_matcher_returns_none_for_method_mismatch() -> None:
    matcher = RouteMatcher()
    endpoints = [
        Endpoint(
            id="endpoint_1",
            project_id="demo",
            name="Payment lookup",
            path="/payments/{payment_id}",
            method="POST",
            is_active=True,
        )
    ]
    request_ctx = IncomingRequestContext(method="GET", raw_path="/payments/pay_123")

    assert matcher.match(endpoints, request_ctx) is None


def test_route_matcher_prefers_more_static_route() -> None:
    matcher = RouteMatcher()
    endpoints = [
        Endpoint(
            id="endpoint_dynamic",
            project_id="demo",
            name="Dynamic",
            path="/payments/{payment_id}",
            method="GET",
            is_active=True,
        ),
        Endpoint(
            id="endpoint_static",
            project_id="demo",
            name="Static",
            path="/payments/search",
            method="GET",
            is_active=True,
        ),
    ]
    request_ctx = IncomingRequestContext(method="GET", raw_path="/payments/search")

    matched = matcher.match(endpoints, request_ctx)

    assert matched is not None
    assert matched.endpoint.id == "endpoint_static"
