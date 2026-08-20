from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from commerce_agent.application.agents.prompts import PromptRegistry
from commerce_agent.application.agents.records import InMemoryAgentRunStore
from commerce_agent.application.agents.runner import AgentRunner
from commerce_agent.application.agents.schemas import (
    CandidateInput,
    ShopAggregateProfile,
)
from commerce_agent.application.agents.specialists import (
    AgentExecutionContext,
    CategorizerAgent,
    CategorizerInput,
    EvidenceItem,
    MarketAnalystAgent,
    MarketAnalystInput,
    ShopFitAgent,
    ShopFitInput,
    SourcingAgent,
    SourcingInput,
)
from commerce_agent.integrations.llm.fake import FakeLLMClient


def context() -> AgentExecutionContext:
    return AgentExecutionContext(uuid4(), uuid4(), "fake-model")


def candidate() -> CandidateInput:
    return CandidateInput(
        canonical_name="600 ml steel tumbler",
        observed_attributes={"capacity_ml": 600},
        source_observation_ids=["obs-1"],
    )


def runner(response: dict[str, object]) -> AgentRunner:
    return AgentRunner(
        client=FakeLLMClient([response]),
        prompts=PromptRegistry(Path("prompts")),
        store=InMemoryAgentRunStore(),
    )


def envelope(result: dict[str, object], *, confidence: float = 0.8) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "confidence": confidence,
        "summary": "Grounded result",
        "facts": [{"id": "f1", "statement": "Observed fact", "source_ids": ["obs-1"]}],
        "inferences": [{"statement": "Interpretation", "supporting_fact_ids": ["f1"]}],
        "risks": [],
        "missing_data": [],
        "result": result,
    }


@pytest.mark.asyncio
async def test_categorizer_uses_supplied_taxonomy_and_review_rule() -> None:
    response = envelope(
        {
            "category_id": "home.kitchen.drinkware",
            "attributes": {"capacity_ml": 600},
            "reason": "Observed",
            "needs_review": False,
        }
    )
    output = await CategorizerAgent(runner(response)).analyze(
        context(),
        CategorizerInput(
            candidate=candidate(),
            allowed_category_ids=["home.kitchen.drinkware"],
            review_confidence_threshold=0.7,
        ),
    )
    assert output.result.category_id == "home.kitchen.drinkware"


@pytest.mark.asyncio
async def test_market_analyst_accepts_only_available_sources() -> None:
    response = envelope(
        {
            "demand_assessment": "Growing",
            "competition_assessment": "Moderate",
            "price_band": {"minimum": "20", "maximum": "30", "currency": "USD"},
            "positive_signals": ["growth"],
            "negative_signals": [],
            "market_risks": [],
        }
    )
    output = await MarketAnalystAgent(runner(response)).analyze(
        context(),
        MarketAnalystInput(
            candidate=candidate(), observations=[EvidenceItem(source_id="obs-1", data={})]
        ),
    )
    assert output.result.price_band is not None


@pytest.mark.asyncio
async def test_sourcing_does_not_invent_supplier_without_source() -> None:
    response = {
        "schema_version": "1.0",
        "confidence": 0.2,
        "summary": "No supplier evidence",
        "facts": [],
        "inferences": [],
        "risks": [],
        "missing_data": ["supplier source"],
        "result": {
            "suppliers": [
                {
                    "supplier_name": "Invented Supplier",
                    "source_ids": ["invented"],
                    "rank": 1,
                    "landed_cost_assumptions": [],
                    "risks": [],
                }
            ],
            "verification_checklist": [],
        },
    }
    with pytest.raises(ValueError, match="unavailable sources"):
        await SourcingAgent(runner(response)).analyze(
            context(), SourcingInput(candidate=candidate(), supplier_observations=[])
        )


@pytest.mark.asyncio
async def test_shop_fit_prompt_receives_aggregate_profile_only() -> None:
    response = envelope(
        {
            "category_affinity": 0.8,
            "asp_fit": 0.7,
            "attribute_fit": 0.9,
            "cross_sell_opportunity": 0.6,
            "cannibalization_risk": 0.2,
            "reason": "Aggregate fit",
        }
    )
    profile = ShopAggregateProfile(
        category_revenue_share={"home.kitchen": 0.8},
        asp_percentiles={"p50": Decimal("25")},
        repeat_purchase_proxy=0.2,
        best_seller_attributes={"material": ["steel"]},
        seasonality_features={},
        inventory_turnover_by_category={"home.kitchen": 3.0},
        data_coverage=0.9,
    )
    output = await ShopFitAgent(runner(response)).analyze(
        context(),
        ShopFitInput(candidate=candidate(), shop_profile=profile, profile_source_id="obs-1"),
    )
    assert output.result.category_affinity == 0.8
