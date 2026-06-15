"""Template rendering stage for MockMesh DEO.

``ResponseRenderer`` replaces ``{{placeholder}}`` tokens in response bodies and
headers using path params, query params, request body values, and built-in
template functions. ``TEMPLATE_FUNCTIONS_REGISTRY`` exposes built-ins such as
``now`` and ``uuid``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from deo.models import FinalResponse, IncomingRequestContext, SelectedResponse

TemplateFunction = Callable[[], str]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid4())


TEMPLATE_FUNCTIONS_REGISTRY: dict[str, TemplateFunction] = {
    "now": _now,
    "uuid": _uuid,
}
"""Registry of zero-argument template functions available to placeholders."""


class ResponseRenderer:
    """Render selected response templates into final HTTP response data."""

    _placeholder_pattern = re.compile(r"{{\s*([^{}]+?)\s*}}")

    def __init__(
        self,
        template_functions_registry: dict[str, TemplateFunction] | None = None,
    ) -> None:
        self.template_functions_registry = (
            template_functions_registry or TEMPLATE_FUNCTIONS_REGISTRY
        )

    def render(
        self,
        selected_response: SelectedResponse,
        request_ctx: IncomingRequestContext,
        path_params: dict[str, str] | None = None,
    ) -> FinalResponse:
        """Render body and headers from request data and built-in functions."""

        rendered_headers = {
            key: self._render_template(value, request_ctx, path_params or {})
            for key, value in selected_response.headers.items()
        }
        rendered_body = self._render_template(
            selected_response.body_template,
            request_ctx,
            path_params or {},
        )
        return FinalResponse(
            status_code=selected_response.status_code,
            headers=rendered_headers,
            body=rendered_body,
        )

    def _render_template(
        self,
        template: str,
        request_ctx: IncomingRequestContext,
        path_params: dict[str, str],
    ) -> str:
        def replace(match: re.Match[str]) -> str:
            placeholder = match.group(1).strip()
            value = self._resolve_placeholder(placeholder, request_ctx, path_params)
            return "" if value is None else str(value)

        return self._placeholder_pattern.sub(replace, template)

    def _resolve_placeholder(
        self,
        placeholder: str,
        request_ctx: IncomingRequestContext,
        path_params: dict[str, str],
    ) -> Any:
        if placeholder in self.template_functions_registry:
            return self.template_functions_registry[placeholder]()

        if placeholder.startswith("path."):
            return self._lookup_dotted(path_params, placeholder.removeprefix("path."))
        if placeholder.startswith("path_params."):
            return self._lookup_dotted(
                path_params,
                placeholder.removeprefix("path_params."),
            )
        if placeholder.startswith("query."):
            return self._lookup_dotted(
                request_ctx.query_params,
                placeholder.removeprefix("query."),
            )
        if placeholder.startswith("query_params."):
            return self._lookup_dotted(
                request_ctx.query_params,
                placeholder.removeprefix("query_params."),
            )
        if placeholder.startswith("body."):
            return self._lookup_dotted(request_ctx.body, placeholder.removeprefix("body."))

        for source in (path_params, request_ctx.query_params, request_ctx.body):
            value = self._lookup_dotted(source, placeholder)
            if value is not None:
                return value
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
