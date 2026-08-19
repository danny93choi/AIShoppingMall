from typing import Literal

from apps.api.dependencies import get_database_health_checker, get_redis_health_checker
from fastapi import FastAPI
from httpx import AsyncClient


class StubHealthChecker:
    def __init__(self, result: bool) -> None:
        self._result = result

    async def check(self) -> bool:
        return self._result

    async def close(self) -> None:
        return None


def override_health(app: FastAPI, *, database: bool, redis: bool) -> None:
    app.dependency_overrides[get_database_health_checker] = lambda: StubHealthChecker(database)
    app.dependency_overrides[get_redis_health_checker] = lambda: StubHealthChecker(redis)


async def test_live(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_when_all_dependencies_are_healthy(app: FastAPI, client: AsyncClient) -> None:
    override_health(app, database=True, redis=True)
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {"postgres": True, "redis": True},
    }


async def test_not_ready_reports_failed_dependency(app: FastAPI, client: AsyncClient) -> None:
    override_health(app, database=False, redis=True)
    response = await client.get("/health/ready")
    assert response.status_code == 503
    payload: dict[str, Literal["not_ready"] | dict[str, bool]] = response.json()
    assert payload == {
        "status": "not_ready",
        "dependencies": {"postgres": False, "redis": True},
    }
