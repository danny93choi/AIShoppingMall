from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from commerce_agent.domain.common import Entity, TenantOwnedEntity


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class CandidateStatus(StrEnum):
    DISCOVERED = "discovered"
    ANALYZING = "analyzing"
    SCORED = "scored"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


@dataclass(kw_only=True)
class Tenant(Entity):
    name: str
    status: TenantStatus = TenantStatus.ACTIVE
    timezone: str = "UTC"
    currency: str = "USD"


@dataclass(kw_only=True)
class CommerceConnection(TenantOwnedEntity):
    provider: str
    external_shop_id: str
    display_name: str
    status: str = "active"
    credential_ref: str | None = None
    scopes: list[str] = field(default_factory=list)
    last_sync_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class ProductCandidate(TenantOwnedEntity):
    canonical_name: str
    dedupe_key: str
    brand: str | None = None
    category_path: list[str] = field(default_factory=list)
    description: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    primary_image_url: str | None = None
    source_count: int = 0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    status: CandidateStatus = CandidateStatus.DISCOVERED


@dataclass(kw_only=True)
class ProductSourceObservation(TenantOwnedEntity):
    candidate_id: UUID
    source_type: str
    source_name: str
    observed_at: datetime
    external_id: str | None = None
    url: str | None = None
    title_raw: str | None = None
    price_raw: Decimal | None = None
    currency: str | None = None
    raw_payload_ref: str | None = None


@dataclass(kw_only=True)
class SupplierCandidate(TenantOwnedEntity):
    product_candidate_id: UUID
    supplier_name: str
    source: str
    unit_cost: Decimal | None = None
    currency: str | None = None
    moq: int | None = None
    data_confidence: Decimal | None = None


@dataclass(kw_only=True)
class OpportunityScore(TenantOwnedEntity):
    candidate_id: UUID
    version: str
    final_score: Decimal
    components: dict[str, Decimal] = field(default_factory=dict)
    weights: dict[str, Decimal] = field(default_factory=dict)
    features: dict[str, Any] = field(default_factory=dict)
    explanation: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class Recommendation(TenantOwnedEntity):
    candidate_id: UUID
    score_id: UUID
    rank: int
    recommendation_type: str
    summary: str
    status: str = "pending"


@dataclass(kw_only=True)
class Approval(TenantOwnedEntity):
    resource_type: str
    resource_id: UUID
    action: str
    requested_by: UUID
    status: str = "pending"
    decided_by: UUID | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None


@dataclass(kw_only=True)
class Job(TenantOwnedEntity):
    correlation_id: UUID
    idempotency_key: str
    job_type: str
    status: str = "queued"
    progress_percent: int = 0
    current_step: str | None = None


@dataclass(kw_only=True)
class AgentRun(TenantOwnedEntity):
    agent_name: str
    agent_version: str
    workflow_name: str
    correlation_id: UUID
    status: str = "running"
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] | None = None
    prompt_version: str | None = None
