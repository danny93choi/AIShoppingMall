from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.application.workflows.discovery import DiscoveryWorkflow
from commerce_agent.domain.common import utc_now
from commerce_agent.infrastructure.db.models import (
    CommerceConnectionModel,
    JobModel,
    OpportunityScoreModel,
    RecommendationModel,
    TenantModel,
)
from commerce_agent.integrations.commerce.mock import MockCommerceAdapter
from commerce_agent.integrations.trend_sources.base import RawTrendItem, TrendQuery
from commerce_agent.integrations.trend_sources.mock import MockTrendSource

ROOT = Path(__file__).resolve().parents[2]


class FailingTrendSource:
    name = "failing_source"

    async def discover(self, query: TrendQuery) -> list[RawTrendItem]:
        raise TimeoutError("fixture timeout")


async def test_discovery_continues_after_one_source_failure_and_is_idempotent(
    db_session: AsyncSession,
) -> None:
    now = utc_now()
    tenant = TenantModel(
        name=f"Discovery {uuid4()}",
        status="active",
        timezone="UTC",
        currency="KRW",
        created_at=now,
        updated_at=now,
    )
    db_session.add(tenant)
    await db_session.flush()
    connection = CommerceConnectionModel(
        tenant_id=tenant.id,
        provider="mock",
        external_shop_id=f"shop-{uuid4()}",
        display_name="Discovery Fixture",
        status="active",
        credential_ref=None,
        scopes=[],
        last_sync_at=None,
        metadata_json={},
        created_at=now,
        updated_at=now,
    )
    db_session.add(connection)
    await db_session.flush()
    workflow = DiscoveryWorkflow(
        session=db_session,
        commerce_adapter=MockCommerceAdapter(ROOT / "fixtures/commerce/demo_shop.json"),
        trend_sources=[
            MockTrendSource("mock_trend_a", ROOT / "fixtures/trend_sources/mock_trend_a.json"),
            FailingTrendSource(),
        ],
        scoring_config_path=ROOT / "assets/scoring/default/v1.json",
        supplier_fixture_path=ROOT / "fixtures/suppliers/demo_suppliers.json",
    )

    first = await workflow.run(
        tenant_id=tenant.id,
        connection_id=connection.id,
        categories=[],
        idempotency_key="integration-discovery",
    )
    second = await workflow.run(
        tenant_id=tenant.id,
        connection_id=connection.id,
        categories=[],
        idempotency_key="integration-discovery",
    )

    assert first.status == "partial"
    assert first.warning_count == 1
    assert first.candidates == 5
    assert first.recommendations == 5
    assert [item["rank"] for item in first.top_recommendations] == [1, 2, 3, 4, 5]
    assert second.job_id == first.job_id
    score_count = await db_session.scalar(
        select(func.count())
        .select_from(OpportunityScoreModel)
        .where(OpportunityScoreModel.tenant_id == tenant.id)
    )
    recommendation_count = await db_session.scalar(
        select(func.count())
        .select_from(RecommendationModel)
        .where(RecommendationModel.tenant_id == tenant.id)
    )
    job = await db_session.scalar(
        select(JobModel).where(JobModel.tenant_id == tenant.id, JobModel.id == first.job_id)
    )
    assert score_count == 5
    assert recommendation_count == 5
    assert job is not None
    assert job.status == "partial"
    assert job.progress_percent == 100
    assert job.summary_json["recommendations"] == 5
