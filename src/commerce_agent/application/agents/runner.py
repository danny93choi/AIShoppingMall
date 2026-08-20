from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError

from commerce_agent.application.agents.budget import CostBudgetGuard
from commerce_agent.application.agents.prompts import PromptRegistry
from commerce_agent.application.agents.records import AgentRunRecord, AgentRunStore
from commerce_agent.domain.common import utc_now
from commerce_agent.integrations.llm.base import LLMClient, LLMRequest, LLMUsage
from commerce_agent.integrations.llm.errors import LLMStructuredOutputError


@dataclass(frozen=True, slots=True)
class AgentRequest:
    tenant_id: UUID
    correlation_id: UUID
    agent_name: str
    agent_version: str
    workflow_name: str
    prompt_name: str
    prompt_version: str
    model: str
    input: dict[str, Any]
    output_schema: type[BaseModel]
    maximum_cost_usd: Decimal = Decimal("1")


@dataclass(frozen=True, slots=True)
class AgentResult:
    output: BaseModel
    run_id: UUID
    usage: LLMUsage
    repair_attempts: int


class AgentRunner:
    def __init__(
        self,
        *,
        client: LLMClient,
        prompts: PromptRegistry,
        store: AgentRunStore,
        max_repair_attempts: int = 2,
    ) -> None:
        self._client = client
        self._prompts = prompts
        self._store = store
        self._max_repair_attempts = max_repair_attempts

    async def run(self, request: AgentRequest) -> AgentResult:
        prompt = self._prompts.load(request.prompt_name, request.prompt_version)
        system_prompt, user_prompt = prompt.render(request.input)
        record = AgentRunRecord(
            tenant_id=request.tenant_id,
            agent_name=request.agent_name,
            agent_version=request.agent_version,
            workflow_name=request.workflow_name,
            correlation_id=request.correlation_id,
            input=request.input,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            prompt_hash=prompt.content_hash,
        )
        await self._store.start(record)
        budget = CostBudgetGuard(request.maximum_cost_usd)
        total_usage = LLMUsage()
        repair_attempts = 0
        current_user_prompt = user_prompt
        try:
            while True:
                try:
                    response = await self._client.generate_structured(
                        LLMRequest(
                            model=request.model,
                            system_prompt=system_prompt,
                            user_prompt=current_user_prompt,
                            output_schema=request.output_schema,
                            metadata={"agent_run_id": str(record.id)},
                        )
                    )
                    total_usage = _add_usage(total_usage, response.usage)
                    record.model_provider = response.provider
                    record.model_name = response.model
                    _apply_usage(record, total_usage)
                    budget.reserve(response.usage.estimated_cost_usd)
                    output = request.output_schema.model_validate(response.output.model_dump())
                    record.status = "succeeded"
                    record.output = output.model_dump(mode="json")
                    record.completed_at = utc_now()
                    await self._store.finish(record)
                    return AgentResult(
                        output=output,
                        run_id=record.id,
                        usage=total_usage,
                        repair_attempts=repair_attempts,
                    )
                except (ValidationError, LLMStructuredOutputError) as error:
                    if repair_attempts >= self._max_repair_attempts:
                        raise
                    repair_attempts += 1
                    current_user_prompt = (
                        f"{user_prompt}\n\nThe previous output failed schema validation. "
                        f"Return only a corrected response matching the schema. Error: {error}"
                    )
        except Exception as error:
            record.status = "failed"
            record.error_code = type(error).__name__
            record.error_message = str(error)[:2000]
            record.completed_at = utc_now()
            _apply_usage(record, total_usage)
            await self._store.finish(record)
            raise


def _add_usage(left: LLMUsage, right: LLMUsage) -> LLMUsage:
    return LLMUsage(
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
        estimated_cost_usd=left.estimated_cost_usd + right.estimated_cost_usd,
    )


def _apply_usage(record: AgentRunRecord, usage: LLMUsage) -> None:
    record.input_tokens = usage.input_tokens
    record.output_tokens = usage.output_tokens
    record.estimated_cost = usage.estimated_cost_usd
