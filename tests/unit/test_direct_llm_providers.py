import json

import httpx
import pytest
from pydantic import BaseModel

from commerce_agent.integrations.llm.anthropic import AnthropicLLMClient
from commerce_agent.integrations.llm.base import LLMRequest
from commerce_agent.integrations.llm.gemini import GeminiLLMClient


class ProviderOutput(BaseModel):
    verdict: str


def _request() -> LLMRequest:
    return LLMRequest(
        model="provider-model",
        system_prompt="system",
        user_prompt="user",
        output_schema=ProviderOutput,
    )


@pytest.mark.asyncio
async def test_anthropic_adapter_normalizes_structured_output() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "anthropic-key"
        return httpx.Response(
            200,
            json={
                "model": "provider-model",
                "content": [{"type": "text", "text": json.dumps({"verdict": "watch"})}],
                "usage": {"input_tokens": 12, "output_tokens": 4},
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    response = await AnthropicLLMClient(api_key="anthropic-key", client=http).generate_structured(
        _request()
    )

    assert response.provider == "anthropic"
    assert response.output == ProviderOutput(verdict="watch")
    assert response.usage.total_tokens == 16
    await http.aclose()


@pytest.mark.asyncio
async def test_gemini_adapter_sends_json_schema_and_normalizes_output() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.headers["x-goog-api-key"] == "gemini-key"
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps({"verdict": "source"})}]}}
                ],
                "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 3},
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    response = await GeminiLLMClient(api_key="gemini-key", client=http).generate_structured(
        _request()
    )

    assert response.provider == "gemini"
    assert response.output == ProviderOutput(verdict="source")
    assert response.usage.total_tokens == 11
    await http.aclose()
