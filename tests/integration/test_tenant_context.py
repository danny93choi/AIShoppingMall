from typing import Annotated
from uuid import uuid4

from apps.api.tenant import get_tenant_context
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from commerce_agent.application.tenant_context import TenantContext


async def test_tenant_context_is_created_from_request_headers() -> None:
    app = FastAPI()

    @app.get("/context")
    async def context(
        value: Annotated[TenantContext, Depends(get_tenant_context)],
    ) -> dict[str, object]:
        return {"tenant_id": str(value.tenant_id), "roles": sorted(value.roles)}

    tenant_id = uuid4()
    actor_id = uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/context",
            headers={
                "X-Tenant-ID": str(tenant_id),
                "X-Actor-ID": str(actor_id),
                "X-Roles": "admin, analyst",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"tenant_id": str(tenant_id), "roles": ["admin", "analyst"]}
