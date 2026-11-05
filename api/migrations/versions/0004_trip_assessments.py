"""trip assessment audit table

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-05
Phase: expand (additive only: one new table)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trip_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("booking_id", sa.String(16), nullable=False),
        sa.Column("relevance", sa.String(16), nullable=False),
        sa.Column("reasons", sa.JSON, nullable=False),
        sa.Column("rejected", sa.JSON, nullable=False),
        sa.Column("rules_version", sa.String(32), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
    )
    op.create_index("ix_trip_assessments_booking_id", "trip_assessments", ["booking_id"])


def downgrade() -> None:
    op.drop_index("ix_trip_assessments_booking_id", table_name="trip_assessments")
    op.drop_table("trip_assessments")
