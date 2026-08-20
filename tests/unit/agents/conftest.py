from pathlib import Path

import pytest

from commerce_agent.application.agents.prompts import PromptRegistry


@pytest.fixture
def prompt_registry(tmp_path: Path) -> PromptRegistry:
    prompt = tmp_path / "test" / "analyze" / "v1.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text(
        "## System\nUse only supplied facts.\n\n## User\nAnalyze {candidate_json}\n",
        encoding="utf-8",
    )
    return PromptRegistry(tmp_path)
