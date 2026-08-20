from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from commerce_agent.domain.scoring.calculator import FeatureScores, OpportunityScoreCalculator
from commerce_agent.domain.scoring.config import ScoringConfig


def test_same_input_produces_same_score(scoring_config: ScoringConfig) -> None:
    candidate_id = uuid4()
    scores = FeatureScores(
        trend=80,
        demand=70,
        competition=60,
        margin=90,
        supply=50,
        shop_fit=85,
        confidence=75,
    )
    calculator = OpportunityScoreCalculator()
    first = calculator.calculate(candidate_id, scores, scoring_config)
    second = calculator.calculate(candidate_id, scores, scoring_config)
    assert first == second
    assert first.final_score == Decimal("74.750")


@pytest.mark.parametrize(("value", "expected"), [(0, Decimal("0.000")), (100, Decimal("100.000"))])
def test_zero_and_max_scores(value: int, expected: Decimal, scoring_config: ScoringConfig) -> None:
    scores = FeatureScores(**dict.fromkeys(FeatureScores.model_fields, value))
    result = OpportunityScoreCalculator().calculate(uuid4(), scores, scoring_config)
    assert result.final_score == expected


def test_missing_feature_is_rejected() -> None:
    with pytest.raises(ValidationError):
        FeatureScores.model_validate(
            {
                "trend": 1,
                "demand": 1,
                "competition": 1,
                "margin": 1,
                "supply": 1,
                "shop_fit": 1,
            }
        )
