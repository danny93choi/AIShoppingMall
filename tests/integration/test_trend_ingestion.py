from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.application.services.trend_ingestion import TrendIngestionService
from commerce_agent.domain.entities import Tenant
from commerce_agent.infrastructure.db.models import (
    ProductCandidateModel,
    RawTrendObservationModel,
)
from commerce_agent.infrastructure.db.repositories import SqlAlchemyTenantRepository
from commerce_agent.integrations.trend_sources.base import TrendQuery
from commerce_agent.integrations.trend_sources.mock import MockTrendSource

FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "trend_sources"


async def test_100_items_merge_to_five_candidates_and_are_idempotent(
    db_session: AsyncSession,
) -> None:
    tenant = Tenant(name=f"Trend tenant {uuid4()}", currency="KRW", timezone="Asia/Seoul")
    await SqlAlchemyTenantRepository(db_session).add(tenant)
    sources = [
        MockTrendSource("mock_trend_a", FIXTURE_ROOT / "mock_trend_a.json"),
        MockTrendSource("mock_trend_b", FIXTURE_ROOT / "mock_trend_b.json"),
    ]
    service = TrendIngestionService(db_session)

    first = await service.ingest(tenant.id, sources, TrendQuery(max_results=100))
    second = await service.ingest(tenant.id, sources, TrendQuery(max_results=100))

    candidate_count = await db_session.scalar(
        select(func.count())
        .select_from(ProductCandidateModel)
        .where(ProductCandidateModel.tenant_id == tenant.id)
    )
    observation_count = await db_session.scalar(
        select(func.count())
        .select_from(RawTrendObservationModel)
        .where(RawTrendObservationModel.tenant_id == tenant.id)
    )
    candidates = (
        await db_session.scalars(
            select(ProductCandidateModel).where(ProductCandidateModel.tenant_id == tenant.id)
        )
    ).all()
    observation = await db_session.scalar(
        select(RawTrendObservationModel)
        .where(RawTrendObservationModel.tenant_id == tenant.id)
        .limit(1)
    )

    assert first.raw_items == 100
    assert first.candidates_created == 5
    assert second.candidates_created == 0
    assert candidate_count == 5
    assert observation_count == 100
    assert {candidate.source_count for candidate in candidates} == {20}
    assert all(candidate.category_path != ["uncategorized"] for candidate in candidates)
    assert observation is not None
    assert observation.source
    assert observation.source_id
    assert observation.url.startswith("https://")
    assert observation.candidate_id is not None
