"""Spec trip-status: every assessment is recorded, append-only, without personal data."""

from datetime import UTC
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, select

from companion.ports.audit import AssessmentNotRecorded
from companion.repositories.sql.assessments import SqlAssessmentLog
from companion.repositories.sql.tables import trip_assessments
from companion.schemas.assessment import Assessment
from companion.schemas.tools import OperationalEvents
from companion.services.assessment.solver import DeterministicSolver
from tests.unit.data.brief import NOW, events_payload, facts_from, trip_context_payload
from tests.unit.data.reference import AIRPORTS, rel_2026_09

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    url = f"sqlite+pysqlite:///{tmp_path / 'audit.db'}"
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return create_engine(url)


def _brief() -> Assessment:
    return DeterministicSolver().assess(
        facts_from(trip_context_payload()),
        OperationalEvents.model_validate(events_payload()),
        rel_2026_09(),
        AIRPORTS,
        NOW,
    )


def _rows(engine: Engine) -> list[dict]:
    with engine.connect() as connection:
        return [dict(r) for r in connection.execute(select(trip_assessments)).mappings()]


def test_records_one_row_per_call(engine: Engine) -> None:
    log = SqlAssessmentLog(engine)

    log.record("ABC123", _brief(), "req-1")
    log.record("ABC123", _brief(), "req-2")

    rows = _rows(engine)
    assert [r["request_id"] for r in rows] == ["req-1", "req-2"]
    assert rows[0]["id"] != rows[1]["id"]
    row = rows[0]
    assert row["booking_id"] == "ABC123"
    assert row["relevance"] == "DISRUPTIVE"
    assert row["reasons"] == [
        {"code": "MISSED_CONNECTION", "segment_ids": ["S1", "S2"], "event_ids": ["E-1001"]},
        {"code": "LONG_DELAY", "segment_ids": ["S1"], "event_ids": ["E-1001"]},
    ]
    assert row["rejected"] == [{"event_id": "E-1012", "reason": "SOURCE_DEGRADED"}]
    assert row["rules_version"] == "REL-2026-09"
    assert row["assessed_at"].replace(tzinfo=UTC) == NOW


def test_no_personal_data_in_any_column(engine: Engine) -> None:
    SqlAssessmentLog(engine).record("ABC123", _brief(), "req-1")

    text = repr(_rows(engine))
    for value in ["Silva", "María", "Tomás", "maria.silva@example.com", "12.345.678-9"]:
        assert value not in text


def test_database_error_raises(tmp_path: Path) -> None:
    empty = create_engine(f"sqlite+pysqlite:///{tmp_path / 'empty.db'}")

    with pytest.raises(AssessmentNotRecorded):
        SqlAssessmentLog(empty).record("ABC123", _brief(), "req-1")


def test_record_returns_the_new_row_id(engine: Engine) -> None:
    record_id = SqlAssessmentLog(engine).record("ABC123", _brief(), "req-1")

    assert [r["id"] for r in _rows(engine)] == [record_id]
