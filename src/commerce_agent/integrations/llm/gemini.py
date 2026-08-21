from decimal import Decimal
from typing import Any

import httpx

from commerce_agent.integrations.llm.base import LLMClient, LLMRequest, LLMResponse, LLMUsage
from commerce_agent.integrations.llm.errors import LLMConfigurationError, LLMStructuredOutputError


class GeminiLLMClient(LLMClient):
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 30,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if client is None and not api_key:
            raise LLMConfigurationError("Gemini API key is required")
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None

    async def generate_structured(self, request: LLMRequest) -> LLMResponse:
        response = await self._client.post(
            f"{self._base_url}/models/{request.model}:generateContent",
            headers={"x-goog-api-key": self._api_key, "content-type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": request.system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": request.user_prompt}]}],
                "generationConfig": {
                    "temperature": request.temperature,
                    "responseMimeType": "application/json",
                    "responseJsonSchema": request.output_schema.model_json_schema(),
                },
            },
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        try:
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            output = request.output_schema.model_validate_json(text)
        except Exception as error:
            raise LLMStructuredOutputError("Gemini returned invalid structured output") from error
        usage = payload.get("usageMetadata", {})
        return LLMResponse(
            output=output,
            usage=LLMUsage(
                input_tokens=int(usage.get("promptTokenCount", 0)),
                output_tokens=int(usage.get("candidatesTokenCount", 0)),
                estimated_cost_usd=Decimal("0"),
            ),
            provider="gemini",
            model=request.model,
            trace_id=response.headers.get("x-request-id"),
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
