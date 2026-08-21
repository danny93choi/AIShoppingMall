import json
from decimal import Decimal
from typing import Any

import httpx

from commerce_agent.integrations.llm.base import LLMClient, LLMRequest, LLMResponse, LLMUsage
from commerce_agent.integrations.llm.errors import LLMConfigurationError, LLMStructuredOutputError


class AnthropicLLMClient(LLMClient):
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = "https://api.anthropic.com/v1",
        timeout_seconds: float = 30,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if client is None and not api_key:
            raise LLMConfigurationError("Anthropic API key is required")
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None

    async def generate_structured(self, request: LLMRequest) -> LLMResponse:
        schema = request.output_schema.model_json_schema()
        response = await self._client.post(
            f"{self._base_url}/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": request.model,
                "max_tokens": 4096,
                "temperature": request.temperature,
                "system": request.system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"{request.user_prompt}\n\nReturn only JSON matching this schema: "
                            f"{json.dumps(schema, ensure_ascii=False)}"
                        ),
                    }
                ],
            },
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        text = next(
            (
                str(item.get("text", ""))
                for item in payload.get("content", [])
                if item.get("type") == "text"
            ),
            "",
        )
        try:
            output = request.output_schema.model_validate_json(text)
        except Exception as error:
            raise LLMStructuredOutputError(
                "Anthropic returned invalid structured output"
            ) from error
        usage = payload.get("usage", {})
        return LLMResponse(
            output=output,
            usage=LLMUsage(
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
                estimated_cost_usd=Decimal("0"),
            ),
            provider="anthropic",
            model=str(payload.get("model", request.model)),
            trace_id=response.headers.get("request-id"),
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
