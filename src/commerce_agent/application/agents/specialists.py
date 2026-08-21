from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from commerce_agent.application.agents.evals import evaluate_grounding
from commerce_agent.application.agents.runner import AgentRequest, AgentRunner
from commerce_agent.application.agents.schemas import (
    AgentEnvelope,
    CandidateInput,
    CategorizerOutput,
    MarketAnalystOutput,
    ShopAggregateProfile,
    ShopFitOutput,
    SourcingOutput,
    SupplierObservation,
)


class SpecialistInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CategorizerInput(SpecialistInput):
    candidate: CandidateInput
    allowed_category_ids: list[str] = Field(min_length=1)
    review_confidence_threshold: float = Field(default=0.7, ge=0, le=1)


class EvidenceItem(SpecialistInput):
    source_id: str = Field(min_length=1)
    data: dict[str, Any]


class MarketAnalystInput(SpecialistInput):
    candidate: CandidateInput
    observations: list[EvidenceItem]


class SourcingInput(SpecialistInput):
    candidate: CandidateInput
    supplier_observations: list[SupplierObservation]


class ShopFitInput(SpecialistInput):
    candidate: CandidateInput
    shop_profile: ShopAggregateProfile
    profile_source_id: str = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class AgentExecutionContext:
    tenant_id: UUID
    correlation_id: UUID
    model: str
    provider: str | None = None
    maximum_cost_usd: Decimal = Decimal("1")


class _SpecialistAgent:
    agent_name: str
    prompt_name: str
    output_schema: type[AgentEnvelope]
    agent_version = "1.0"
    prompt_version = "v1"

    def __init__(self, runner: AgentRunner) -> None:
        self._runner = runner

    async def _execute(
        self,
        *,
        context: AgentExecutionContext,
        agent_input: SpecialistInput,
        allowed_source_ids: set[str],
    ) -> AgentEnvelope:
        result = await self._runner.run(
            AgentRequest(
                tenant_id=context.tenant_id,
                correlation_id=context.correlation_id,
                agent_name=self.agent_name,
                agent_version=self.agent_version,
                workflow_name="candidate_enrichment",
                prompt_name=self.prompt_name,
                prompt_version=self.prompt_version,
                model=context.model,
                provider=context.provider,
                input={"input_json": agent_input.model_dump_json()},
                output_schema=self.output_schema,
                maximum_cost_usd=context.maximum_cost_usd,
            )
        )
        output = self.output_schema.model_validate(result.output.model_dump())
        evaluation = evaluate_grounding(output, allowed_source_ids)
        if not evaluation.passed:
            raise ValueError(f"output contains unsupported claims: {evaluation.unsupported_claims}")
        return output


class CategorizerAgent(_SpecialistAgent):
    agent_name = "categorizer"
    prompt_name = "categorizer/classify_candidate"
    output_schema = CategorizerOutput

    async def analyze(
        self, context: AgentExecutionContext, agent_input: CategorizerInput
    ) -> CategorizerOutput:
        output = CategorizerOutput.model_validate(
            (
                await self._execute(
                    context=context,
                    agent_input=agent_input,
                    allowed_source_ids=set(agent_input.candidate.source_observation_ids),
                )
            ).model_dump()
        )
        if output.result.category_id not in agent_input.allowed_category_ids:
            raise ValueError("categorizer returned a category outside the supplied taxonomy")
        expected_review = output.confidence < agent_input.review_confidence_threshold
        if output.result.needs_review != expected_review:
            raise ValueError("needs_review does not match the configured confidence threshold")
        return output


class MarketAnalystAgent(_SpecialistAgent):
    agent_name = "market_analyst"
    prompt_name = "market/analyze_candidate"
    output_schema = MarketAnalystOutput

    async def analyze(
        self, context: AgentExecutionContext, agent_input: MarketAnalystInput
    ) -> MarketAnalystOutput:
        output = await self._execute(
            context=context,
            agent_input=agent_input,
            allowed_source_ids={item.source_id for item in agent_input.observations},
        )
        return MarketAnalystOutput.model_validate(output.model_dump())


class SourcingAgent(_SpecialistAgent):
    agent_name = "sourcing"
    prompt_name = "sourcing/compare_suppliers"
    output_schema = SourcingOutput

    async def analyze(
        self, context: AgentExecutionContext, agent_input: SourcingInput
    ) -> SourcingOutput:
        available = {item.source_id for item in agent_input.supplier_observations}
        output = SourcingOutput.model_validate(
            (
                await self._execute(
                    context=context,
                    agent_input=agent_input,
                    allowed_source_ids=available,
                )
            ).model_dump()
        )
        cited = {
            source_id for supplier in output.result.suppliers for source_id in supplier.source_ids
        }
        if cited - available:
            raise ValueError(f"supplier cites unavailable sources: {sorted(cited - available)}")
        if not available and output.result.suppliers:
            raise ValueError("suppliers cannot be created without source observations")
        return output


class ShopFitAgent(_SpecialistAgent):
    agent_name = "shop_fit"
    prompt_name = "shop_fit/analyze_candidate"
    output_schema = ShopFitOutput

    async def analyze(
        self, context: AgentExecutionContext, agent_input: ShopFitInput
    ) -> ShopFitOutput:
        output = await self._execute(
            context=context,
            agent_input=agent_input,
            allowed_source_ids={
                agent_input.profile_source_id,
                *agent_input.candidate.source_observation_ids,
            },
        )
        return ShopFitOutput.model_validate(output.model_dump())
