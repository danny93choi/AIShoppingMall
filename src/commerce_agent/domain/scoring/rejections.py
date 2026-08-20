from decimal import Decimal

from pydantic import BaseModel, Field

from commerce_agent.domain.scoring.config import HardRejectConfig


class HardRejectInput(BaseModel):
    model_config = {"frozen": True}
    category_id: str
    margin_rate: Decimal
    confidence_score: Decimal = Field(ge=0, le=100)
    supplier_count: int = Field(ge=0)
    expected_selling_price: Decimal = Field(gt=0)
    market_reference_price: Decimal | None = Field(default=None, gt=0)


class HardRejectDecision(BaseModel):
    model_config = {"frozen": True}
    rejected: bool
    reason_codes: tuple[str, ...]


def evaluate_hard_reject(value: HardRejectInput, config: HardRejectConfig) -> HardRejectDecision:
    reasons: list[str] = []
    if value.margin_rate < config.minimum_margin_rate:
        reasons.append("MARGIN_BELOW_MINIMUM")
    if value.confidence_score < config.minimum_confidence_score:
        reasons.append("CONFIDENCE_BELOW_MINIMUM")
    if config.require_supplier and value.supplier_count == 0:
        reasons.append("SUPPLIER_REQUIRED")
    if value.category_id in config.restricted_categories:
        reasons.append("RESTRICTED_CATEGORY")
    if value.market_reference_price is not None:
        maximum_price = value.market_reference_price * (
            Decimal("1") + config.maximum_price_premium_rate
        )
        if value.expected_selling_price > maximum_price:
            reasons.append("PRICE_PREMIUM_UNREALISTIC")
    return HardRejectDecision(rejected=bool(reasons), reason_codes=tuple(reasons))
