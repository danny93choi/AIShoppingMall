from collections.abc import AsyncIterator
from uuid import uuid4

from apps.api.dependencies import get_db_session
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.domain.common import utc_now
from commerce_agent.infrastructure.db.models import ProductCandidateModel, TenantModel


async def test_commercial_evidence_is_tenant_scoped_and_persisted(
    app: FastAPI, db_session: AsyncSession
) -> None:
    now = utc_now()
    tenant = TenantModel(
        name="Commercial evidence",
        status="active",
        timezone="Asia/Seoul",
        currency="KRW",
        created_at=now,
        updated_at=now,
    )
    db_session.add(tenant)
    await db_session.flush()
    candidate = ProductCandidateModel(
        tenant_id=tenant.id,
        canonical_name="진공밀폐용기",
        brand=None,
        category_path=["home"],
        description=None,
        attributes_json={},
        primary_image_url=None,
        source_count=1,
        first_seen_at=now,
        last_seen_at=now,
        dedupe_key=f"commercial-{uuid4()}",
        status="discovered",
        created_at=now,
        updated_at=now,
    )
    db_session.add(candidate)
    await db_session.flush()

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = session_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/admin/candidates/{candidate.id}/commercial-evidence",
                headers={
                    "X-Tenant-ID": str(tenant.id),
                    "X-Actor-ID": str(uuid4()),
                    "X-Roles": "owner",
                },
                json={
                    "supplier_name": "테스트 공급처",
                    "supplier_cost": 10000,
                    "expected_sale_price": 25000,
                    "shipping_per_unit": 3000,
                    "minimum_order_quantity": 20,
                    "competitor_price": 26000,
                    "marketplace_fee_rate": 0.12,
                    "ad_cost_rate": 0.05,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["expected_margin_rate"] == 0.31
    assert candidate.attributes_json["commercial_evidence"]["verdict"] == "판매 검토 가능"
