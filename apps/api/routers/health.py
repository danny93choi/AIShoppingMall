import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from apps.api.dependencies import get_database_health_checker, get_redis_health_checker
from commerce_agent.infrastructure.health import HealthChecker

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"


class DependencyStatus(BaseModel):
    postgres: bool
    redis: bool


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: DependencyStatus


@router.get("/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse()


@router.get("/ready", response_model=ReadyResponse)
async def ready(
    response: Response,
    database: Annotated[HealthChecker, Depends(get_database_health_checker)],
    redis: Annotated[HealthChecker, Depends(get_redis_health_checker)],
) -> ReadyResponse:
    postgres_ready, redis_ready = await asyncio.gather(database.check(), redis.check())
    is_ready = postgres_ready and redis_ready
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(
        status="ready" if is_ready else "not_ready",
        dependencies=DependencyStatus(postgres=postgres_ready, redis=redis_ready),
    )
