from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from commerce_agent.domain.scoring.config import ScoringConfig

FINAL_SCORE_QUANTUM = Decimal("0.001")


class FeatureScores(BaseModel):
    model_config = {"frozen": True}
    trend: Decimal = Field(ge=0, le=100)
    demand: Decimal = Field(ge=0, le=100)
    competition: Decimal = Field(ge=0, le=100)
    margin: Decimal = Field(ge=0, le=100)
    supply: Decimal = Field(ge=0, le=100)
    shop_fit: Decimal = Field(ge=0, le=100)
    confidence: Decimal = Field(ge=0, le=100)


class CalculatedOpportunityScore(BaseModel):
    model_config = {"frozen": True}
    candidate_id: UUID
    version: str
    scores: FeatureScores
    final_score: Decimal = Field(ge=0, le=100)
    weights: dict[str, Decimal]


class OpportunityScoreCalculator:
    def calculate(
        self, candidate_id: UUID, scores: FeatureScores, config: ScoringConfig
    ) -> CalculatedOpportunityScore:
        score_values = scores.model_dump()
        weight_values = config.weights.model_dump()
        final_score = sum(
            (score_values[name] * weight_values[name] for name in score_values), Decimal("0")
        ).quantize(FINAL_SCORE_QUANTUM, rounding=ROUND_HALF_UP)
        return CalculatedOpportunityScore(
            candidate_id=candidate_id,
            version=config.version,
            scores=scores,
            final_score=final_score,
            weights=weight_values,
        )
