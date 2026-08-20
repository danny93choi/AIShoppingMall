from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID, uuid4

from commerce_agent.domain.common import utc_now


@dataclass(slots=True)
class AgentRunRecord:
    tenant_id: UUID
    agent_name: str
    agent_version: str
    workflow_name: str
    correlation_id: UUID
    input: dict[str, Any]
    prompt_name: str
    prompt_version: str
    prompt_hash: str
    id: UUID = field(default_factory=uuid4)
    status: str = "running"
    output: dict[str, Any] | None = None
    model_provider: str | None = None
    model_name: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: Decimal = Decimal("0")
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class ToolCallRecord:
    tenant_id: UUID
    agent_run_id: UUID
    tool_name: str
    arguments: dict[str, Any]
    id: UUID = field(default_factory=uuid4)
    result_summary: dict[str, Any] | None = None
    status: str = "running"
    latency_ms: int | None = None
    error_message: str | None = None


class AgentRunStore(Protocol):
    async def start(self, record: AgentRunRecord) -> None: ...

    async def finish(self, record: AgentRunRecord) -> None: ...

    async def log_tool_call(self, record: ToolCallRecord) -> None: ...


class InMemoryAgentRunStore(AgentRunStore):
    def __init__(self) -> None:
        self.runs: list[AgentRunRecord] = []
        self.tool_calls: list[ToolCallRecord] = []

    async def start(self, record: AgentRunRecord) -> None:
        self.runs.append(record)

    async def finish(self, record: AgentRunRecord) -> None:
        return None

    async def log_tool_call(self, record: ToolCallRecord) -> None:
        self.tool_calls.append(record)
