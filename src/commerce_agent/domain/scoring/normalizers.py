from decimal import ROUND_HALF_UP, Decimal

from commerce_agent.domain.scoring.config import MarginScorePoint
from commerce_agent.domain.scoring.features import (
    CompetitionFeatures,
    ConfidenceFeatures,
    DemandFeatures,
    ShopFitFeatures,
    SupplyFeatures,
    TrendFeatures,
)

SCORE_QUANTUM = Decimal("0.001")
HUNDRED = Decimal("100")


def _score(value: Decimal) -> Decimal:
    return min(max(value * HUNDRED, Decimal("0")), HUNDRED).quantize(
        SCORE_QUANTUM, rounding=ROUND_HALF_UP
    )


def _average(values: tuple[Decimal, ...]) -> Decimal:
    return _score(sum(values, Decimal("0")) / Decimal(len(values)))


def normalize_trend(value: TrendFeatures) -> Decimal:
    raw = (
        Decimal("0.35") * value.growth_7d
        + Decimal("0.25") * value.growth_30d
        + Decimal("0.15") * value.acceleration
        + Decimal("0.15") * value.source_diversity
        + Decimal("0.10") * value.recency
    )
    return _score(raw)


def normalize_demand(value: DemandFeatures) -> Decimal:
    return _average(
        (
            value.engagement_level,
            value.review_velocity,
            value.sales_rank_signal,
            value.intent_signal,
        )
    )


def normalize_competition(value: CompetitionFeatures) -> Decimal:
    return _average(
        (
            value.competing_product_inverse,
            value.seller_concentration_inverse,
            value.ad_saturation_inverse,
            value.price_compression_inverse,
        )
    )


def normalize_supply(value: SupplyFeatures) -> Decimal:
    return _average(
        (
            value.supplier_count,
            value.moq_suitability,
            value.lead_time,
            value.supplier_confidence,
            value.cost_stability,
            value.stock_availability,
        )
    )


def normalize_shop_fit(value: ShopFitFeatures) -> Decimal:
    positive = _average(
        (
            value.category_affinity,
            value.target_asp_fit,
            value.winner_attribute_similarity,
            value.cross_sell_potential,
            value.customer_profile_fit,
            value.season_fit,
        )
    )
    return max(positive - _score(value.cannibalization_penalty), Decimal("0")).quantize(
        SCORE_QUANTUM, rounding=ROUND_HALF_UP
    )


def normalize_confidence(value: ConfidenceFeatures) -> Decimal:
    return _average(
        (
            value.source_count,
            value.source_diversity,
            value.freshness,
            value.price_confidence,
            value.supplier_verification,
            value.shop_data_coverage,
        )
    )


def normalize_margin(margin_rate: Decimal, points: tuple[MarginScorePoint, ...]) -> Decimal:
    if margin_rate <= points[0].margin_rate:
        return points[0].score.quantize(SCORE_QUANTUM)
    if margin_rate >= points[-1].margin_rate:
        return points[-1].score.quantize(SCORE_QUANTUM)
    for index in range(len(points) - 1):
        left, right = points[index], points[index + 1]
        if left.margin_rate <= margin_rate <= right.margin_rate:
            position = (margin_rate - left.margin_rate) / (right.margin_rate - left.margin_rate)
            return (left.score + position * (right.score - left.score)).quantize(
                SCORE_QUANTUM, rounding=ROUND_HALF_UP
            )
    raise AssertionError("validated margin points must cover the input")
