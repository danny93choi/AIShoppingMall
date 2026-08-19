"""Tenant-scope the recommendation status index.

Revision ID: b6f2d4a1c8e0
Revises: 964ff1c07e2b
Create Date: 2026-08-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b6f2d4a1c8e0"
down_revision: str | None = "964ff1c07e2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_recommendations_status", table_name="recommendations")
    op.create_index(
        "ix_recommendation_tenant_status",
        "recommendations",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_recommendation_tenant_status", table_name="recommendations")
    op.create_index("ix_recommendations_status", "recommendations", ["status"])
