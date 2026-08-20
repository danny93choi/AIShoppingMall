from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_app_settings, get_db_session
from apps.api.tenant import get_tenant_context
from commerce_agent.application.services.approvals import ApprovalDecision, ApprovalService
from commerce_agent.application.tenant_context import TenantContext
from commerce_agent.config.settings import Settings
from commerce_agent.infrastructure.db.models import MarketingDraftModel

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


class DecisionRequest(BaseModel):
    note: str | None = None


def _require_operator(context: TenantContext) -> None:
    if not context.roles.intersection({"owner", "admin", "operator"}):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="operator role required")


@router.post("/recommendations/{recommendation_id}/marketing-draft")
async def create_marketing_draft(
    recommendation_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, Any]:
    _require_operator(context)
    try:
        draft = await ApprovalService(session).create_marketing_draft(
            tenant_id=context.tenant_id,
            actor_id=context.actor_id,
            recommendation_id=recommendation_id,
            allow_before_approval=settings.allow_marketing_draft_before_approval,
        )
    except (ValueError, PermissionError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"id": draft.id, "status": draft.status, "claims_to_verify": draft.claims_to_verify}


@router.post("/recommendations/{recommendation_id}/{decision}")
async def decide_recommendation(
    recommendation_id: UUID,
    decision: str,
    body: DecisionRequest,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    _require_operator(context)
    if decision not in {"approve", "reject", "defer"}:
        raise HTTPException(status_code=404, detail="unsupported decision")
    status_value = {"approve": "approved", "reject": "rejected", "defer": "deferred"}[decision]
    try:
        recommendation = await ApprovalService(session).decide(
            tenant_id=context.tenant_id,
            actor_id=context.actor_id,
            decision=ApprovalDecision(
                recommendation_id=recommendation_id, status=status_value, note=body.note
            ),
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"id": recommendation.id, "status": recommendation.status}


@router.get("/marketing-drafts/{draft_id}")
async def get_marketing_draft(
    draft_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    draft = await session.scalar(
        select(MarketingDraftModel).where(
            MarketingDraftModel.tenant_id == context.tenant_id,
            MarketingDraftModel.id == draft_id,
        )
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="marketing draft not found")
    return {
        "id": draft.id,
        "content": draft.content_json,
        "claims_to_verify": draft.claims_to_verify,
        "risks": draft.risks_json,
    }
