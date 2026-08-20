from decimal import Decimal

from commerce_agent.domain.scoring.costs import (
    CostValue,
    DataQuality,
    LandedCostInput,
    PricingInput,
    calculate_landed_cost,
    calculate_pricing_economics,
)


def known(amount: str, quality: DataQuality = DataQuality.ESTIMATED) -> CostValue:
    return CostValue(amount=Decimal(amount), quality=quality)


def test_landed_cost_sums_known_components() -> None:
    result = calculate_landed_cost(
        LandedCostInput(
            supplier_unit_cost=known("10000", DataQuality.QUOTED),
            per_unit_shipping=known("2000"),
            per_unit_duty=known("500"),
            per_unit_import_tax=known("1000"),
            payment_fee=known("300"),
            inbound_handling=known("200"),
        )
    )
    assert result.amount == Decimal("14000.0000")
    assert result.complete
    assert result.unknown_components == ()


def test_unknown_cost_is_reported_and_not_invented() -> None:
    result = calculate_landed_cost(
        LandedCostInput(
            supplier_unit_cost=known("10000"),
            per_unit_shipping=CostValue(quality=DataQuality.UNKNOWN),
            per_unit_duty=known("0"),
            per_unit_import_tax=known("0"),
            payment_fee=known("0"),
            inbound_handling=known("0"),
        )
    )
    assert result.amount == Decimal("10000.0000")
    assert not result.complete
    assert result.unknown_components == ("per_unit_shipping",)


def test_contribution_margin_and_rate_are_deterministic() -> None:
    result = calculate_pricing_economics(
        PricingInput(
            selling_price=Decimal("39000"),
            landed_cost=Decimal("16000"),
            variable_platform_fee=Decimal("3900"),
            expected_discount=Decimal("2000"),
            expected_refund_cost=Decimal("800"),
        )
    )
    assert result.contribution_margin == Decimal("16300.0000")
    assert result.margin_rate == Decimal("0.417949")
