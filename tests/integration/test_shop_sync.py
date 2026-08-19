from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.application.services.shop_sync import ShopSyncService
from commerce_agent.domain.common import utc_now
from commerce_agent.domain.entities import Tenant
from commerce_agent.infrastructure.db.models import (
    CommerceConnectionModel,
    SalesAggregateModel,
    ShopProductSnapshotModel,
)
from commerce_agent.infrastructure.db.repositories import SqlAlchemyTenantRepository
from commerce_agent.integrations.commerce.mock import MockCommerceAdapter

FIXTURE = Path(__file__).parents[2] / "fixtures" / "commerce" / "demo_shop.json"


async def test_sync_is_idempotent_and_builds_expected_profile(db_session: AsyncSession) -> None:
    tenant = Tenant(name=f"Demo {uuid4()}", currency="KRW", timezone="Asia/Seoul")
    await SqlAlchemyTenantRepository(db_session).add(tenant)
    now = utc_now()
    connection = CommerceConnectionModel(
        tenant_id=tenant.id,
        provider="mock",
        external_shop_id=f"demo-{uuid4()}",
        display_name="Demo shop",
        status="active",
        credential_ref=None,
        scopes=[],
        metadata_json={},
        created_at=now,
        updated_at=now,
    )
    db_session.add(connection)
    await db_session.flush()
    service = ShopSyncService(db_session, MockCommerceAdapter(FIXTURE))

    first = await service.sync(tenant.id, connection.id)
    second = await service.sync(tenant.id, connection.id)

    product_count = await db_session.scalar(
        select(func.count())
        .select_from(ShopProductSnapshotModel)
        .where(ShopProductSnapshotModel.tenant_id == tenant.id)
    )
    sales_count = await db_session.scalar(
        select(func.count())
        .select_from(SalesAggregateModel)
        .where(SalesAggregateModel.tenant_id == tenant.id)
    )
    assert product_count == 2
    assert sales_count == 2
    assert first.profile == second.profile.model_copy(
        update={"generated_at": first.profile.generated_at}
    )
    assert first.profile.category_revenue_share == {
        "home.kitchen": 0.8,
        "home.bath": 0.2,
    }
    assert first.profile.category_unit_share == {
        "home.kitchen": 2 / 3,
        "home.bath": 1 / 3,
    }
    assert first.profile.asp_percentiles["p50"] == 20000
    assert first.profile.data_coverage == 1.0
