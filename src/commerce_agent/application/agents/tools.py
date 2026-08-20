from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any
from uuid import UUID

from commerce_agent.application.agents.records import AgentRunStore, ToolCallRecord

ToolFunction = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class LoggedToolExecutor:
    def __init__(self, store: AgentRunStore) -> None:
        self._store = store

    async def execute(
        self,
        *,
        tenant_id: UUID,
        agent_run_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        function: ToolFunction,
    ) -> dict[str, Any]:
        started = monotonic()
        record = ToolCallRecord(
            tenant_id=tenant_id,
            agent_run_id=agent_run_id,
            tool_name=tool_name,
            arguments=arguments,
        )
        try:
            result = await function(arguments)
            record.status = "succeeded"
            record.result_summary = result
            return result
        except Exception as error:
            record.status = "failed"
            record.error_message = str(error)[:2000]
            raise
        finally:
            record.latency_ms = round((monotonic() - started) * 1000)
            await self._store.log_tool_call(record)
