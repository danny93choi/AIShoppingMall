"""approval audit and marketing drafts

Revision ID: f8d4b02c5e31
Revises: e7c3a91b4d20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8d4b02c5e31"
down_revision: str | None = "e7c3a91b4d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index(
        "ix_audit_tenant_resource",
        "audit_events",
        ["tenant_id", "resource_type", "resource_id"],
    )
    op.create_table(
        "marketing_drafts",
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("content_json", postgresql.JSONB(), nullable=False),
        sa.Column("claims_to_verify", postgresql.JSONB(), nullable=False),
        sa.Column("risks_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "recommendation_id"),
    )
    op.create_index("ix_marketing_drafts_tenant_id", "marketing_drafts", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("marketing_drafts")
    op.drop_table("audit_events")
