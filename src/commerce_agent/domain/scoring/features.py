from decimal import Decimal

from pydantic import BaseModel, Field

Normalized = Decimal


class NormalizedFeatureModel(BaseModel):
    model_config = {"frozen": True}


class TrendFeatures(NormalizedFeatureModel):
    growth_7d: Normalized = Field(ge=0, le=1)
    growth_30d: Normalized = Field(ge=0, le=1)
    acceleration: Normalized = Field(ge=0, le=1)
    source_diversity: Normalized = Field(ge=0, le=1)
    recency: Normalized = Field(ge=0, le=1)


class DemandFeatures(NormalizedFeatureModel):
    engagement_level: Normalized = Field(ge=0, le=1)
    review_velocity: Normalized = Field(ge=0, le=1)
    sales_rank_signal: Normalized = Field(ge=0, le=1)
    intent_signal: Normalized = Field(ge=0, le=1)


class CompetitionFeatures(NormalizedFeatureModel):
    competing_product_inverse: Normalized = Field(ge=0, le=1)
    seller_concentration_inverse: Normalized = Field(ge=0, le=1)
    ad_saturation_inverse: Normalized = Field(ge=0, le=1)
    price_compression_inverse: Normalized = Field(ge=0, le=1)


class MarginFeatures(NormalizedFeatureModel):
    margin_rate: Decimal


class SupplyFeatures(NormalizedFeatureModel):
    supplier_count: Normalized = Field(ge=0, le=1)
    moq_suitability: Normalized = Field(ge=0, le=1)
    lead_time: Normalized = Field(ge=0, le=1)
    supplier_confidence: Normalized = Field(ge=0, le=1)
    cost_stability: Normalized = Field(ge=0, le=1)
    stock_availability: Normalized = Field(ge=0, le=1)


class ShopFitFeatures(NormalizedFeatureModel):
    category_affinity: Normalized = Field(ge=0, le=1)
    target_asp_fit: Normalized = Field(ge=0, le=1)
    winner_attribute_similarity: Normalized = Field(ge=0, le=1)
    cross_sell_potential: Normalized = Field(ge=0, le=1)
    customer_profile_fit: Normalized = Field(ge=0, le=1)
    season_fit: Normalized = Field(ge=0, le=1)
    cannibalization_penalty: Normalized = Field(ge=0, le=1)


class ConfidenceFeatures(NormalizedFeatureModel):
    source_count: Normalized = Field(ge=0, le=1)
    source_diversity: Normalized = Field(ge=0, le=1)
    freshness: Normalized = Field(ge=0, le=1)
    price_confidence: Normalized = Field(ge=0, le=1)
    supplier_verification: Normalized = Field(ge=0, le=1)
    shop_data_coverage: Normalized = Field(ge=0, le=1)
