"""relevance rules and airport reference tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-04
Phase: expand (additive only: three new tables, nothing renamed or dropped)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "relevance_rule_sets",
        sa.Column("version", sa.String(32), primary_key=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("freshness_max_age_minutes", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "relevance_criteria",
        sa.Column(
            "rule_set_version",
            sa.String(32),
            sa.ForeignKey("relevance_rule_sets.version"),
            primary_key=True,
        ),
        sa.Column("criterion_key", sa.String(64), primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("params", sa.JSON, nullable=False),
        sa.CheckConstraint("tier IN ('DISRUPTIVE', 'INFORMATIONAL')", name="ck_criteria_tier"),
    )
    op.create_table(
        "airports",
        sa.Column("iata", sa.String(3), primary_key=True),
        sa.Column("iana_tz", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("airports")
    op.drop_table("relevance_criteria")
    op.drop_table("relevance_rule_sets")
