import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.domain.common import utc_now
from commerce_agent.infrastructure.db.models import (
    DeadLetterModel,
    IdempotencyRecordModel,
    OutboxEventModel,
)

Operation = Callable[[], Awaitable[dict[str, Any]]]


class IdempotencyConflictError(ValueError):
    pass


class IdempotencyService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(
        self, *, tenant_id: UUID, route: str, key: str, body: dict[str, Any]
    ) -> dict[str, Any] | None:
        request_hash = _hash(body)
        record = await self._session.scalar(
            select(IdempotencyRecordModel).where(
                IdempotencyRecordModel.tenant_id == tenant_id,
                IdempotencyRecordModel.route == route,
                IdempotencyRecordModel.key == key,
            )
        )
        if record is None:
            return None
        if record.request_hash != request_hash:
            raise IdempotencyConflictError("idempotency key reused with a different request")
        return record.response_json

    async def save(
        self,
        *,
        tenant_id: UUID,
        route: str,
        key: str,
        body: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        now = utc_now()
        self._session.add(
            IdempotencyRecordModel(
                id=uuid4(),
                tenant_id=tenant_id,
                route=route,
                key=key,
                request_hash=_hash(body),
                response_json=response,
                created_at=now,
                updated_at=now,
            )
        )
        await self._session.flush()


class OutboxService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        *,
        tenant_id: UUID,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: dict[str, Any],
    ) -> OutboxEventModel:
        now = utc_now()
        event = OutboxEventModel(
            id=uuid4(),
            tenant_id=tenant_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload_json=payload,
            published_at=None,
            attempt_count=0,
            created_at=now,
            updated_at=now,
        )
        self._session.add(event)
        await self._session.flush()
        return event


class TenantRateLimiter:
    def __init__(self, limit: int, window: timedelta) -> None:
        self._limit = limit
        self._window = window
        self._requests: dict[UUID, deque[datetime]] = defaultdict(deque)

    def allow(self, tenant_id: UUID, now: datetime | None = None) -> bool:
        current = now or utc_now()
        requests = self._requests[tenant_id]
        cutoff = current - self._window
        while requests and requests[0] <= cutoff:
            requests.popleft()
        if len(requests) >= self._limit:
            return False
        requests.append(current)
        return True


async def retry_or_dead_letter(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    operation_name: str,
    payload: dict[str, Any],
    operation: Operation,
    max_attempts: int = 3,
) -> dict[str, Any] | None:
    last_error: Exception | None = None
    for _attempt in range(1, max_attempts + 1):
        try:
            return await operation()
        except Exception as error:
            last_error = error
    assert last_error is not None
    now = utc_now()
    session.add(
        DeadLetterModel(
            id=uuid4(),
            tenant_id=tenant_id,
            operation=operation_name,
            payload_json=payload,
            error_code=type(last_error).__name__,
            error_message=str(last_error)[:2000],
            attempts=max_attempts,
            status="pending",
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()
    return None


def _hash(body: dict[str, Any]) -> str:
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
