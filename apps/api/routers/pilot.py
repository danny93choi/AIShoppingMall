from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from apps.api.tenant import get_tenant_context
from commerce_agent.application.services.pilot import FeedbackInput, OnboardingConfig, PilotService
from commerce_agent.application.tenant_context import TenantContext
from commerce_agent.infrastructure.db.models import DeadLetterModel, FeatureFlagModel
from commerce_agent.security.rbac import Permission, require_permission

router = APIRouter(prefix="/api/v1/pilot", tags=["pilot"])


class FlagUpdate(BaseModel):
    enabled: bool


@router.post("/onboarding")
async def onboard(
    body: OnboardingConfig,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    require_permission(context, Permission.MANAGE_INTEGRATIONS)
    await PilotService(session).onboard(context.tenant_id, body)
    return {"status": "ready"}


@router.get("/feature-flags")
async def list_flags(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    require_permission(context, Permission.VIEW)
    flags = (
        await session.scalars(
            select(FeatureFlagModel).where(FeatureFlagModel.tenant_id == context.tenant_id)
        )
    ).all()
    return [
        {"key": item.key, "enabled": item.enabled, "config": item.configuration_json}
        for item in flags
    ]


@router.put("/feature-flags/{key}")
async def update_flag(
    key: str,
    body: FlagUpdate,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    require_permission(context, Permission.MANAGE_SECURITY)
    try:
        await PilotService(session).set_flag(context.tenant_id, key, body.enabled)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"key": key, "enabled": body.enabled}


@router.post("/feedback")
async def capture_feedback(
    body: FeedbackInput,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    feedback = await PilotService(session).feedback(context.tenant_id, context.actor_id, body)
    return {"id": feedback.id, "status": "recorded"}


@router.get("/dashboard")
async def pilot_dashboard(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    require_permission(context, Permission.VIEW)
    return await PilotService(session).dashboard(context.tenant_id)


@router.get("/support/dead-letters")
async def support_dead_letters(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    require_permission(context, Permission.MANAGE_INTEGRATIONS)
    items = (
        await session.scalars(
            select(DeadLetterModel).where(DeadLetterModel.tenant_id == context.tenant_id)
        )
    ).all()
    return [
        {
            "id": item.id,
            "operation": item.operation,
            "error": item.error_code,
            "attempts": item.attempts,
            "status": item.status,
        }
        for item in items
    ]
