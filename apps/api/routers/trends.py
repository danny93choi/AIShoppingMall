from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from apps.api.tenant import get_tenant_context
from commerce_agent.application.services.trend_ingestion import (
    TrendIngestionResult,
    TrendIngestionService,
)
from commerce_agent.application.tenant_context import TenantContext
from commerce_agent.integrations.trend_sources.base import TrendQuery
from commerce_agent.integrations.trend_sources.mock import MockTrendSource

router = APIRouter(prefix="/api/v1/trends", tags=["trend-ingestion"])
FIXTURE_ROOT = Path(__file__).parents[3] / "fixtures" / "trend_sources"


@router.post("/mock-ingest", response_model=TrendIngestionResult)
async def ingest_mock_trends(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    query: TrendQuery | None = None,
) -> TrendIngestionResult:
    sources = [
        MockTrendSource("mock_trend_a", FIXTURE_ROOT / "mock_trend_a.json"),
        MockTrendSource("mock_trend_b", FIXTURE_ROOT / "mock_trend_b.json"),
    ]
    return await TrendIngestionService(session).ingest(
        context.tenant_id, sources, query or TrendQuery()
    )
