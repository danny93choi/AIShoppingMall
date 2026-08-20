"""pilot readiness configuration and feedback

Revision ID: b0f6d24e7a53
Revises: a9e5c13d6f42
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b0f6d24e7a53"
down_revision: str | None = "a9e5c13d6f42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    common = [
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]
    op.create_table(
        "feature_flags",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("configuration_json", postgresql.JSONB(), nullable=False),
        *common,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "key"),
    )
    op.create_index("ix_feature_flags_tenant_id", "feature_flags", ["tenant_id"])
    op.create_table(
        "tenant_pilot_configs",
        sa.Column("onboarding_status", sa.String(30), nullable=False),
        sa.Column("scoring_preset", sa.String(100), nullable=False),
        sa.Column("discovery_categories", postgresql.JSONB(), nullable=False),
        sa.Column("max_daily_candidates", sa.Integer(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        *common,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index("ix_tenant_pilot_configs_tenant_id", "tenant_pilot_configs", ["tenant_id"])
    op.create_table(
        "pilot_feedback",
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        *common,
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_pilot_feedback_rating"),
    )
    op.create_index("ix_pilot_feedback_tenant_id", "pilot_feedback", ["tenant_id"])
    op.create_index("ix_feedback_tenant_created", "pilot_feedback", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("pilot_feedback")
    op.drop_table("tenant_pilot_configs")
    op.drop_table("feature_flags")
