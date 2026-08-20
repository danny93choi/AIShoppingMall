import pytest

from commerce_agent.application.agents.allowlist import (
    SideEffectLevel,
    ToolAllowlist,
    ToolNotAllowedError,
    ToolPolicy,
    allowlist_for_agent,
)


def test_allowlist_rejects_unknown_tool() -> None:
    allowlist = ToolAllowlist([])
    with pytest.raises(ToolNotAllowedError, match="not allowlisted"):
        allowlist.require("web_search")


def test_external_mutation_requires_approval() -> None:
    policy = ToolPolicy("create_draft", "v1", False, SideEffectLevel.EXTERNAL_MUTATION, 5, 1000)
    allowlist = ToolAllowlist([policy])
    with pytest.raises(ToolNotAllowedError, match="approval"):
        allowlist.require("create_draft")
    assert allowlist.require("create_draft", approval_granted=True) == policy


def test_each_specialist_has_a_separate_allowlist() -> None:
    market_policy = allowlist_for_agent("market_analyst").require("observation_lookup")
    assert market_policy.read_only
    with pytest.raises(ToolNotAllowedError):
        allowlist_for_agent("categorizer").require("observation_lookup")
