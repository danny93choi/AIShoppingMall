from uuid import uuid4

import pytest

from commerce_agent.application.agents.records import InMemoryAgentRunStore
from commerce_agent.application.agents.tools import LoggedToolExecutor


@pytest.mark.asyncio
async def test_tool_call_is_logged() -> None:
    store = InMemoryAgentRunStore()

    async def tool(arguments: dict[str, object]) -> dict[str, object]:
        return {"count": arguments["limit"]}

    result = await LoggedToolExecutor(store).execute(
        tenant_id=uuid4(),
        agent_run_id=uuid4(),
        tool_name="search",
        arguments={"limit": 3},
        function=tool,
    )

    assert result == {"count": 3}
    assert store.tool_calls[0].status == "succeeded"
    assert store.tool_calls[0].latency_ms is not None
