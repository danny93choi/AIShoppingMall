from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceFact(StrictModel):
    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)


class SupportedInference(StrictModel):
    statement: str = Field(min_length=1)
    supporting_fact_ids: list[str] = Field(min_length=1)


class AgentEnvelope(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=1)
    facts: list[EvidenceFact] = Field(default_factory=list)
    inferences: list[SupportedInference] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence_and_confidence(self) -> "AgentEnvelope":
        fact_ids = {fact.id for fact in self.facts}
        unsupported = {
            fact_id
            for inference in self.inferences
            for fact_id in inference.supporting_fact_ids
            if fact_id not in fact_ids
        }
        if unsupported:
            raise ValueError(f"inferences reference unknown facts: {sorted(unsupported)}")
        if not self.facts and self.confidence > 0.2:
            raise ValueError("confidence cannot exceed 0.2 without sourced facts")
        if self.missing_data and self.confidence > 0.8:
            raise ValueError("confidence cannot exceed 0.8 when data is missing")
        return self


class CandidateInput(StrictModel):
    canonical_name: str
    description: str | None = None
    observed_attributes: dict[str, Any] = Field(default_factory=dict)
    source_observation_ids: list[str] = Field(default_factory=list)


class CategorizationResult(StrictModel):
    category_id: str
    attributes: dict[str, str | int | float | bool]
    reason: str
    needs_review: bool


class CategorizerOutput(AgentEnvelope):
    result: CategorizationResult


class PriceBand(StrictModel):
    minimum: Decimal
    maximum: Decimal
    currency: str = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_range(self) -> "PriceBand":
        if self.maximum < self.minimum:
            raise ValueError("price maximum must be at least minimum")
        return self


class MarketAnalysisResult(StrictModel):
    demand_assessment: str
    competition_assessment: str
    price_band: PriceBand | None = None
    positive_signals: list[str]
    negative_signals: list[str]
    market_risks: list[str]


class MarketAnalystOutput(AgentEnvelope):
    result: MarketAnalysisResult


class SupplierObservation(StrictModel):
    source_id: str = Field(min_length=1)
    supplier_name: str
    unit_cost: Decimal | None = None
    currency: str | None = None
    moq: int | None = Field(default=None, ge=1)
    lead_time_days: int | None = Field(default=None, ge=0)
    verified: bool = False


class SupplierRanking(StrictModel):
    supplier_name: str
    source_ids: list[str] = Field(min_length=1)
    rank: int = Field(ge=1)
    landed_cost_assumptions: list[str]
    risks: list[str]


class SourcingResult(StrictModel):
    suppliers: list[SupplierRanking]
    verification_checklist: list[str]


class SourcingOutput(AgentEnvelope):
    result: SourcingResult


class ShopAggregateProfile(StrictModel):
    category_revenue_share: dict[str, float]
    asp_percentiles: dict[str, Decimal]
    repeat_purchase_proxy: float | None = Field(default=None, ge=0, le=1)
    best_seller_attributes: dict[str, list[str]]
    seasonality_features: dict[str, float]
    inventory_turnover_by_category: dict[str, float]
    data_coverage: float = Field(ge=0, le=1)


class ShopFitResult(StrictModel):
    category_affinity: float = Field(ge=0, le=1)
    asp_fit: float = Field(ge=0, le=1)
    attribute_fit: float = Field(ge=0, le=1)
    cross_sell_opportunity: float = Field(ge=0, le=1)
    cannibalization_risk: float = Field(ge=0, le=1)
    reason: str


class ShopFitOutput(AgentEnvelope):
    result: ShopFitResult
