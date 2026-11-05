"""Design D3/D12: rule set selection by effective window, airports, fail closed."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, insert

from companion.ports.rules import RulesUnavailable
from companion.repositories.clock import SystemClock
from companion.repositories.sql.rules import SqlAirportDirectory, SqlRuleSetRepository
from companion.repositories.sql.tables import relevance_criteria, relevance_rule_sets
from companion.schemas.assessment import Tier

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
NOW = datetime(2026, 9, 15, 11, 3, tzinfo=UTC)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    url = f"sqlite+pysqlite:///{tmp_path / 'rules.db'}"
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return create_engine(url)


def _add_version(engine: Engine, version: str, start: datetime, end: datetime | None) -> None:
    with engine.begin() as connection:
        connection.execute(
            insert(relevance_rule_sets).values(
                version=version,
                effective_from=start,
                effective_to=end,
                freshness_max_age_minutes=45,
                created_at=start,
            )
        )
        connection.execute(
            insert(relevance_criteria).values(
                rule_set_version=version,
                criterion_key="MISSED_CONNECTION",
                enabled=True,
                tier="DISRUPTIVE",
                params={"default_mct_minutes": 75},
            )
        )


def test_seeded_rule_set_is_in_effect(engine: Engine) -> None:
    rules = SqlRuleSetRepository(engine).get_effective(NOW)

    assert rules.version == "REL-2026-09"
    assert rules.freshness_max_age_minutes == 30
    assert rules.effective_from == datetime(2026, 9, 1, tzinfo=UTC)
    assert rules.effective_from.tzinfo is not None
    by_key = {c.key: c for c in rules.criteria}
    assert set(by_key) == {
        "CANCELLATION",
        "MISSED_CONNECTION",
        "LONG_DELAY",
        "MINOR_DELAY",
        "GATE_CHANGE",
    }
    assert by_key["MISSED_CONNECTION"].params == {
        "default_mct_minutes": 60,
        "mct_by_airport": {"MEX": 90},
    }
    assert by_key["GATE_CHANGE"].tier is Tier.INFORMATIONAL


def test_latest_version_in_effect_wins(engine: Engine) -> None:
    _add_version(engine, "REL-2026-10", datetime(2026, 9, 10, tzinfo=UTC), None)
    _add_version(engine, "REL-FUTURE", datetime(2027, 1, 1, tzinfo=UTC), None)

    assert SqlRuleSetRepository(engine).get_effective(NOW).version == "REL-2026-10"


def test_expired_version_is_skipped(engine: Engine) -> None:
    _add_version(
        engine,
        "REL-EXPIRED",
        datetime(2026, 9, 10, tzinfo=UTC),
        datetime(2026, 9, 12, tzinfo=UTC),
    )

    assert SqlRuleSetRepository(engine).get_effective(NOW).version == "REL-2026-09"


def test_none_in_effect(engine: Engine) -> None:
    with pytest.raises(RulesUnavailable):
        SqlRuleSetRepository(engine).get_effective(datetime(2026, 1, 1, tzinfo=UTC))


def test_database_error_is_rules_unavailable(tmp_path: Path) -> None:
    empty = create_engine(f"sqlite+pysqlite:///{tmp_path / 'empty.db'}")

    with pytest.raises(RulesUnavailable):
        SqlRuleSetRepository(empty).get_effective(NOW)
    with pytest.raises(RulesUnavailable):
        SqlAirportDirectory(empty).find({"SCL"})


def test_airports_found_and_unknown_omitted(engine: Engine) -> None:
    found = SqlAirportDirectory(engine).find({"SCL", "LIM", "XXX"})

    assert {code: a.iana_tz for code, a in found.items()} == {
        "SCL": "America/Santiago",
        "LIM": "America/Lima",
    }


def test_system_clock_is_aware_utc() -> None:
    assert SystemClock().now().utcoffset().total_seconds() == 0
