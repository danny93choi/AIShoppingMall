from pathlib import Path

import pytest

from commerce_agent.domain.scoring.config import ScoringConfig, load_scoring_config

CONFIG_PATH = Path(__file__).parents[3] / "assets" / "scoring" / "default" / "v1.json"


@pytest.fixture
def scoring_config() -> ScoringConfig:
    return load_scoring_config(CONFIG_PATH)
