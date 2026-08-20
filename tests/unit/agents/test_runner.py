from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field

from commerce_agent.application.agents.prompts import PromptRegistry
from commerce_agent.application.agents.records import InMemoryAgentRunStore
from commerce_agent.application.agents.runner import AgentRequest, AgentRunner
from commerce_agent.integrations.llm.base import LLMResponse, LLMUsage
from commerce_agent.integrations.llm.errors import LLMBudgetExceededError
from commerce_agent.integrations.llm.fake import FakeLLMClient


class AnalysisOutput(BaseModel):
    score: int = Field(ge=0, le=100)
    reason: str


def request() -> AgentRequest:
    return AgentRequest(
        tenant_id=uuid4(),
        correlation_id=uuid4(),
        agent_name="test-agent",
        agent_version="1.0",
        workflow_name="test-workflow",
        prompt_name="test/analyze",
        prompt_version="v1",
        model="fake-model",
        input={"candidate_json": '{"name":"cup"}'},
        output_schema=AnalysisOutput,
    )


@pytest.mark.asyncio
async def test_runner_records_prompt_usage_and_output(prompt_registry: PromptRegistry) -> None:
    client = FakeLLMClient([{"score": 80, "reason": "good fit"}])
    store = InMemoryAgentRunStore()
    result = await AgentRunner(client=client, prompts=prompt_registry, store=store).run(request())

    assert result.output == AnalysisOutput(score=80, reason="good fit")
    assert result.usage.total_tokens == 15
    assert store.runs[0].status == "succeeded"
    assert store.runs[0].prompt_hash
    assert store.runs[0].input_tokens == 10


@pytest.mark.asyncio
async def test_malformed_output_is_repaired_with_bounded_retry(
    prompt_registry: PromptRegistry,
) -> None:
    client = FakeLLMClient(
        [{"score": 500, "reason": "invalid"}, {"score": 50, "reason": "repaired"}]
    )
    store = InMemoryAgentRunStore()
    result = await AgentRunner(client=client, prompts=prompt_registry, store=store).run(request())

    assert result.repair_attempts == 1
    assert len(client.requests) == 2
    assert "failed schema validation" in client.requests[1].user_prompt


@pytest.mark.asyncio
async def test_budget_exceeded_has_clear_failure_record(prompt_registry: PromptRegistry) -> None:
    output = AnalysisOutput(score=80, reason="costly")
    client = FakeLLMClient(
        [
            LLMResponse(
                output=output,
                usage=LLMUsage(100, 50, Decimal("2")),
                provider="fake",
                model="fake-model",
            )
        ]
    )
    store = InMemoryAgentRunStore()

    with pytest.raises(LLMBudgetExceededError, match="budget exceeded"):
        await AgentRunner(client=client, prompts=prompt_registry, store=store).run(request())
    assert store.runs[0].status == "failed"
    assert store.runs[0].error_code == "LLMBudgetExceededError"
    assert store.runs[0].input_tokens == 100
    assert store.runs[0].estimated_cost == Decimal("2")
