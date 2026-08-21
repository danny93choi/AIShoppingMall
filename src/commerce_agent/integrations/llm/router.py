from dataclasses import replace

from commerce_agent.integrations.llm.base import LLMClient, LLMRequest, LLMResponse
from commerce_agent.integrations.llm.errors import LLMConfigurationError


class ModelRouter(LLMClient):
    """Routes provider-neutral requests to configured model adapters."""

    def __init__(
        self,
        *,
        clients: dict[str, LLMClient],
        default_provider: str,
        fallback_provider: str | None = None,
    ) -> None:
        if default_provider not in clients:
            raise LLMConfigurationError(
                f"default LLM provider '{default_provider}' is not configured"
            )
        if fallback_provider is not None and fallback_provider not in clients:
            raise LLMConfigurationError(
                f"fallback LLM provider '{fallback_provider}' is not configured"
            )
        self._clients = dict(clients)
        self._default_provider = default_provider
        self._fallback_provider = fallback_provider

    @property
    def providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._clients))

    async def generate_structured(self, request: LLMRequest) -> LLMResponse:
        provider = request.provider or self._default_provider
        client = self._clients.get(provider)
        if client is None:
            raise LLMConfigurationError(
                f"LLM provider '{provider}' is not configured; available: "
                f"{', '.join(self.providers) or 'none'}"
            )
        try:
            return await client.generate_structured(replace(request, provider=provider))
        except Exception:
            fallback = self._fallback_provider
            if fallback is None or fallback == provider:
                raise
            return await self._clients[fallback].generate_structured(
                replace(request, provider=fallback)
            )
