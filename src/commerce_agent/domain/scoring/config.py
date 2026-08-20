import json
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

SCORE_COMPONENTS = (
    "trend",
    "demand",
    "competition",
    "margin",
    "supply",
    "shop_fit",
    "confidence",
)


class ScoreWeights(BaseModel):
    model_config = {"frozen": True}
    trend: Decimal = Field(ge=0, le=1)
    demand: Decimal = Field(ge=0, le=1)
    competition: Decimal = Field(ge=0, le=1)
    margin: Decimal = Field(ge=0, le=1)
    supply: Decimal = Field(ge=0, le=1)
    shop_fit: Decimal = Field(ge=0, le=1)
    confidence: Decimal = Field(ge=0, le=1)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "ScoreWeights":
        if sum(self.model_dump().values(), Decimal("0")) != Decimal("1"):
            raise ValueError("scoring weights must sum to 1.0")
        return self


class MarginScorePoint(BaseModel):
    model_config = {"frozen": True}
    margin_rate: Decimal
    score: Decimal = Field(ge=0, le=100)


class HardRejectConfig(BaseModel):
    model_config = {"frozen": True}
    minimum_margin_rate: Decimal = Decimal("0.05")
    minimum_confidence_score: Decimal = Field(default=Decimal("30"), ge=0, le=100)
    require_supplier: bool = True
    restricted_categories: frozenset[str] = frozenset()
    maximum_price_premium_rate: Decimal = Field(default=Decimal("0.30"), ge=0)


class ScoringConfig(BaseModel):
    model_config = {"frozen": True}
    version: str
    weights: ScoreWeights
    margin_score_points: tuple[MarginScorePoint, ...]
    hard_reject: HardRejectConfig = HardRejectConfig()

    @model_validator(mode="after")
    def margin_points_are_valid(self) -> "ScoringConfig":
        if len(self.margin_score_points) < 2:
            raise ValueError("at least two margin score points are required")
        rates = [point.margin_rate for point in self.margin_score_points]
        scores = [point.score for point in self.margin_score_points]
        if rates != sorted(rates) or len(rates) != len(set(rates)):
            raise ValueError("margin rate points must be unique and ascending")
        if scores != sorted(scores):
            raise ValueError("margin scores must be ascending")
        return self


def load_scoring_config(path: Path) -> ScoringConfig:
    return ScoringConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))
