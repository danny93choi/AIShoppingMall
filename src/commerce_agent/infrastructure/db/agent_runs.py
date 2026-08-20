from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.application.agents.records import (
    AgentRunRecord,
    AgentRunStore,
    ToolCallRecord,
)
from commerce_agent.domain.common import utc_now
from commerce_agent.infrastructure.db.models import AgentRunModel, ToolCallModel


class SqlAlchemyAgentRunStore(AgentRunStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._models: dict[object, AgentRunModel] = {}

    async def start(self, record: AgentRunRecord) -> None:
        model = AgentRunModel(
            id=record.id,
            tenant_id=record.tenant_id,
            agent_name=record.agent_name,
            agent_version=record.agent_version,
            workflow_name=record.workflow_name,
            correlation_id=record.correlation_id,
            status=record.status,
            input_json=record.input,
            output_json=record.output,
            prompt_name=record.prompt_name,
            prompt_version=record.prompt_version,
            prompt_hash=record.prompt_hash,
            model_provider=record.model_provider,
            model_name=record.model_name,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            estimated_cost=record.estimated_cost,
            started_at=record.started_at,
            completed_at=record.completed_at,
            error_code=record.error_code,
            error_message=record.error_message,
            created_at=record.started_at,
            updated_at=record.started_at,
        )
        self._session.add(model)
        self._models[record.id] = model
        await self._session.flush()

    async def finish(self, record: AgentRunRecord) -> None:
        model = self._models.get(record.id)
        if model is None:
            raise ValueError("agent run was not started by this store")
        model.status = record.status
        model.output_json = record.output
        model.model_provider = record.model_provider
        model.model_name = record.model_name
        model.input_tokens = record.input_tokens
        model.output_tokens = record.output_tokens
        model.estimated_cost = record.estimated_cost
        model.completed_at = record.completed_at
        model.error_code = record.error_code
        model.error_message = record.error_message
        model.updated_at = utc_now()
        await self._session.flush()

    async def log_tool_call(self, record: ToolCallRecord) -> None:
        now = utc_now()
        self._session.add(
            ToolCallModel(
                id=record.id,
                tenant_id=record.tenant_id,
                agent_run_id=record.agent_run_id,
                tool_name=record.tool_name,
                arguments_json=record.arguments,
                result_summary_json=record.result_summary,
                status=record.status,
                latency_ms=record.latency_ms,
                error_message=record.error_message,
                created_at=now,
                updated_at=now,
            )
        )
        await self._session.flush()
