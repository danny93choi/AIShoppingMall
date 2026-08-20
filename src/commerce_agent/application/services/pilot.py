from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.domain.common import utc_now
from commerce_agent.infrastructure.db.models import (
    AgentRunModel,
    FeatureFlagModel,
    JobModel,
    PilotFeedbackModel,
    RecommendationModel,
    TenantPilotConfigModel,
)


class OnboardingConfig(BaseModel):
    scoring_preset: str = Field(pattern="^(conservative|growth)$")
    discovery_categories: list[str] = Field(min_length=1)
    max_daily_candidates: int = Field(default=50, ge=1, le=500)
    retention_days: int = Field(default=90, ge=30, le=730)


class FeedbackInput(BaseModel):
    recommendation_id: UUID | None = None
    rating: int = Field(ge=1, le=5)
    category: str = Field(min_length=1, max_length=100)
    comment: str | None = Field(default=None, max_length=2000)


DEFAULT_FLAGS = {
    "discovery": True,
    "marketing_drafts": True,
    "external_mutations": False,
    "shopify_webhooks": False,
}


class PilotService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def onboard(self, tenant_id: UUID, config: OnboardingConfig) -> None:
        now = utc_now()
        values = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            "onboarding_status": "ready",
            **config.model_dump(),
            "created_at": now,
            "updated_at": now,
        }
        statement = insert(TenantPilotConfigModel).values(**values)
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=["tenant_id"],
                set_={
                    key: value for key, value in values.items() if key not in {"id", "created_at"}
                },
            )
        )
        for key, enabled in DEFAULT_FLAGS.items():
            flag_values = {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "key": key,
                "enabled": enabled,
                "configuration_json": {},
                "created_at": now,
                "updated_at": now,
            }
            flag = insert(FeatureFlagModel).values(**flag_values)
            await self._session.execute(
                flag.on_conflict_do_nothing(index_elements=["tenant_id", "key"])
            )
        await self._session.flush()

    async def set_flag(self, tenant_id: UUID, key: str, enabled: bool) -> None:
        flag = await self._session.scalar(
            select(FeatureFlagModel).where(
                FeatureFlagModel.tenant_id == tenant_id, FeatureFlagModel.key == key
            )
        )
        if flag is None:
            raise ValueError("feature flag not found")
        flag.enabled = enabled
        flag.updated_at = utc_now()
        await self._session.flush()

    async def feedback(
        self, tenant_id: UUID, actor_id: UUID, value: FeedbackInput
    ) -> PilotFeedbackModel:
        now = utc_now()
        model = PilotFeedbackModel(
            id=uuid4(),
            tenant_id=tenant_id,
            actor_id=actor_id,
            recommendation_id=value.recommendation_id,
            rating=value.rating,
            category=value.category,
            comment=value.comment,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return model

    async def dashboard(self, tenant_id: UUID) -> dict[str, Any]:
        jobs_total = await self._count(JobModel, tenant_id)
        jobs_succeeded = (
            await self._session.scalar(
                select(func.count())
                .select_from(JobModel)
                .where(JobModel.tenant_id == tenant_id, JobModel.status == "succeeded")
            )
            or 0
        )
        recommendations = await self._count(RecommendationModel, tenant_id)
        approved = (
            await self._session.scalar(
                select(func.count())
                .select_from(RecommendationModel)
                .where(
                    RecommendationModel.tenant_id == tenant_id,
                    RecommendationModel.status == "approved",
                )
            )
            or 0
        )
        cost = await self._session.scalar(
            select(func.coalesce(func.sum(AgentRunModel.estimated_cost), 0)).where(
                AgentRunModel.tenant_id == tenant_id
            )
        )
        average_rating = await self._session.scalar(
            select(func.avg(PilotFeedbackModel.rating)).where(
                PilotFeedbackModel.tenant_id == tenant_id
            )
        )
        cost_value = cost or Decimal("0")
        return {
            "workflow_success_rate": jobs_succeeded / jobs_total if jobs_total else None,
            "approval_rate": approved / recommendations if recommendations else None,
            "llm_cost_usd": str(cost_value),
            "cost_per_discovery_run": str(cost_value / jobs_total) if jobs_total else None,
            "average_feedback_rating": float(average_rating) if average_rating else None,
            "jobs_total": jobs_total,
            "recommendations_total": recommendations,
        }

    async def _count(self, model: type[Any], tenant_id: UUID) -> int:
        return int(
            await self._session.scalar(
                select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
            )
            or 0
        )
