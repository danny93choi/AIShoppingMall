from decimal import Decimal

from commerce_agent.domain.scoring.config import HardRejectConfig
from commerce_agent.domain.scoring.rejections import HardRejectInput, evaluate_hard_reject


def valid_input(**updates: object) -> HardRejectInput:
    values: dict[str, object] = {
        "category_id": "home.kitchen.drinkware",
        "margin_rate": Decimal("0.20"),
        "confidence_score": Decimal("80"),
        "supplier_count": 2,
        "expected_selling_price": Decimal("10000"),
        "market_reference_price": Decimal("10000"),
    }
    values.update(updates)
    return HardRejectInput.model_validate(values)


def test_valid_candidate_is_not_rejected() -> None:
    assert not evaluate_hard_reject(valid_input(), HardRejectConfig()).rejected


def test_hard_reject_collects_all_reason_codes() -> None:
    config = HardRejectConfig(restricted_categories=frozenset({"restricted"}))
    decision = evaluate_hard_reject(
        valid_input(
            category_id="restricted",
            margin_rate=Decimal("0.01"),
            confidence_score=10,
            supplier_count=0,
            expected_selling_price=Decimal("15000"),
        ),
        config,
    )
    assert decision.rejected
    assert decision.reason_codes == (
        "MARGIN_BELOW_MINIMUM",
        "CONFIDENCE_BELOW_MINIMUM",
        "SUPPLIER_REQUIRED",
        "RESTRICTED_CATEGORY",
        "PRICE_PREMIUM_UNREALISTIC",
    )


def test_minimum_boundaries_are_allowed() -> None:
    config = HardRejectConfig()
    decision = evaluate_hard_reject(
        valid_input(
            margin_rate=config.minimum_margin_rate,
            confidence_score=config.minimum_confidence_score,
        ),
        config,
    )
    assert not decision.rejected
