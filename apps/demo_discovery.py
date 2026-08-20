import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from commerce_agent.application.workflows.discovery import DiscoveryWorkflow
from commerce_agent.config.settings import get_settings
from commerce_agent.domain.common import utc_now
from commerce_agent.infrastructure.db.models import CommerceConnectionModel, TenantModel
from commerce_agent.infrastructure.db.session import create_session_factory
from commerce_agent.integrations.commerce.mock import MockCommerceAdapter
from commerce_agent.integrations.trend_sources.mock import MockTrendSource

ROOT = Path(__file__).resolve().parents[1]


async def run_demo() -> None:
    settings = get_settings()
    factory = create_session_factory(settings.database_url)
    async with factory() as session, session.begin():
        tenant = await session.scalar(select(TenantModel).where(TenantModel.name == "Demo Shop"))
        now = utc_now()
        if tenant is None:
            tenant = TenantModel(
                name="Demo Shop",
                status="active",
                timezone="Asia/Seoul",
                currency="KRW",
                created_at=now,
                updated_at=now,
            )
            session.add(tenant)
            await session.flush()
        connection = await session.scalar(
            select(CommerceConnectionModel).where(
                CommerceConnectionModel.tenant_id == tenant.id,
                CommerceConnectionModel.provider == "mock",
                CommerceConnectionModel.external_shop_id == "demo-shop",
            )
        )
        if connection is None:
            connection = CommerceConnectionModel(
                tenant_id=tenant.id,
                provider="mock",
                external_shop_id="demo-shop",
                display_name="Demo Fixture Shop",
                status="active",
                credential_ref=None,
                scopes=["read_products", "read_orders", "read_inventory"],
                last_sync_at=None,
                metadata_json={"fixture": True},
                created_at=now,
                updated_at=now,
            )
            session.add(connection)
            await session.flush()
        workflow = DiscoveryWorkflow(
            session=session,
            commerce_adapter=MockCommerceAdapter(ROOT / "fixtures/commerce/demo_shop.json"),
            trend_sources=[
                MockTrendSource("mock_trend_a", ROOT / "fixtures/trend_sources/mock_trend_a.json"),
                MockTrendSource("mock_trend_b", ROOT / "fixtures/trend_sources/mock_trend_b.json"),
            ],
            scoring_config_path=ROOT / "assets/scoring/default/v1.json",
            supplier_fixture_path=ROOT / "fixtures/suppliers/demo_suppliers.json",
        )
        summary = await workflow.run(
            tenant_id=tenant.id,
            connection_id=connection.id,
            categories=[],
            idempotency_key="demo-discovery-v1",
            max_candidates=100,
            top_n=5,
        )
        print(json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(run_demo())
