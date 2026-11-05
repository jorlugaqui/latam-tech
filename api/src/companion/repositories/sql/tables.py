"""SQLAlchemy Core table definitions; Alembic autogenerates revisions from this metadata.

Use portable column types only, so tables behave the same on PostgreSQL and SQLite.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
)

metadata = MetaData()

# Versioned relevance rules (design D3, D12). Rows are immutable by convention: a change is
# a new version inserted by a migration; no code path updates them.
relevance_rule_sets = Table(
    "relevance_rule_sets",
    metadata,
    Column("version", String(32), primary_key=True),
    Column("effective_from", DateTime(timezone=True), nullable=False),
    Column("effective_to", DateTime(timezone=True), nullable=True),
    Column("freshness_max_age_minutes", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

relevance_criteria = Table(
    "relevance_criteria",
    metadata,
    Column(
        "rule_set_version",
        String(32),
        ForeignKey("relevance_rule_sets.version"),
        primary_key=True,
    ),
    Column("criterion_key", String(64), primary_key=True),
    Column("enabled", Boolean, nullable=False),
    Column("tier", String(16), nullable=False),
    Column("params", JSON, nullable=False),
    CheckConstraint("tier IN ('DISRUPTIVE', 'INFORMATIONAL')", name="ck_criteria_tier"),
)

# Reference facts, not rules: IATA code to IANA time zone.
airports = Table(
    "airports",
    metadata,
    Column("iata", String(3), primary_key=True),
    Column("iana_tz", String(64), nullable=False),
)

# Append-only audit of every assessment shown to a passenger (design D15). No personal
# data. The application never updates or deletes rows; retention is indefinite in the demo.
trip_assessments = Table(
    "trip_assessments",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("booking_id", String(16), nullable=False, index=True),
    Column("relevance", String(16), nullable=False),
    Column("reasons", JSON, nullable=False),
    Column("rejected", JSON, nullable=False),
    Column("rules_version", String(32), nullable=True),
    Column("assessed_at", DateTime(timezone=True), nullable=False),
    Column("request_id", String(64), nullable=False),
)

# Our record of each human case (design D8 of add-recommendation-and-handoff). One active
# case per booking: ``active_booking_id`` holds the booking code while the case is
# REQUESTED / OPEN / INDETERMINATE and is cleared on FAILED. Being UNIQUE and nullable,
# it blocks a second active case even under concurrent requests, on SQLite and PostgreSQL.
human_cases = Table(
    "human_cases",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("booking_id", String(16), nullable=False, index=True),
    Column("active_booking_id", String(16), nullable=True, unique=True),
    Column("reason", String(32), nullable=False),
    Column("status", String(16), nullable=False),
    Column("option_id", String(16), nullable=True),
    Column("assessment_id", String(36), nullable=False),
    Column("evidence", JSON, nullable=False),
    Column("case_id", String(64), nullable=True),
    Column("queue", String(64), nullable=True),
    Column("sla_minutes", Integer, nullable=True),
    Column("request_id", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
