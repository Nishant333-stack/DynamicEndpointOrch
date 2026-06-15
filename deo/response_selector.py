"""Response selection stage for MockMesh DEO.

``ResponseSelector`` uses the rule action as a response identifier. When no
rule action is present, it chooses the endpoint's default response. If neither
is available, it returns a deterministic 501 placeholder response.
"""

from __future__ import annotations

from deo.models import SelectedResponse
from deo.repository import EndpointRepository


class ResponseSelector:
    """Select the mock response definition and configured headers."""

    def __init__(self, repository: EndpointRepository) -> None:
        self.repository = repository

    async def select(
        self,
        endpoint_id: str,
        action: str | None,
    ) -> SelectedResponse:
        """Select a response by rule action, default flag, or 501 fallback."""

        responses = await self.repository.get_responses(endpoint_id)
        selected = None

        if action is not None:
            selected = next((response for response in responses if response.id == action), None)

        if selected is None:
            selected = next((response for response in responses if response.is_default), None)

        if selected is None:
            return SelectedResponse(
                status_code=501,
                body_template='{"error":"response_not_configured"}',
                headers={"content-type": "application/json"},
            )

        response_headers = await self.repository.get_response_headers(selected.id)
        return SelectedResponse(
            status_code=selected.status_code,
            body_template=selected.body_template,
            headers={header.key: header.value for header in response_headers},
        )
