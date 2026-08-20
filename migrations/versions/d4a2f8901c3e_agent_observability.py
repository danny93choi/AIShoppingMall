"""agent observability

Revision ID: d4a2f8901c3e
Revises: f345941f9f82
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4a2f8901c3e"
down_revision: str | None = "f345941f9f82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("prompt_name", sa.String(200), nullable=True))
    op.add_column("agent_runs", sa.Column("prompt_hash", sa.String(64), nullable=True))
    op.add_column("agent_runs", sa.Column("model_provider", sa.String(50), nullable=True))
    op.add_column("agent_runs", sa.Column("model_name", sa.String(100), nullable=True))
    op.add_column(
        "agent_runs", sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "agent_runs", sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "agent_runs",
        sa.Column("estimated_cost", sa.Numeric(12, 6), server_default="0", nullable=False),
    )
    op.add_column("agent_runs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "agent_runs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("agent_runs", sa.Column("error_code", sa.String(100), nullable=True))
    op.add_column("agent_runs", sa.Column("error_message", sa.Text(), nullable=True))
    op.execute("UPDATE agent_runs SET started_at = created_at WHERE started_at IS NULL")
    op.alter_column("agent_runs", "started_at", nullable=False)
    op.create_unique_constraint("uq_agent_run_tenant_id", "agent_runs", ["tenant_id", "id"])
    op.create_index(
        "ix_agent_run_tenant_correlation", "agent_runs", ["tenant_id", "correlation_id"]
    )
    op.create_table(
        "tool_calls",
        sa.Column("agent_run_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(200), nullable=False),
        sa.Column("arguments_json", postgresql.JSONB(), nullable=False),
        sa.Column("result_summary_json", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "agent_run_id"], ["agent_runs.tenant_id", "agent_runs.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_call_tenant_run", "tool_calls", ["tenant_id", "agent_run_id"])
    op.create_index("ix_tool_calls_tenant_id", "tool_calls", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("tool_calls")
    op.drop_index("ix_agent_run_tenant_correlation", table_name="agent_runs")
    op.drop_constraint("uq_agent_run_tenant_id", "agent_runs", type_="unique")
    for column in (
        "error_message",
        "error_code",
        "completed_at",
        "started_at",
        "estimated_cost",
        "output_tokens",
        "input_tokens",
        "model_name",
        "model_provider",
        "prompt_hash",
        "prompt_name",
    ):
        op.drop_column("agent_runs", column)
