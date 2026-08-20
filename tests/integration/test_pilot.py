from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.application.services.pilot import FeedbackInput, OnboardingConfig, PilotService
from commerce_agent.infrastructure.db.models import FeatureFlagModel, PilotFeedbackModel


async def test_onboarding_flags_feedback_and_cost_dashboard(db_session: AsyncSession) -> None:
    tenant_id = uuid4()
    service = PilotService(db_session)
    await service.onboard(
        tenant_id,
        OnboardingConfig(
            scoring_preset="conservative",
            discovery_categories=["home.kitchen"],
        ),
    )
    flag_count = await db_session.scalar(
        select(func.count())
        .select_from(FeatureFlagModel)
        .where(FeatureFlagModel.tenant_id == tenant_id)
    )
    assert flag_count == 4
    await service.set_flag(tenant_id, "external_mutations", True)
    await service.feedback(
        tenant_id,
        uuid4(),
        FeedbackInput(rating=4, category="recommendation_quality", comment="Useful"),
    )
    feedback_count = await db_session.scalar(
        select(func.count())
        .select_from(PilotFeedbackModel)
        .where(PilotFeedbackModel.tenant_id == tenant_id)
    )
    assert feedback_count == 1
    dashboard = await service.dashboard(tenant_id)
    assert dashboard["llm_cost_usd"] == "0"
    assert dashboard["average_feedback_rating"] == 4.0
