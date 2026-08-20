"""hardening outbox idempotency and dead letters

Revision ID: a9e5c13d6f42
Revises: f8d4b02c5e31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9e5c13d6f42"
down_revision: str | None = "f8d4b02c5e31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common() -> list[sa.Column[object]]:
    return [
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("aggregate_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_tenant_id", "outbox_events", ["tenant_id"])
    op.create_index("ix_outbox_tenant_unpublished", "outbox_events", ["tenant_id", "published_at"])
    op.create_table(
        "idempotency_records",
        sa.Column("route", sa.String(300), nullable=False),
        sa.Column("key", sa.String(300), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_json", postgresql.JSONB(), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "route", "key"),
    )
    op.create_index("ix_idempotency_records_tenant_id", "idempotency_records", ["tenant_id"])
    op.create_table(
        "dead_letters",
        sa.Column("operation", sa.String(200), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dead_letters_tenant_id", "dead_letters", ["tenant_id"])
    op.create_index("ix_dead_letter_tenant_status", "dead_letters", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_table("dead_letters")
    op.drop_table("idempotency_records")
    op.drop_table("outbox_events")
