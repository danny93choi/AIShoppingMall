from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.application.workflows.state import DiscoveryWorkflowState
from commerce_agent.domain.common import utc_now
from commerce_agent.infrastructure.db.models import JobModel


class JobService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_or_restart(
        self, *, tenant_id: UUID, correlation_id: UUID, idempotency_key: str
    ) -> JobModel:
        job = await self._session.scalar(
            select(JobModel).where(
                JobModel.tenant_id == tenant_id,
                JobModel.idempotency_key == idempotency_key,
            )
        )
        now = utc_now()
        if job is None:
            job = JobModel(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                job_type="discovery",
                status="queued",
                progress_percent=0,
                current_step=None,
                completed_steps=[],
                warnings_json=[],
                errors_json=[],
                summary_json={},
                started_at=None,
                completed_at=None,
                heartbeat_at=now,
                created_at=now,
                updated_at=now,
            )
            self._session.add(job)
        else:
            job.correlation_id = correlation_id
            job.status = "queued"
            job.progress_percent = 0
            job.current_step = None
            job.completed_steps = []
            job.warnings_json = []
            job.errors_json = []
            job.summary_json = {}
            job.started_at = None
            job.completed_at = None
            job.heartbeat_at = now
            job.updated_at = now
        await self._session.flush()
        return job

    async def update(
        self,
        state: DiscoveryWorkflowState,
        *,
        step: str | None,
        progress: int,
        summary: dict[str, Any] | None = None,
    ) -> None:
        job = await self._session.scalar(
            select(JobModel).where(
                JobModel.tenant_id == state.tenant_id, JobModel.id == state.job_id
            )
        )
        if job is None:
            raise ValueError("job not found in tenant scope")
        now = utc_now()
        job.status = state.status
        job.progress_percent = progress
        job.current_step = step
        job.completed_steps = state.completed_steps
        job.warnings_json = [item.model_dump(mode="json") for item in state.warnings]
        job.errors_json = [item.model_dump(mode="json") for item in state.errors]
        job.summary_json = summary or job.summary_json
        job.started_at = job.started_at or now
        job.heartbeat_at = now
        job.completed_at = now if state.status in {"succeeded", "partial", "failed"} else None
        job.updated_at = now
        await self._session.flush()
