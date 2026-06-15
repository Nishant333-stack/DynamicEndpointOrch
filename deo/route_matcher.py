"""Route matching stage for MockMesh DEO.

``RouteMatcher`` compares the incoming method and path against active endpoint
definitions. Endpoint paths may contain ``{param}`` segments, which are
extracted into ``MatchedEndpoint.path_params`` for later rules and rendering.
"""

from __future__ import annotations

from urllib.parse import unquote

from deo.models import Endpoint, IncomingRequestContext, MatchedEndpoint


class RouteMatcher:
    """Match HTTP requests to active endpoint definitions."""

    def match(
        self,
        endpoints: list[Endpoint],
        request_ctx: IncomingRequestContext,
    ) -> MatchedEndpoint | None:
        """Return the best endpoint match for method and path, or ``None``."""

        request_method = request_ctx.method.upper()
        request_segments = self._split_path(request_ctx.raw_path)
        matches: list[tuple[int, MatchedEndpoint]] = []

        for endpoint in endpoints:
            if not endpoint.is_active or endpoint.method.upper() != request_method:
                continue

            endpoint_segments = self._split_path(endpoint.path)
            path_params = self._match_segments(endpoint_segments, request_segments)
            if path_params is None:
                continue

            static_count = sum(
                1
                for segment in endpoint_segments
                if not (segment.startswith("{") and segment.endswith("}"))
            )
            matches.append(
                (static_count, MatchedEndpoint(endpoint=endpoint, path_params=path_params))
            )

        if not matches:
            return None
        return max(matches, key=lambda item: item[0])[1]

    @staticmethod
    def _split_path(path: str) -> list[str]:
        path_without_query = path.split("?", 1)[0]
        return [
            unquote(segment)
            for segment in path_without_query.strip("/").split("/")
            if segment
        ]

    @staticmethod
    def _match_segments(
        endpoint_segments: list[str],
        request_segments: list[str],
    ) -> dict[str, str] | None:
        if len(endpoint_segments) != len(request_segments):
            return None

        path_params: dict[str, str] = {}
        for endpoint_segment, request_segment in zip(endpoint_segments, request_segments):
            if endpoint_segment.startswith("{") and endpoint_segment.endswith("}"):
                param_name = endpoint_segment[1:-1].strip()
                if not param_name:
                    return None
                path_params[param_name] = request_segment
                continue
            if endpoint_segment != request_segment:
                return None

        return path_params
