import pytest
from pydantic import BaseModel

from commerce_agent.config.settings import Settings
from commerce_agent.integrations.llm.base import LLMRequest
from commerce_agent.integrations.llm.errors import LLMConfigurationError
from commerce_agent.integrations.llm.factory import configured_llm_providers
from commerce_agent.integrations.llm.fake import FakeLLMClient
from commerce_agent.integrations.llm.router import ModelRouter


class RoutedOutput(BaseModel):
    verdict: str


def _request(provider: str | None = None) -> LLMRequest:
    return LLMRequest(
        model="market-model",
        provider=provider,
        system_prompt="system",
        user_prompt="user",
        output_schema=RoutedOutput,
    )


@pytest.mark.asyncio
async def test_router_selects_requested_provider() -> None:
    openai = FakeLLMClient([{"verdict": "openai"}])
    gateway = FakeLLMClient([{"verdict": "gateway"}])
    router = ModelRouter(
        clients={"openai": openai, "gateway": gateway},
        default_provider="openai",
    )

    response = await router.generate_structured(_request("gateway"))

    assert response.output == RoutedOutput(verdict="gateway")
    assert len(openai.requests) == 0
    assert gateway.requests[0].provider == "gateway"


@pytest.mark.asyncio
async def test_router_uses_configured_fallback() -> None:
    primary = FakeLLMClient([RuntimeError("provider unavailable")])
    fallback = FakeLLMClient([{"verdict": "fallback"}])
    router = ModelRouter(
        clients={"primary": primary, "fallback": fallback},
        default_provider="primary",
        fallback_provider="fallback",
    )

    response = await router.generate_structured(_request())

    assert response.output == RoutedOutput(verdict="fallback")
    assert fallback.requests[0].provider == "fallback"


@pytest.mark.asyncio
async def test_router_rejects_unconfigured_provider() -> None:
    router = ModelRouter(
        clients={"openai": FakeLLMClient([])},
        default_provider="openai",
    )

    with pytest.raises(LLMConfigurationError, match="not configured"):
        await router.generate_structured(_request("unknown"))


def test_configured_provider_detection_does_not_expose_secrets() -> None:
    settings = Settings(
        openai_api_key="openai-secret",
        llm_gateway_base_url="http://gateway.test/v1",
        llm_gateway_api_key="gateway-secret",
    )

    assert configured_llm_providers(settings) == ["openai", "gateway"]
    assert "secret" not in repr(settings)
