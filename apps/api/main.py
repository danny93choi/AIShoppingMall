from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.routers.health import router as health_router
from apps.api.routers.integrations import router as integrations_router
from apps.api.routers.recommendations import router as recommendations_router
from apps.api.routers.trends import router as trends_router
from commerce_agent.config.settings import get_settings
from commerce_agent.infrastructure.cache.health import RedisHealthChecker
from commerce_agent.infrastructure.db.health import DatabaseHealthChecker
from commerce_agent.infrastructure.db.session import create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.database_health = DatabaseHealthChecker(settings.database_url)
    app.state.redis_health = RedisHealthChecker(settings.redis_url)
    app.state.session_factory = create_session_factory(settings.database_url)
    yield
    await app.state.database_health.close()
    await app.state.redis_health.close()


def create_app() -> FastAPI:
    application = FastAPI(
        title="AI Commerce Agent API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(health_router)
    application.include_router(integrations_router)
    application.include_router(trends_router)
    application.include_router(recommendations_router)
    return application


app = create_app()
