from dataclasses import dataclass

from commerce_agent.application.agents.schemas import AgentEnvelope


@dataclass(frozen=True, slots=True)
class GroundingEvaluation:
    fact_count: int
    inference_count: int
    unsupported_claims: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.unsupported_claims


def evaluate_grounding(
    output: AgentEnvelope, available_source_ids: set[str]
) -> GroundingEvaluation:
    unsupported = tuple(
        fact.statement
        for fact in output.facts
        if any(source_id not in available_source_ids for source_id in fact.source_ids)
    )
    return GroundingEvaluation(
        fact_count=len(output.facts),
        inference_count=len(output.inferences),
        unsupported_claims=unsupported,
    )
