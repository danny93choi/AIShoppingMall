from collections import deque
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from commerce_agent.integrations.llm.base import LLMClient, LLMRequest, LLMResponse, LLMUsage


class FakeLLMClient(LLMClient):
    """Deterministic scripted client for tests and offline demos."""

    def __init__(
        self, responses: Iterable[LLMResponse | BaseModel | dict[str, Any] | Exception]
    ) -> None:
        self._responses = deque(responses)
        self.requests: list[LLMRequest] = []

    async def generate_structured(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self._responses:
            raise RuntimeError("FakeLLMClient has no scripted response")
        scripted = self._responses.popleft()
        if isinstance(scripted, Exception):
            raise scripted
        if isinstance(scripted, LLMResponse):
            return scripted
        output = (
            scripted
            if isinstance(scripted, BaseModel)
            else request.output_schema.model_validate(scripted)
        )
        return LLMResponse(
            output=output,
            usage=LLMUsage(input_tokens=10, output_tokens=5),
            provider="fake",
            model=request.model,
            trace_id=f"fake-{len(self.requests)}",
        )
