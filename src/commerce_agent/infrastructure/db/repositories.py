from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.domain.entities import ProductCandidate, Tenant
from commerce_agent.infrastructure.db.mappers import (
    candidate_to_entity,
    candidate_to_model,
    tenant_to_entity,
    tenant_to_model,
)
from commerce_agent.infrastructure.db.models import ProductCandidateModel, TenantModel


class SqlAlchemyTenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tenant: Tenant) -> Tenant:
        self._session.add(tenant_to_model(tenant))
        await self._session.flush()
        return tenant

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        model = await self._session.get(TenantModel, tenant_id)
        return tenant_to_entity(model) if model is not None else None


class SqlAlchemyProductCandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tenant_id: UUID, candidate: ProductCandidate) -> ProductCandidate:
        if candidate.tenant_id != tenant_id:
            raise ValueError("candidate tenant_id does not match repository tenant scope")
        self._session.add(candidate_to_model(candidate))
        await self._session.flush()
        return candidate

    async def get_by_id(self, tenant_id: UUID, candidate_id: UUID) -> ProductCandidate | None:
        statement = select(ProductCandidateModel).where(
            ProductCandidateModel.tenant_id == tenant_id,
            ProductCandidateModel.id == candidate_id,
        )
        model = await self._session.scalar(statement)
        return candidate_to_entity(model) if model is not None else None

    async def list(self, tenant_id: UUID) -> Sequence[ProductCandidate]:
        statement = (
            select(ProductCandidateModel)
            .where(ProductCandidateModel.tenant_id == tenant_id)
            .order_by(ProductCandidateModel.created_at)
        )
        models = (await self._session.scalars(statement)).all()
        return [candidate_to_entity(model) for model in models]
