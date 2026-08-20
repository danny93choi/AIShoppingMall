from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: Decimal = Decimal("0")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class LLMRequest:
    model: str
    system_prompt: str
    user_prompt: str
    output_schema: type[BaseModel]
    temperature: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMResponse:
    output: BaseModel
    usage: LLMUsage
    provider: str
    model: str
    trace_id: str | None = None


class LLMClient(Protocol):
    async def generate_structured(self, request: LLMRequest) -> LLMResponse: ...
