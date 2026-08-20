from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.application.services.hardening import (
    IdempotencyConflictError,
    IdempotencyService,
    OutboxService,
    TenantRateLimiter,
    retry_or_dead_letter,
)
from commerce_agent.infrastructure.db.models import DeadLetterModel


async def test_idempotency_outbox_rate_limit_and_dead_letter(db_session: AsyncSession) -> None:
    tenant_id = uuid4()
    service = IdempotencyService(db_session)
    assert (
        await service.resolve(tenant_id=tenant_id, route="/webhook", key="event-1", body={"id": 1})
        is None
    )
    await service.save(
        tenant_id=tenant_id, route="/webhook", key="event-1", body={"id": 1}, response={"ok": True}
    )
    assert await service.resolve(
        tenant_id=tenant_id, route="/webhook", key="event-1", body={"id": 1}
    ) == {"ok": True}
    with pytest.raises(IdempotencyConflictError):
        await service.resolve(tenant_id=tenant_id, route="/webhook", key="event-1", body={"id": 2})
    event = await OutboxService(db_session).append(
        tenant_id=tenant_id,
        event_type="test",
        aggregate_type="candidate",
        aggregate_id=uuid4(),
        payload={"safe": True},
    )
    assert event.published_at is None
    limiter = TenantRateLimiter(2, timedelta(minutes=1))
    assert limiter.allow(tenant_id)
    assert limiter.allow(tenant_id)
    assert not limiter.allow(tenant_id)

    async def fail() -> dict[str, object]:
        raise RuntimeError("provider down")

    assert (
        await retry_or_dead_letter(
            session=db_session,
            tenant_id=tenant_id,
            operation_name="sync",
            payload={},
            operation=fail,
            max_attempts=2,
        )
        is None
    )
    count = await db_session.scalar(
        select(func.count())
        .select_from(DeadLetterModel)
        .where(DeadLetterModel.tenant_id == tenant_id)
    )
    assert count == 1
