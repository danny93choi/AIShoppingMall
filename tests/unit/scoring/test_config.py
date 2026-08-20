from decimal import Decimal

import pytest
from pydantic import ValidationError

from commerce_agent.domain.scoring.config import (
    MarginScorePoint,
    ScoreWeights,
    ScoringConfig,
)


def test_default_config_is_versioned(scoring_config: ScoringConfig) -> None:
    assert scoring_config.version == "1.0.0"
    assert sum(scoring_config.weights.model_dump().values(), Decimal("0")) == Decimal("1")


def test_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError, match="sum to 1.0"):
        ScoreWeights(
            trend=Decimal("0.1"),
            demand=Decimal("0.1"),
            competition=Decimal("0.1"),
            margin=Decimal("0.1"),
            supply=Decimal("0.1"),
            shop_fit=Decimal("0.1"),
            confidence=Decimal("0.1"),
        )


def test_margin_points_must_be_ascending(scoring_config: ScoringConfig) -> None:
    with pytest.raises(ValidationError, match="ascending"):
        ScoringConfig(
            version="bad",
            weights=scoring_config.weights,
            margin_score_points=(
                MarginScorePoint(margin_rate=Decimal("0.2"), score=Decimal("50")),
                MarginScorePoint(margin_rate=Decimal("0.1"), score=Decimal("60")),
            ),
        )
