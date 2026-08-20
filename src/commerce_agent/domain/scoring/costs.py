from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

MONEY_QUANTUM = Decimal("0.0001")
RATE_QUANTUM = Decimal("0.000001")


class DataQuality(StrEnum):
    ACTUAL = "actual"
    QUOTED = "quoted"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class CostValue(BaseModel):
    model_config = {"frozen": True}
    amount: Decimal | None = Field(default=None, ge=0)
    quality: DataQuality

    @model_validator(mode="after")
    def quality_matches_amount(self) -> "CostValue":
        if self.quality == DataQuality.UNKNOWN and self.amount is not None:
            raise ValueError("unknown cost must not have an amount")
        if self.quality != DataQuality.UNKNOWN and self.amount is None:
            raise ValueError("known cost must have an amount")
        return self


class LandedCostInput(BaseModel):
    model_config = {"frozen": True}
    supplier_unit_cost: CostValue
    per_unit_shipping: CostValue
    per_unit_duty: CostValue
    per_unit_import_tax: CostValue
    payment_fee: CostValue
    inbound_handling: CostValue


class LandedCostResult(BaseModel):
    model_config = {"frozen": True}
    amount: Decimal
    complete: bool
    unknown_components: tuple[str, ...]


class PricingInput(BaseModel):
    model_config = {"frozen": True}
    selling_price: Decimal = Field(gt=0)
    landed_cost: Decimal = Field(ge=0)
    variable_platform_fee: Decimal = Field(default=Decimal("0"), ge=0)
    expected_discount: Decimal = Field(default=Decimal("0"), ge=0)
    expected_refund_cost: Decimal = Field(default=Decimal("0"), ge=0)


class PricingEconomics(BaseModel):
    model_config = {"frozen": True}
    contribution_margin: Decimal
    margin_rate: Decimal


def calculate_landed_cost(value: LandedCostInput) -> LandedCostResult:
    components = value.model_dump()
    unknown = tuple(name for name, item in components.items() if item["amount"] is None)
    amount = sum(
        (item["amount"] or Decimal("0") for item in components.values()), Decimal("0")
    ).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    return LandedCostResult(amount=amount, complete=not unknown, unknown_components=unknown)


def calculate_pricing_economics(value: PricingInput) -> PricingEconomics:
    contribution_margin = (
        value.selling_price
        - value.landed_cost
        - value.variable_platform_fee
        - value.expected_discount
        - value.expected_refund_cost
    ).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    margin_rate = (contribution_margin / value.selling_price).quantize(
        RATE_QUANTUM, rounding=ROUND_HALF_UP
    )
    return PricingEconomics(
        contribution_margin=contribution_margin,
        margin_rate=margin_rate,
    )
