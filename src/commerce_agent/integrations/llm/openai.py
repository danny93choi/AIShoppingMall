from collections.abc import Callable
from decimal import Decimal
from typing import Any

from openai import AsyncOpenAI

from commerce_agent.integrations.llm.base import LLMClient, LLMRequest, LLMResponse, LLMUsage
from commerce_agent.integrations.llm.errors import LLMConfigurationError, LLMStructuredOutputError

RedactionHook = Callable[[str], str]
CostEstimator = Callable[[str, int, int], Decimal]


def _identity(value: str) -> str:
    return value


def _zero_cost(_model: str, _input_tokens: int, _output_tokens: int) -> Decimal:
    return Decimal("0")


class OpenAILLMClient(LLMClient):
    """OpenAI Responses API adapter; provider objects never cross this boundary."""

    def __init__(
        self,
        *,
        api_key: str | None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        redact: RedactionHook = _identity,
        estimate_cost: CostEstimator = _zero_cost,
        client: AsyncOpenAI | None = None,
    ) -> None:
        if client is None and not api_key:
            raise LLMConfigurationError("OPENAI_API_KEY is required for the OpenAI provider")
        self._client = client or AsyncOpenAI(
            api_key=api_key, timeout=timeout_seconds, max_retries=max_retries
        )
        self._redact = redact
        self._estimate_cost = estimate_cost

    async def generate_structured(self, request: LLMRequest) -> LLMResponse:
        response = await self._client.responses.parse(
            model=request.model,
            input=[
                {"role": "system", "content": self._redact(request.system_prompt)},
                {"role": "user", "content": self._redact(request.user_prompt)},
            ],
            text_format=request.output_schema,
            temperature=request.temperature,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise LLMStructuredOutputError("OpenAI response did not contain parsed output")
        usage: Any = response.usage
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        model_name = str(response.model or request.model)
        return LLMResponse(
            output=parsed,
            usage=LLMUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=self._estimate_cost(model_name, input_tokens, output_tokens),
            ),
            provider="openai",
            model=model_name,
            trace_id=response.id,
        )
