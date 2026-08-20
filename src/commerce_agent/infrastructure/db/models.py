from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from commerce_agent.infrastructure.db.base import AuditMixin, Base, TenantOwnedMixin


class TenantModel(AuditMixin, Base):
    __tablename__ = "tenants"
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), index=True)
    timezone: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(3))


class CommerceConnectionModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "commerce_connections"
    __table_args__ = (UniqueConstraint("tenant_id", "provider", "external_shop_id"),)
    provider: Mapped[str] = mapped_column(String(30))
    external_shop_id: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    credential_ref: Mapped[str | None] = mapped_column(String(500))
    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class ProductCandidateModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "product_candidates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_candidate_tenant_dedupe"),
        Index("ix_candidate_tenant_status_seen", "tenant_id", "status", "last_seen_at"),
        UniqueConstraint("tenant_id", "id", name="uq_candidate_tenant_id"),
    )
    canonical_name: Mapped[str] = mapped_column(String(500))
    brand: Mapped[str | None] = mapped_column(String(200))
    category_path: Mapped[list[str]] = mapped_column(JSONB, default=list)
    description: Mapped[str | None] = mapped_column(Text)
    attributes_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    primary_image_url: Mapped[str | None] = mapped_column(Text)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedupe_key: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30))


class ProductObservationModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "product_source_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "candidate_id"],
            ["product_candidates.tenant_id", "product_candidates.id"],
        ),
        Index("ix_observation_tenant_candidate", "tenant_id", "candidate_id"),
    )
    candidate_id: Mapped[UUID]
    source_type: Mapped[str] = mapped_column(String(50))
    source_name: Mapped[str] = mapped_column(String(100))
    external_id: Mapped[str | None] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(Text)
    title_raw: Mapped[str | None] = mapped_column(Text)
    price_raw: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_payload_ref: Mapped[str | None] = mapped_column(Text)


class SupplierCandidateModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "supplier_candidates"
    product_candidate_id: Mapped[UUID]
    supplier_name: Mapped[str] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(100))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    moq: Mapped[int | None]
    data_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))


class OpportunityScoreModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "opportunity_scores"
    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_id", "version", name="uq_score_candidate_version"),
    )
    candidate_id: Mapped[UUID]
    version: Mapped[str] = mapped_column(String(50))
    final_score: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    components_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    weights_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    features_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSONB)


class RecommendationModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        Index("ix_recommendation_tenant_status", "tenant_id", "status"),
        UniqueConstraint("tenant_id", "score_id", name="uq_recommendation_score"),
    )
    candidate_id: Mapped[UUID]
    score_id: Mapped[UUID]
    rank: Mapped[int]
    recommendation_type: Mapped[str] = mapped_column(String(30))
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))


class ApprovalModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "approvals"
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[UUID]
    action: Mapped[str] = mapped_column(String(100))
    requested_by: Mapped[UUID]
    status: Mapped[str] = mapped_column(String(30))
    decided_by: Mapped[UUID | None]
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class AuditEventModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_tenant_resource", "tenant_id", "resource_type", "resource_id"),
    )
    event_type: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[UUID]
    actor_id: Mapped[UUID]
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB)


class MarketingDraftModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "marketing_drafts"
    __table_args__ = (UniqueConstraint("tenant_id", "recommendation_id"),)
    recommendation_id: Mapped[UUID]
    schema_version: Mapped[str] = mapped_column(String(20))
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    claims_to_verify: Mapped[list[str]] = mapped_column(JSONB)
    risks_json: Mapped[list[str]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30))


@event.listens_for(AuditEventModel, "before_update")
@event.listens_for(AuditEventModel, "before_delete")
def _prevent_audit_mutation(*_args: Any) -> None:
    raise ValueError("audit events are immutable")


class JobModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key"),)
    correlation_id: Mapped[UUID]
    idempotency_key: Mapped[str] = mapped_column(String(300))
    job_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str | None] = mapped_column(String(200))
    completed_steps: Mapped[list[str]] = mapped_column(JSONB, default=list)
    warnings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    errors_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRunModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_agent_run_tenant_id"),
        Index("ix_agent_run_tenant_correlation", "tenant_id", "correlation_id"),
    )
    agent_name: Mapped[str] = mapped_column(String(100))
    agent_version: Mapped[str] = mapped_column(String(50))
    workflow_name: Mapped[str] = mapped_column(String(100))
    correlation_id: Mapped[UUID]
    status: Mapped[str] = mapped_column(String(30))
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    prompt_name: Mapped[str | None] = mapped_column(String(200))
    prompt_version: Mapped[str | None] = mapped_column(String(100))
    prompt_hash: Mapped[str | None] = mapped_column(String(64))
    model_provider: Mapped[str | None] = mapped_column(String(50))
    model_name: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)


class ToolCallModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "tool_calls"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "agent_run_id"], ["agent_runs.tenant_id", "agent_runs.id"]
        ),
        Index("ix_tool_call_tenant_run", "tenant_id", "agent_run_id"),
    )
    agent_run_id: Mapped[UUID]
    tool_name: Mapped[str] = mapped_column(String(200))
    arguments_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)


class OutboxEventModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_tenant_unpublished", "tenant_id", "published_at"),)
    event_type: Mapped[str] = mapped_column(String(100))
    aggregate_type: Mapped[str] = mapped_column(String(100))
    aggregate_id: Mapped[UUID]
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)


class IdempotencyRecordModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("tenant_id", "route", "key"),)
    route: Mapped[str] = mapped_column(String(300))
    key: Mapped[str] = mapped_column(String(300))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_json: Mapped[dict[str, Any]] = mapped_column(JSONB)


class DeadLetterModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "dead_letters"
    __table_args__ = (Index("ix_dead_letter_tenant_status", "tenant_id", "status"),)
    operation: Mapped[str] = mapped_column(String(200))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    error_code: Mapped[str] = mapped_column(String(100))
    error_message: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))


class ShopProductSnapshotModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "shop_product_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "connection_id", "external_product_id", name="uq_shop_product_external"
        ),
        Index("ix_shop_product_tenant_connection", "tenant_id", "connection_id"),
    )
    connection_id: Mapped[UUID]
    external_product_id: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(500))
    category_path: Mapped[list[str]] = mapped_column(JSONB)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(3))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    inventory_quantity: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(30))
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SalesAggregateModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "sales_aggregates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "connection_id", "external_product_id", "date", name="uq_sales_daily"
        ),
        Index("ix_sales_tenant_connection_date", "tenant_id", "connection_id", "date"),
    )
    connection_id: Mapped[UUID]
    external_product_id: Mapped[str] = mapped_column(String(300))
    date: Mapped[date] = mapped_column(Date)
    orders: Mapped[int]
    units: Mapped[int]
    gross_revenue: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    estimated_cogs: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    gross_margin: Mapped[Decimal] = mapped_column(Numeric(18, 4))


class ShopIntelligenceProfileModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "shop_intelligence_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "connection_id", name="uq_shop_profile"),)
    connection_id: Mapped[UUID]
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sales_window_days: Mapped[int]
    category_revenue_share: Mapped[dict[str, Any]] = mapped_column(JSONB)
    category_unit_share: Mapped[dict[str, Any]] = mapped_column(JSONB)
    asp_percentiles: Mapped[dict[str, Any]] = mapped_column(JSONB)
    top_product_attributes: Mapped[dict[str, Any]] = mapped_column(JSONB)
    repeat_purchase_proxy: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    inventory_turnover_by_category: Mapped[dict[str, Any]] = mapped_column(JSONB)
    seasonality_features: Mapped[dict[str, Any]] = mapped_column(JSONB)
    data_coverage: Mapped[Decimal] = mapped_column(Numeric(5, 4))


class RawTrendObservationModel(TenantOwnedMixin, AuditMixin, Base):
    __tablename__ = "raw_trend_observations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "source_id", name="uq_raw_trend_source_item"),
        Index("ix_raw_trend_tenant_candidate", "tenant_id", "candidate_id"),
    )
    candidate_id: Mapped[UUID | None]
    source: Mapped[str] = mapped_column(String(100))
    source_id: Mapped[str] = mapped_column(String(300))
    title_raw: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    observed_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB)
