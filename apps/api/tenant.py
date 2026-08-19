from typing import Annotated
from uuid import UUID

from fastapi import Header

from commerce_agent.application.tenant_context import TenantContext


async def get_tenant_context(
    tenant_id: Annotated[UUID, Header(alias="X-Tenant-ID")],
    actor_id: Annotated[UUID, Header(alias="X-Actor-ID")],
    roles: Annotated[str, Header(alias="X-Roles")] = "viewer",
) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        actor_id=actor_id,
        roles=frozenset(role.strip() for role in roles.split(",") if role.strip()),
    )
