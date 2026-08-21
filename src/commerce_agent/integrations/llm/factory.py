from commerce_agent.config.settings import Settings
from commerce_agent.integrations.llm.anthropic import AnthropicLLMClient
from commerce_agent.integrations.llm.base import LLMClient
from commerce_agent.integrations.llm.errors import LLMConfigurationError
from commerce_agent.integrations.llm.gemini import GeminiLLMClient
from commerce_agent.integrations.llm.openai import OpenAILLMClient
from commerce_agent.integrations.llm.router import ModelRouter


def configured_llm_providers(settings: Settings) -> list[str]:
    providers: list[str] = []
    if settings.openai_api_key:
        providers.append("openai")
    if settings.anthropic_api_key:
        providers.append("anthropic")
    if settings.gemini_api_key:
        providers.append("gemini")
    if settings.llm_gateway_base_url and settings.llm_gateway_api_key:
        providers.append("gateway")
    return providers


def create_model_router(settings: Settings) -> ModelRouter:
    clients: dict[str, LLMClient] = {}
    if settings.openai_api_key:
        clients["openai"] = OpenAILLMClient(
            api_key=settings.openai_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    if settings.anthropic_api_key:
        clients["anthropic"] = AnthropicLLMClient(
            api_key=settings.anthropic_api_key.get_secret_value(),
            base_url=settings.anthropic_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if settings.gemini_api_key:
        clients["gemini"] = GeminiLLMClient(
            api_key=settings.gemini_api_key.get_secret_value(),
            base_url=settings.gemini_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if settings.llm_gateway_base_url and settings.llm_gateway_api_key:
        clients["gateway"] = OpenAILLMClient(
            api_key=settings.llm_gateway_api_key.get_secret_value(),
            base_url=settings.llm_gateway_base_url,
            provider_name="gateway",
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    if not clients:
        raise LLMConfigurationError(
            "configure OPENAI_API_KEY or LLM_GATEWAY_BASE_URL and LLM_GATEWAY_API_KEY"
        )
    return ModelRouter(
        clients=clients,
        default_provider=settings.llm_provider,
        fallback_provider=settings.llm_fallback_provider,
    )
