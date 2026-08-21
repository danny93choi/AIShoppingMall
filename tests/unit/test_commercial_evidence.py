from decimal import Decimal

from apps.api.routers.admin import CommercialEvidenceRequest, _commercial_evidence


def test_commercial_evidence_calculates_profit_margin_and_break_even() -> None:
    evidence = _commercial_evidence(
        CommercialEvidenceRequest(
            supplier_name="테스트 공급처",
            supplier_cost=Decimal("10000"),
            expected_sale_price=Decimal("25000"),
            shipping_per_unit=Decimal("3000"),
            minimum_order_quantity=20,
            competitor_price=Decimal("26000"),
            marketplace_fee_rate=Decimal("0.12"),
            ad_cost_rate=Decimal("0.05"),
        )
    )

    assert evidence["landed_cost"] == 13000
    assert evidence["fee_cost"] == 4250
    assert evidence["expected_profit"] == 7750
    assert evidence["expected_margin_rate"] == 0.31
    assert evidence["break_even_price"] == 15662.65
    assert evidence["verdict"] == "판매 검토 가능"


def test_commercial_evidence_blocks_low_margin_or_overpriced_product() -> None:
    evidence = _commercial_evidence(
        CommercialEvidenceRequest(
            supplier_name="테스트 공급처",
            supplier_cost=Decimal("18000"),
            expected_sale_price=Decimal("22000"),
            competitor_price=Decimal("18000"),
        )
    )

    assert evidence["price_risk"] is True
    assert evidence["verdict"] == "판매 보류"
