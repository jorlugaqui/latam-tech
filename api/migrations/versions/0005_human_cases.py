"""human cases (local record, one active case per booking)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-05
Phase: expand (additive only: one new table)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "human_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("booking_id", sa.String(16), nullable=False),
        sa.Column("active_booking_id", sa.String(16), nullable=True),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("option_id", sa.String(16), nullable=True),
        sa.Column("assessment_id", sa.String(36), nullable=False),
        sa.Column("evidence", sa.JSON, nullable=False),
        sa.Column("case_id", sa.String(64), nullable=True),
        sa.Column("queue", sa.String(64), nullable=True),
        sa.Column("sla_minutes", sa.Integer, nullable=True),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("active_booking_id", name="uq_human_cases_active_booking_id"),
    )
    op.create_index("ix_human_cases_booking_id", "human_cases", ["booking_id"])


def downgrade() -> None:
    op.drop_index("ix_human_cases_booking_id", table_name="human_cases")
    op.drop_table("human_cases")
