from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.application.agents.records import AgentRunRecord, ToolCallRecord
from commerce_agent.domain.common import utc_now
from commerce_agent.domain.entities import Tenant
from commerce_agent.infrastructure.db.agent_runs import SqlAlchemyAgentRunStore
from commerce_agent.infrastructure.db.models import AgentRunModel, ToolCallModel
from commerce_agent.infrastructure.db.repositories import SqlAlchemyTenantRepository


async def test_agent_and_tool_call_records_are_persisted(db_session: AsyncSession) -> None:
    tenant = Tenant(name="Agent Tenant")
    await SqlAlchemyTenantRepository(db_session).add(tenant)
    store = SqlAlchemyAgentRunStore(db_session)
    run = AgentRunRecord(
        tenant_id=tenant.id,
        agent_name="market",
        agent_version="1",
        workflow_name="discovery",
        correlation_id=uuid4(),
        input={"candidate": "cup"},
        prompt_name="market/analyze",
        prompt_version="v1",
        prompt_hash="a" * 64,
    )
    await store.start(run)
    run.status = "succeeded"
    run.output = {"score": 80}
    run.model_provider = "fake"
    run.model_name = "fake-model"
    run.input_tokens = 12
    run.output_tokens = 4
    run.estimated_cost = Decimal("0.001")
    run.completed_at = utc_now()
    await store.finish(run)
    await store.log_tool_call(
        ToolCallRecord(
            tenant_id=tenant.id,
            agent_run_id=run.id,
            tool_name="search",
            arguments={"query": "cup"},
            result_summary={"count": 2},
            status="succeeded",
            latency_ms=5,
        )
    )

    stored_run = await db_session.scalar(select(AgentRunModel).where(AgentRunModel.id == run.id))
    stored_tool = await db_session.scalar(
        select(ToolCallModel).where(ToolCallModel.agent_run_id == run.id)
    )
    assert stored_run is not None
    assert stored_run.prompt_hash == "a" * 64
    assert stored_run.input_tokens == 12
    assert stored_tool is not None
    assert stored_tool.result_summary_json == {"count": 2}
