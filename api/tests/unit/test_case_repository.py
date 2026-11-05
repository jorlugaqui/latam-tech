"""Design D8: human_cases (expand 0005), one active case per booking, transitions only."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, select

from companion.ports.cases import CasesUnavailable, NewCase
from companion.repositories.sql.cases import SqlCaseRepository
from companion.repositories.sql.tables import human_cases
from companion.schemas.case_states import IllegalTransition
from companion.schemas.handoff import CaseReason, CaseStatus

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _config(url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    url = f"sqlite+pysqlite:///{tmp_path / 'cases.db'}"
    command.upgrade(_config(url), "head")
    return create_engine(url)


def _new(booking: str = "ABC123") -> NewCase:
    return NewCase(
        booking_id=booking,
        reason=CaseReason.OPTION_APPROVAL,
        option_id="O1",
        assessment_id="A-1",
        evidence={"booking_id": booking, "option": {"option_id": "O1"}},
        request_id="req-1",
    )


def test_migration_0005_up_and_down(tmp_path: Path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'm.db'}"
    command.upgrade(_config(url), "head")
    assert "human_cases" in inspect(create_engine(url)).get_table_names()

    command.downgrade(_config(url), "0004")

    tables = inspect(create_engine(url)).get_table_names()
    assert "human_cases" not in tables
    assert "trip_assessments" in tables


def test_insert_then_existing_active_case_is_returned(engine: Engine) -> None:
    repo = SqlCaseRepository(engine)

    first, created = repo.open_or_get_active(_new())
    again, created_again = repo.open_or_get_active(_new())

    assert created is True
    assert first.status is CaseStatus.REQUESTED
    assert created_again is False
    assert again.id == first.id


def test_open_stores_the_tool_answer(engine: Engine) -> None:
    repo = SqlCaseRepository(engine)
    case, _ = repo.open_or_get_active(_new())

    opened = repo.transition(case.id, CaseStatus.OPEN, "HC-4471", "DISRUPTION_L2", 45)

    assert (opened.status, opened.case_id, opened.queue, opened.sla_minutes) == (
        CaseStatus.OPEN,
        "HC-4471",
        "DISRUPTION_L2",
        45,
    )
    assert repo.open_or_get_active(_new())[0].case_id == "HC-4471"


def test_failed_frees_the_slot(engine: Engine) -> None:
    repo = SqlCaseRepository(engine)
    case, _ = repo.open_or_get_active(_new())
    repo.transition(case.id, CaseStatus.FAILED)

    retry, created = repo.open_or_get_active(_new())

    assert created is True
    assert retry.id != case.id


def test_indeterminate_keeps_the_slot(engine: Engine) -> None:
    repo = SqlCaseRepository(engine)
    case, _ = repo.open_or_get_active(_new())
    repo.transition(case.id, CaseStatus.INDETERMINATE)

    again, created = repo.open_or_get_active(_new())

    assert (again.id, again.status, created) == (case.id, CaseStatus.INDETERMINATE, False)


def test_other_bookings_are_independent(engine: Engine) -> None:
    repo = SqlCaseRepository(engine)
    repo.open_or_get_active(_new("ABC123"))

    assert repo.open_or_get_active(_new("CASERR"))[1] is True


def test_illegal_transition_is_rejected(engine: Engine) -> None:
    repo = SqlCaseRepository(engine)
    case, _ = repo.open_or_get_active(_new())
    repo.transition(case.id, CaseStatus.OPEN, "HC-1", "Q", 45)

    with pytest.raises(IllegalTransition):
        repo.transition(case.id, CaseStatus.INDETERMINATE)


def test_evidence_and_request_id_are_stored(engine: Engine) -> None:
    case, _ = SqlCaseRepository(engine).open_or_get_active(_new())

    with engine.connect() as connection:
        row = connection.execute(select(human_cases)).mappings().one()
    assert row["id"] == case.id
    assert row["evidence"]["option"]["option_id"] == "O1"
    assert (row["request_id"], row["assessment_id"]) == ("req-1", "A-1")


def test_database_error_is_unavailable(tmp_path: Path) -> None:
    empty = create_engine(f"sqlite+pysqlite:///{tmp_path / 'empty.db'}")

    with pytest.raises(CasesUnavailable):
        SqlCaseRepository(empty).open_or_get_active(_new())
