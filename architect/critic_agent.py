"""Hybrid deterministic and semantic critic agent."""

from __future__ import annotations

from typing import Any

from architect.llm_client import JSONOnlyLLMClient
from architect.models import AgentRole, CriticIssue, CriticReport
from architect.registry import AgentMetadata, AgentRegistry, BaseAgent
from deo.delay_engine import DELAY_STRATEGY_REGISTRY
from deo.rule_engine import OPERATOR_REGISTRY


class CriticAgent(BaseAgent):
    """Validate generated configs before sandbox execution."""

    metadata = AgentMetadata(
        name="CriticAgent",
        role=AgentRole.CRITIC.value,
        model_fallbacks=["mockmesh-critic-primary"],
        prompt_variant="deterministic_then_semantic",
        temperature=0,
        capabilities=["integrity_validation", "semantic_review"],
    )

    def __init__(self, llm_client: JSONOnlyLLMClient) -> None:
        self.llm_client = llm_client

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        config = state["generated_config"]
        issues = self._deterministic_issues(config)
        if issues:
            return {
                "critic_report": CriticReport(passed=False, issues=issues),
                "repair_feedback": [issue.message for issue in issues],
            }

        semantic_notes: list[str] = []
        try:
            payload = await self.llm_client.complete_json(
                agent_name=self.metadata.name,
                prompt=f"Return semantic review JSON for config: {config.model_dump()}",
                schema_hint={"semantic_notes": ["string"], "passed": True},
            )
            semantic_notes = [
                str(note) for note in payload.get("semantic_notes", [])
            ]
            passed = bool(payload.get("passed", True))
        except Exception as error:
            semantic_notes = [f"Semantic review skipped: {error}"]
            passed = True

        return {
            "critic_report": CriticReport(
                passed=passed,
                issues=[],
                semantic_notes=semantic_notes,
            )
        }

    def _deterministic_issues(self, config: Any) -> list[CriticIssue]:
        issues: list[CriticIssue] = []
        endpoint_keys = {endpoint.key for endpoint in config.endpoints}
        signatures: set[tuple[str, str]] = set()
        for endpoint_config in config.endpoints:
            endpoint = endpoint_config.endpoint
            signature = (endpoint.method, endpoint.path)
            if signature in signatures:
                issues.append(
                    CriticIssue(
                        severity="error",
                        message=f"Duplicate endpoint signature {endpoint.method} {endpoint.path}",
                        location=f"endpoints.{endpoint_config.key}",
                    )
                )
            signatures.add(signature)
            if endpoint.delay_ms and endpoint.delay_mode not in DELAY_STRATEGY_REGISTRY:
                issues.append(
                    CriticIssue(
                        severity="error",
                        message=f"Unsupported delay mode {endpoint.delay_mode}",
                        location=f"endpoints.{endpoint_config.key}.delay_mode",
                    )
                )

        for rule_config in config.rules:
            if rule_config.endpoint_key not in endpoint_keys:
                issues.append(
                    CriticIssue(
                        severity="error",
                        message=f"Rule references unknown endpoint key {rule_config.endpoint_key}",
                        location="rules.endpoint_key",
                    )
                )
            if rule_config.rule.operator not in OPERATOR_REGISTRY:
                issues.append(
                    CriticIssue(
                        severity="error",
                        message=f"Unsupported operator {rule_config.rule.operator}",
                        location="rules.operator",
                    )
                )
        return issues


def register_agents(registry: AgentRegistry, llm_client: JSONOnlyLLMClient) -> None:
    registry.register(CriticAgent(llm_client))
