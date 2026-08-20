from dataclasses import dataclass
from enum import StrEnum


class SideEffectLevel(StrEnum):
    NONE = "none"
    DRAFT_ONLY = "draft_only"
    EXTERNAL_MUTATION = "external_mutation"


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    name: str
    version: str
    read_only: bool
    side_effect_level: SideEffectLevel
    timeout_seconds: float
    max_result_size: int


class ToolNotAllowedError(PermissionError):
    pass


class ToolAllowlist:
    def __init__(self, policies: list[ToolPolicy]) -> None:
        self._policies = {policy.name: policy for policy in policies}

    def require(self, tool_name: str, *, approval_granted: bool = False) -> ToolPolicy:
        policy = self._policies.get(tool_name)
        if policy is None:
            raise ToolNotAllowedError(f"tool is not allowlisted: {tool_name}")
        if policy.side_effect_level is SideEffectLevel.EXTERNAL_MUTATION and not approval_granted:
            raise ToolNotAllowedError(f"approval is required for tool: {tool_name}")
        return policy


SPECIALIST_TOOL_POLICIES: dict[str, list[ToolPolicy]] = {
    "categorizer": [],
    "market_analyst": [
        ToolPolicy("observation_lookup", "v1", True, SideEffectLevel.NONE, 5, 100_000)
    ],
    "sourcing": [ToolPolicy("supplier_lookup", "v1", True, SideEffectLevel.NONE, 10, 100_000)],
    "shop_fit": [
        ToolPolicy("shop_aggregate_profile", "v1", True, SideEffectLevel.NONE, 5, 100_000)
    ],
}


def allowlist_for_agent(agent_name: str) -> ToolAllowlist:
    try:
        return ToolAllowlist(SPECIALIST_TOOL_POLICIES[agent_name])
    except KeyError as error:
        raise ValueError(f"unknown specialist agent: {agent_name}") from error
