"""discovery job state and idempotent recommendations

Revision ID: e7c3a91b4d20
Revises: d4a2f8901c3e
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7c3a91b4d20"
down_revision: str | None = "d4a2f8901c3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("completed_steps", postgresql.JSONB(), server_default="[]", nullable=False),
    )
    op.add_column(
        "jobs", sa.Column("warnings_json", postgresql.JSONB(), server_default="[]", nullable=False)
    )
    op.add_column(
        "jobs", sa.Column("errors_json", postgresql.JSONB(), server_default="[]", nullable=False)
    )
    op.add_column(
        "jobs", sa.Column("summary_json", postgresql.JSONB(), server_default="{}", nullable=False)
    )
    op.add_column("jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(
        "uq_score_candidate_version",
        "opportunity_scores",
        ["tenant_id", "candidate_id", "version"],
    )
    op.create_unique_constraint(
        "uq_recommendation_score", "recommendations", ["tenant_id", "score_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_recommendation_score", "recommendations", type_="unique")
    op.drop_constraint("uq_score_candidate_version", "opportunity_scores", type_="unique")
    for column in (
        "heartbeat_at",
        "completed_at",
        "started_at",
        "summary_json",
        "errors_json",
        "warnings_json",
        "completed_steps",
    ):
        op.drop_column("jobs", column)
