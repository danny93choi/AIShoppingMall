from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from commerce_agent.config.settings import Settings
from commerce_agent.infrastructure.health import HealthChecker


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_database_health_checker(request: Request) -> HealthChecker:
    return request.app.state.database_health  # type: ignore[no-any-return]


def get_redis_health_checker(request: Request) -> HealthChecker:
    return request.app.state.redis_health  # type: ignore[no-any-return]


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session, session.begin():
        yield session
