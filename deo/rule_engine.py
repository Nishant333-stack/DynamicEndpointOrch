"""Rule evaluation stage for MockMesh DEO.

Rules are evaluated in repository order. ``OPERATOR_REGISTRY`` maps operator
names to small predicate functions, making the engine easy to extend without
changing the evaluation loop.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from deo.models import EndpointRule, IncomingRequestContext, RuleEvaluationResult

Operator = Callable[[Any, Any], bool]


def _equals(actual: Any, expected: Any) -> bool:
    return actual == expected


def _not_equals(actual: Any, expected: Any) -> bool:
    return actual != expected


def _contains(actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    if isinstance(actual, Mapping):
        return expected in actual
    if isinstance(actual, str):
        return str(expected) in actual
    if isinstance(actual, Sequence) and not isinstance(actual, (str, bytes, bytearray)):
        return expected in actual
    return False


def _exists(actual: Any, expected: Any) -> bool:
    return actual is not None


def _gt(actual: Any, expected: Any) -> bool:
    try:
        return float(actual) > float(expected)
    except (TypeError, ValueError):
        return False


def _lt(actual: Any, expected: Any) -> bool:
    try:
        return float(actual) < float(expected)
    except (TypeError, ValueError):
        return False


def _regex(actual: Any, expected: Any) -> bool:
    if actual is None or expected is None:
        return False
    return re.search(str(expected), str(actual)) is not None


OPERATOR_REGISTRY: dict[str, Operator] = {
    "equals": _equals,
    "not_equals": _not_equals,
    "contains": _contains,
    "exists": _exists,
    "gt": _gt,
    "lt": _lt,
    "regex": _regex,
}
"""Registry of supported rule operators.

Each operator receives the extracted request value and the rule's configured
value. It returns ``True`` when the rule should match.
"""


class RuleEngine:
    """Evaluate endpoint rules against an incoming request."""

    def __init__(self, operator_registry: dict[str, Operator] | None = None) -> None:
        self.operator_registry = operator_registry or OPERATOR_REGISTRY

    def evaluate(
        self,
        rules: list[EndpointRule],
        request_ctx: IncomingRequestContext,
        path_params: dict[str, str] | None = None,
    ) -> RuleEvaluationResult:
        """Evaluate rules in order and return the first matching action."""

        for rule in rules:
            operator = self.operator_registry.get(rule.operator)
            if operator is None:
                continue

            actual = self._extract_value(rule, request_ctx, path_params or {})
            if operator(actual, rule.value):
                return RuleEvaluationResult(matched_rule=rule, action=rule.action)

        return RuleEvaluationResult()

    def _extract_value(
        self,
        rule: EndpointRule,
        request_ctx: IncomingRequestContext,
        path_params: dict[str, str],
    ) -> Any:
        condition_type = rule.condition_type.lower()
        field = rule.field

        if condition_type in {"query", "query_params"}:
            return self._lookup_dotted(request_ctx.query_params, field)
        if condition_type in {"header", "headers"}:
            lowered_headers = {
                key.lower(): value for key, value in request_ctx.headers.items()
            }
            return self._lookup_dotted(lowered_headers, field.lower())
        if condition_type in {"body", "json"}:
            return self._lookup_dotted(request_ctx.body, field)
        if condition_type in {"path", "path_params"}:
            return self._lookup_dotted(path_params, field)
        if condition_type == "request":
            request_data = {
                "method": request_ctx.method,
                "raw_path": request_ctx.raw_path,
                "query": request_ctx.query_params,
                "headers": request_ctx.headers,
                "body": request_ctx.body,
                "path": path_params,
            }
            return self._lookup_dotted(request_data, field)

        return None

    def _lookup_dotted(self, source: Any, field: str) -> Any:
        current = source
        for part in field.split("."):
            if current is None:
                return None
            current = self._lookup_part(current, part)
        return current

    @staticmethod
    def _lookup_part(source: Any, part: str) -> Any:
        if isinstance(source, Mapping):
            return source.get(part)
        if isinstance(source, BaseModel):
            return getattr(source, part, None)
        if isinstance(source, Sequence) and not isinstance(source, (str, bytes, bytearray)):
            try:
                return source[int(part)]
            except (ValueError, IndexError):
                return None
        return getattr(source, part, None)
