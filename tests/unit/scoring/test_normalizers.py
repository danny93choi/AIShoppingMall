from decimal import Decimal

from commerce_agent.domain.scoring.config import ScoringConfig
from commerce_agent.domain.scoring.features import (
    CompetitionFeatures,
    ConfidenceFeatures,
    DemandFeatures,
    ShopFitFeatures,
    SupplyFeatures,
    TrendFeatures,
)
from commerce_agent.domain.scoring.normalizers import (
    normalize_competition,
    normalize_confidence,
    normalize_demand,
    normalize_margin,
    normalize_shop_fit,
    normalize_supply,
    normalize_trend,
)


def test_trend_formula_matches_spec() -> None:
    value = TrendFeatures(
        growth_7d=Decimal("1"),
        growth_30d=Decimal("0.8"),
        acceleration=Decimal("0.6"),
        source_diversity=Decimal("0.4"),
        recency=Decimal("0.2"),
    )
    assert normalize_trend(value) == Decimal("72.000")


def test_component_normalizers_cover_zero_and_max() -> None:
    assert normalize_demand(DemandFeatures(**dict.fromkeys(DemandFeatures.model_fields, 0))) == 0
    assert (
        normalize_competition(
            CompetitionFeatures(**dict.fromkeys(CompetitionFeatures.model_fields, 1))
        )
        == 100
    )
    assert normalize_supply(SupplyFeatures(**dict.fromkeys(SupplyFeatures.model_fields, 1))) == 100
    assert (
        normalize_confidence(
            ConfidenceFeatures(**dict.fromkeys(ConfidenceFeatures.model_fields, 0))
        )
        == 0
    )


def test_shop_fit_applies_cannibalization_penalty() -> None:
    value = ShopFitFeatures(
        category_affinity=Decimal("0.8"),
        target_asp_fit=Decimal("0.8"),
        winner_attribute_similarity=Decimal("0.8"),
        cross_sell_potential=Decimal("0.8"),
        customer_profile_fit=Decimal("0.8"),
        season_fit=Decimal("0.8"),
        cannibalization_penalty=Decimal("0.2"),
    )
    assert normalize_shop_fit(value) == Decimal("60.000")


def test_margin_piecewise_boundaries_and_interpolation(scoring_config: ScoringConfig) -> None:
    points = scoring_config.margin_score_points
    assert normalize_margin(Decimal("0.05"), points) == Decimal("0.000")
    assert normalize_margin(Decimal("0.10"), points) == Decimal("25.000")
    assert normalize_margin(Decimal("0.15"), points) == Decimal("42.500")
    assert normalize_margin(Decimal("0.40"), points) == Decimal("100.000")
    assert normalize_margin(Decimal("0.90"), points) == Decimal("100.000")
