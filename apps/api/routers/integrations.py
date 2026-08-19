from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from apps.api.tenant import get_tenant_context
from commerce_agent.application.services.shop_sync import ShopSyncService, SyncResult
from commerce_agent.application.tenant_context import TenantContext
from commerce_agent.domain.common import utc_now
from commerce_agent.infrastructure.db.models import CommerceConnectionModel
from commerce_agent.integrations.commerce.mock import MockCommerceAdapter

router = APIRouter(prefix="/api/v1/integrations/commerce", tags=["commerce-integrations"])
FIXTURE_PATH = Path(__file__).parents[3] / "fixtures" / "commerce" / "demo_shop.json"


class CreateConnectionRequest(BaseModel):
    provider: str = "mock"
    external_shop_id: str
    display_name: str


class ConnectionResponse(BaseModel):
    id: UUID
    provider: str
    external_shop_id: str
    display_name: str
    status: str


def to_response(model: CommerceConnectionModel) -> ConnectionResponse:
    return ConnectionResponse.model_validate(model, from_attributes=True)


@router.post("", response_model=ConnectionResponse, status_code=201)
async def create_connection(
    payload: CreateConnectionRequest,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConnectionResponse:
    if payload.provider != "mock":
        raise HTTPException(status_code=422, detail="Phase 2 supports the mock provider only")
    now = utc_now()
    model = CommerceConnectionModel(
        tenant_id=context.tenant_id,
        provider=payload.provider,
        external_shop_id=payload.external_shop_id,
        display_name=payload.display_name,
        status="active",
        credential_ref=None,
        scopes=["read_products", "read_orders", "read_inventory"],
        metadata_json={},
        created_at=now,
        updated_at=now,
    )
    session.add(model)
    await session.flush()
    return to_response(model)


@router.get("", response_model=list[ConnectionResponse])
async def list_connections(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ConnectionResponse]:
    models = (
        await session.scalars(
            select(CommerceConnectionModel).where(
                CommerceConnectionModel.tenant_id == context.tenant_id
            )
        )
    ).all()
    return [to_response(model) for model in models]


@router.post("/{connection_id}/validate")
async def validate_connection(
    connection_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, object]:
    exists = await session.scalar(
        select(CommerceConnectionModel.id).where(
            CommerceConnectionModel.tenant_id == context.tenant_id,
            CommerceConnectionModel.id == connection_id,
        )
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="connection not found")
    health = await MockCommerceAdapter(FIXTURE_PATH).validate_connection()
    return health.model_dump(mode="json")


@router.post("/{connection_id}/sync", response_model=SyncResult)
async def sync_connection(
    connection_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SyncResult:
    service = ShopSyncService(session, MockCommerceAdapter(FIXTURE_PATH))
    try:
        return await service.sync(context.tenant_id, connection_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
