from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.domain.entities import ProductCandidate, Tenant
from commerce_agent.infrastructure.db.repositories import (
    SqlAlchemyProductCandidateRepository,
    SqlAlchemyTenantRepository,
)


async def test_candidate_read_is_isolated_by_tenant(db_session: AsyncSession) -> None:
    tenant_a = Tenant(name="Tenant A", currency="KRW", timezone="Asia/Seoul")
    tenant_b = Tenant(name="Tenant B", currency="KRW", timezone="Asia/Seoul")
    tenant_repository = SqlAlchemyTenantRepository(db_session)
    await tenant_repository.add(tenant_a)
    await tenant_repository.add(tenant_b)
    candidate = ProductCandidate(
        tenant_id=tenant_a.id,
        canonical_name="Insulated tumbler",
        dedupe_key=f"tumbler-{uuid4()}",
    )
    repository = SqlAlchemyProductCandidateRepository(db_session)
    await repository.add(tenant_a.id, candidate)

    assert await repository.get_by_id(tenant_a.id, candidate.id) == candidate
    assert await repository.get_by_id(tenant_b.id, candidate.id) is None
    assert list(await repository.list(tenant_b.id)) == []


async def test_repository_rejects_mismatched_tenant_scope(db_session: AsyncSession) -> None:
    candidate = ProductCandidate(
        tenant_id=uuid4(), canonical_name="Candidate", dedupe_key=f"candidate-{uuid4()}"
    )
    repository = SqlAlchemyProductCandidateRepository(db_session)
    with pytest.raises(ValueError, match="tenant_id"):
        await repository.add(uuid4(), candidate)
