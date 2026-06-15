"""Dynamic agent registry for architect workflow components."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class AgentMetadata(BaseModel):
    """Registration metadata for one architect agent."""

    name: str
    role: str
    model_fallbacks: list[str] = Field(default_factory=list)
    prompt_variant: str = "default"
    temperature: float = 0
    capabilities: list[str] = Field(default_factory=list)


class BaseAgent(ABC):
    """Base class for dynamically registered agents."""

    metadata: AgentMetadata

    @abstractmethod
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent against workflow state and return a state delta."""


class AgentRegistry:
    """Central registry used by the DAG engine to resolve agents by role."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.metadata.role] = agent

    def get(self, role: str) -> BaseAgent:
        try:
            return self._agents[role]
        except KeyError as error:
            raise KeyError(f"No agent registered for role: {role}") from error

    def metadata(self) -> list[AgentMetadata]:
        return [agent.metadata for agent in self._agents.values()]
