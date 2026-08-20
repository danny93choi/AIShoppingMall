from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from apps.api.tenant import get_tenant_context
from commerce_agent.application.tenant_context import TenantContext
from commerce_agent.application.workflows.discovery import DiscoveryWorkflow
from commerce_agent.infrastructure.db.models import (
    AgentRunModel,
    CommerceConnectionModel,
    JobModel,
    MarketingDraftModel,
    OpportunityScoreModel,
    ProductCandidateModel,
    RecommendationModel,
)
from commerce_agent.integrations.commerce.mock import MockCommerceAdapter
from commerce_agent.integrations.trend_sources.mock import MockTrendSource
from commerce_agent.security.rbac import Permission, require_permission

ROOT = Path(__file__).resolve().parents[3]
router = APIRouter(tags=["admin"])


@router.get("/admin", include_in_schema=False)
async def admin_page() -> FileResponse:
    return FileResponse(ROOT / "apps/api/static/admin.html")


@router.get("/api/v1/admin/overview")
async def admin_overview(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    require_permission(context, Permission.VIEW)
    tenant_id = context.tenant_id
    connections = list(
        (
            await session.scalars(
                select(CommerceConnectionModel).where(
                    CommerceConnectionModel.tenant_id == tenant_id
                )
            )
        ).all()
    )
    candidates = list(
        (
            await session.scalars(
                select(ProductCandidateModel)
                .where(ProductCandidateModel.tenant_id == tenant_id)
                .order_by(ProductCandidateModel.created_at.desc())
                .limit(50)
            )
        ).all()
    )
    scores = list(
        (
            await session.scalars(
                select(OpportunityScoreModel).where(OpportunityScoreModel.tenant_id == tenant_id)
            )
        ).all()
    )
    score_by_id = {item.id: item for item in scores}
    candidate_name_by_id = {item.id: item.canonical_name for item in candidates}
    recommendations = list(
        (
            await session.scalars(
                select(RecommendationModel)
                .where(RecommendationModel.tenant_id == tenant_id)
                .order_by(RecommendationModel.rank)
                .limit(20)
            )
        ).all()
    )
    jobs = list(
        (
            await session.scalars(
                select(JobModel)
                .where(JobModel.tenant_id == tenant_id)
                .order_by(JobModel.updated_at.desc())
                .limit(20)
            )
        ).all()
    )
    runs = list(
        (
            await session.scalars(
                select(AgentRunModel)
                .where(AgentRunModel.tenant_id == tenant_id)
                .order_by(AgentRunModel.updated_at.desc())
                .limit(20)
            )
        ).all()
    )
    drafts = list(
        (
            await session.scalars(
                select(MarketingDraftModel).where(MarketingDraftModel.tenant_id == tenant_id)
            )
        ).all()
    )
    return {
        "connections": [
            {
                "id": item.id,
                "provider": item.provider,
                "name": item.display_name,
                "status": item.status,
                "last_sync_at": item.last_sync_at,
            }
            for item in connections
        ],
        "candidates": [
            {
                "id": item.id,
                "name": item.canonical_name,
                "category": ".".join(item.category_path),
                "status": item.status,
                "source_count": item.source_count,
            }
            for item in candidates
        ],
        "recommendations": [
            {
                "id": item.id,
                "rank": item.rank,
                "status": item.status,
                "summary": item.summary,
                "candidate_name": candidate_name_by_id.get(item.candidate_id, "Unknown"),
                "score": str(score_by_id[item.score_id].final_score)
                if item.score_id in score_by_id
                else None,
                "breakdown": score_by_id[item.score_id].components_json
                if item.score_id in score_by_id
                else {},
            }
            for item in recommendations
        ],
        "jobs": [
            {
                "id": item.id,
                "status": item.status,
                "progress": item.progress_percent,
                "step": item.current_step,
                "warnings": item.warnings_json,
                "errors": item.errors_json,
                "updated_at": item.updated_at,
            }
            for item in jobs
        ],
        "agent_runs": [
            {
                "id": item.id,
                "agent": item.agent_name,
                "status": item.status,
                "model": item.model_name,
                "cost": str(item.estimated_cost),
                "error": item.error_message,
            }
            for item in runs
        ],
        "marketing_drafts": [
            {
                "id": item.id,
                "recommendation_id": item.recommendation_id,
                "status": item.status,
                "content": item.content_json,
                "claims_to_verify": item.claims_to_verify,
                "risks": item.risks_json,
            }
            for item in drafts
        ],
    }


@router.post("/api/v1/admin/discovery")
async def run_admin_discovery(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    require_permission(context, Permission.RUN_DISCOVERY)
    connection = await session.scalar(
        select(CommerceConnectionModel)
        .where(CommerceConnectionModel.tenant_id == context.tenant_id)
        .limit(1)
    )
    if connection is None:
        raise HTTPException(status_code=409, detail="connect a shop before discovery")
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
        tenant_id=context.tenant_id,
        connection_id=connection.id,
        categories=[],
        idempotency_key="admin-discovery",
        top_n=5,
    )
    return summary.model_dump(mode="json")
