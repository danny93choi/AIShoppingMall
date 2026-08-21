"""tenant encrypted credentials

Revision ID: c1a8f24d9e70
Revises: b0f6d24e7a53
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1a8f24d9e70"
down_revision: str | None = "b0f6d24e7a53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_credentials",
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("masked_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider"),
    )
    op.create_index("ix_tenant_credentials_tenant_id", "tenant_credentials", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("tenant_credentials")
