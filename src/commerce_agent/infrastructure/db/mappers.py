from commerce_agent.domain.entities import CandidateStatus, ProductCandidate, Tenant, TenantStatus
from commerce_agent.infrastructure.db.models import ProductCandidateModel, TenantModel


def tenant_to_model(entity: Tenant) -> TenantModel:
    return TenantModel(
        id=entity.id,
        name=entity.name,
        status=entity.status.value,
        timezone=entity.timezone,
        currency=entity.currency,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def tenant_to_entity(model: TenantModel) -> Tenant:
    return Tenant(
        id=model.id,
        name=model.name,
        status=TenantStatus(model.status),
        timezone=model.timezone,
        currency=model.currency,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def candidate_to_model(entity: ProductCandidate) -> ProductCandidateModel:
    return ProductCandidateModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        canonical_name=entity.canonical_name,
        brand=entity.brand,
        category_path=entity.category_path,
        description=entity.description,
        attributes_json=entity.attributes,
        primary_image_url=entity.primary_image_url,
        source_count=entity.source_count,
        first_seen_at=entity.first_seen_at,
        last_seen_at=entity.last_seen_at,
        dedupe_key=entity.dedupe_key,
        status=entity.status.value,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def candidate_to_entity(model: ProductCandidateModel) -> ProductCandidate:
    return ProductCandidate(
        id=model.id,
        tenant_id=model.tenant_id,
        canonical_name=model.canonical_name,
        brand=model.brand,
        category_path=model.category_path,
        description=model.description,
        attributes=model.attributes_json,
        primary_image_url=model.primary_image_url,
        source_count=model.source_count,
        first_seen_at=model.first_seen_at,
        last_seen_at=model.last_seen_at,
        dedupe_key=model.dedupe_key,
        status=CandidateStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
