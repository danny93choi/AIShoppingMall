from pathlib import Path

import pytest

from commerce_agent.application.agents.prompts import PromptRegistry


def test_registry_loads_versions_and_stable_hash(prompt_registry: PromptRegistry) -> None:
    first = prompt_registry.load("test/analyze", "v1")
    second = prompt_registry.load("test/analyze", "v1")

    assert first.content_hash == second.content_hash
    assert first.render({"candidate_json": "{}"})[1] == "Analyze {}"


def test_registry_rejects_missing_values(prompt_registry: PromptRegistry) -> None:
    prompt = prompt_registry.load("test/analyze", "v1")
    with pytest.raises(ValueError, match="candidate_json"):
        prompt.render({})


def test_registry_rejects_path_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes"):
        PromptRegistry(tmp_path).load("../secret", "v1")
