"""CodeGen agent that converts plans into DEO repository create contracts."""

from __future__ import annotations

from typing import Any

from architect.llm_client import JSONOnlyLLMClient
from architect.models import (
    AgentRole,
    GeneratedConfig,
    GeneratedEndpointConfig,
    GeneratedRuleConfig,
)
from architect.registry import AgentMetadata, AgentRegistry, BaseAgent
from deo.models import EndpointCreateRequest, RuleCreateRequest


class CodeGenAgent(BaseAgent):
    """Generate Pydantic-valid MockMesh endpoint and rule configs."""

    metadata = AgentMetadata(
        name="CodeGenAgent",
        role=AgentRole.CODEGEN.value,
        model_fallbacks=["mockmesh-codegen-primary", "mockmesh-codegen-repair"],
        prompt_variant="schema_repairable",
        temperature=0,
        capabilities=["config_generation", "schema_repair"],
    )

    def __init__(self, llm_client: JSONOnlyLLMClient) -> None:
        self.llm_client = llm_client

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        plan = state["plan"]
        repair_feedback = state.get("repair_feedback", [])
        try:
            payload = await self.llm_client.complete_json(
                agent_name=self.metadata.name,
                prompt=(
                    "Return JSON matching GeneratedConfig. "
                    f"Plan: {plan.model_dump()} Feedback: {repair_feedback}"
                ),
                schema_hint=GeneratedConfig.model_json_schema(),
            )
            config = GeneratedConfig.model_validate(payload)
        except Exception as error:
            config = self._fallback_codegen(plan)
            return {"generated_config": config, "codegen_fallback": str(error)}
        return {"generated_config": config}

    def _fallback_codegen(self, plan: Any) -> GeneratedConfig:
        endpoints = [
            GeneratedEndpointConfig(
                key=endpoint.key,
                endpoint=EndpointCreateRequest(
                    name=endpoint.name,
                    path=endpoint.path,
                    method=endpoint.method,
                    status_code=endpoint.default_status_code,
                    body_template=endpoint.body_template,
                    delay_ms=endpoint.delay_ms,
                    delay_mode=endpoint.delay_mode,
                ),
            )
            for endpoint in plan.endpoints
        ]
        rules = [
            GeneratedRuleConfig(
                endpoint_key=rule.endpoint_key,
                rule=RuleCreateRequest(
                    endpoint_id=rule.endpoint_key,
                    condition_type=rule.condition_type,
                    field=rule.field,
                    operator=rule.operator,
                    value=rule.value,
                    status_code=rule.status_code,
                    body_template=rule.body_template,
                ),
            )
            for rule in plan.rules
        ]
        return GeneratedConfig(
            endpoints=endpoints,
            rules=rules,
            scenarios=plan.scenarios,
        )


def register_agents(registry: AgentRegistry, llm_client: JSONOnlyLLMClient) -> None:
    registry.register(CodeGenAgent(llm_client))
