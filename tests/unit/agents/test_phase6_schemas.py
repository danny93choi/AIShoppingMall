from decimal import Decimal

import pytest
from pydantic import ValidationError

from commerce_agent.application.agents.evals import evaluate_grounding
from commerce_agent.application.agents.schemas import (
    CategorizerOutput,
    ShopAggregateProfile,
)


def categorizer_output(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "1.0",
        "confidence": 0.9,
        "summary": "Drinkware",
        "facts": [{"id": "f1", "statement": "600 ml", "source_ids": ["obs-1"]}],
        "inferences": [{"statement": "A tumbler", "supporting_fact_ids": ["f1"]}],
        "risks": [],
        "missing_data": [],
        "result": {
            "category_id": "home.kitchen.drinkware",
            "attributes": {"capacity_ml": 600},
            "reason": "Observed capacity",
            "needs_review": False,
        },
    }
    value.update(overrides)
    return value


def test_envelope_rejects_inference_without_known_fact() -> None:
    value = categorizer_output(
        inferences=[{"statement": "Unsupported", "supporting_fact_ids": ["missing"]}]
    )
    with pytest.raises(ValidationError, match="unknown facts"):
        CategorizerOutput.model_validate(value)


def test_confidence_is_conservative_when_data_is_missing() -> None:
    value = categorizer_output(missing_data=["material"])
    with pytest.raises(ValidationError, match="cannot exceed 0.8"):
        CategorizerOutput.model_validate(value)


def test_unsupported_claim_evaluation_detects_unknown_source() -> None:
    output = CategorizerOutput.model_validate(categorizer_output())
    evaluation = evaluate_grounding(output, {"other-source"})
    assert not evaluation.passed
    assert evaluation.unsupported_claims == ("600 ml",)


def test_shop_profile_rejects_pii_fields() -> None:
    with pytest.raises(ValidationError, match="email"):
        ShopAggregateProfile.model_validate(
            {
                "category_revenue_share": {},
                "asp_percentiles": {"p50": Decimal("20")},
                "repeat_purchase_proxy": None,
                "best_seller_attributes": {},
                "seasonality_features": {},
                "inventory_turnover_by_category": {},
                "data_coverage": 0.5,
                "email": "customer@example.com",
            }
        )
