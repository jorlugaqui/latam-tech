"""seed relevance rule set REL-2026-09 and airport reference data

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-04
Phase: migrate (data only; the schema is unchanged)

Thresholds are documented assumptions to be confirmed by PM + Ops (proposal, Assumptions).
A later change to the rules is a new version in a new revision; this one is never edited.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VERSION = "REL-2026-09"
AIRPORTS = [
    {"iata": "SCL", "iana_tz": "America/Santiago"},
    {"iata": "LIM", "iana_tz": "America/Lima"},
    {"iata": "MEX", "iana_tz": "America/Mexico_City"},
]
CRITERIA = [
    ("CANCELLATION", "DISRUPTIVE", {}),
    ("MISSED_CONNECTION", "DISRUPTIVE", {"default_mct_minutes": 60, "mct_by_airport": {"MEX": 90}}),
    ("LONG_DELAY", "DISRUPTIVE", {"min_delay_minutes": 120}),
    ("MINOR_DELAY", "INFORMATIONAL", {"min_delay_minutes": 15}),
    ("GATE_CHANGE", "INFORMATIONAL", {}),
]

# Self-contained table stubs: a migration must not import application code that may change.
rule_sets = sa.table(
    "relevance_rule_sets",
    sa.column("version", sa.String),
    sa.column("effective_from", sa.DateTime(timezone=True)),
    sa.column("effective_to", sa.DateTime(timezone=True)),
    sa.column("freshness_max_age_minutes", sa.Integer),
    sa.column("created_at", sa.DateTime(timezone=True)),
)
criteria = sa.table(
    "relevance_criteria",
    sa.column("rule_set_version", sa.String),
    sa.column("criterion_key", sa.String),
    sa.column("enabled", sa.Boolean),
    sa.column("tier", sa.String),
    sa.column("params", sa.JSON),
)
airports = sa.table("airports", sa.column("iata", sa.String), sa.column("iana_tz", sa.String))


def upgrade() -> None:
    op.bulk_insert(
        rule_sets,
        [
            {
                "version": VERSION,
                "effective_from": datetime(2026, 9, 1, tzinfo=UTC),
                "effective_to": None,
                "freshness_max_age_minutes": 30,
                "created_at": datetime(2026, 11, 4, tzinfo=UTC),
            }
        ],
    )
    op.bulk_insert(
        criteria,
        [
            {
                "rule_set_version": VERSION,
                "criterion_key": key,
                "enabled": True,
                "tier": tier,
                "params": params,
            }
            for key, tier, params in CRITERIA
        ],
    )
    op.bulk_insert(airports, AIRPORTS)


def downgrade() -> None:
    op.execute(criteria.delete().where(criteria.c.rule_set_version == VERSION))
    op.execute(rule_sets.delete().where(rule_sets.c.version == VERSION))
    op.execute(airports.delete().where(airports.c.iata.in_([a["iata"] for a in AIRPORTS])))
