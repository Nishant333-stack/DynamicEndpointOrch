"""Canonical schema registry used for local RAG-style prompt injection."""

from __future__ import annotations

from architect.models import CanonicalContext


class CanonicalContextRegistry:
    """Local canonical context store.

    This deliberately avoids external vector services while preserving the
    architecture seam for RAG-style retrieval and prompt injection.
    """

    def __init__(self) -> None:
        self._contexts: dict[str, CanonicalContext] = {
            "default": CanonicalContext(
                project_id="default",
                naming_standards=[
                    "Use plural resource nouns in paths.",
                    "Use snake_case JSON fields for payment payloads.",
                    "Prefer {resource_id} path parameters.",
                ],
                standard_objects={
                    "error": {"error": "string", "trace_id": "{{uuid}}"},
                    "success": {"ok": True, "trace_id": "{{uuid}}"},
                },
                previous_patterns=[
                    "GET /payments/{payment_id}",
                    "POST /payouts",
                    "GET /health",
                ],
            )
        }

    def set_context(self, context: CanonicalContext) -> None:
        self._contexts[context.project_id] = context

    def query(self, project_id: str, raw_spec: str) -> CanonicalContext:
        project_context = self._contexts.get(project_id)
        default_context = self._contexts["default"]
        if project_context is None:
            return default_context.model_copy(update={"project_id": project_id})

        terms = raw_spec.lower().split()
        matching_patterns = [
            pattern
            for pattern in project_context.previous_patterns
            if any(term.strip("/{}") in pattern.lower() for term in terms)
        ]
        return project_context.model_copy(
            update={
                "previous_patterns": matching_patterns
                or project_context.previous_patterns,
            }
        )
