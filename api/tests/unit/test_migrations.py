"""Expand/contract discipline: every revision upgrades and downgrades cleanly on SQLite."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _config(url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _current_version(url: str) -> str | None:
    engine = create_engine(url)
    with engine.connect() as connection:
        if not inspect(connection).has_table("alembic_version"):
            return None
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()


def test_upgrade_to_head_then_downgrade_to_base(tmp_path: Path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'migrations.db'}"
    config = _config(url)

    command.upgrade(config, "head")
    assert _current_version(url) == "0004"

    command.downgrade(config, "base")
    assert _current_version(url) is None


RULE_TABLES = {"relevance_rule_sets", "relevance_criteria", "airports"}


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    with engine.connect() as connection:
        return set(inspect(connection).get_table_names())


def _count(url: str, sql: str) -> int:
    engine = create_engine(url)
    with engine.connect() as connection:
        return connection.execute(text(sql)).scalar_one()


def test_expand_creates_rule_tables_and_migrate_seeds_rel_2026_09(tmp_path: Path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'rules.db'}"
    config = _config(url)

    command.upgrade(config, "head")

    assert _tables(url) >= RULE_TABLES
    assert "trip_assessments" in _tables(url)
    assert (
        _count(url, "SELECT count(*) FROM relevance_rule_sets WHERE version = 'REL-2026-09'") == 1
    )
    assert _count(url, "SELECT count(*) FROM relevance_criteria") == 5
    assert _count(url, "SELECT count(*) FROM airports WHERE iata IN ('SCL','LIM','MEX')") == 3


def test_downgrading_the_seed_keeps_the_tables(tmp_path: Path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'rules.db'}"
    config = _config(url)
    command.upgrade(config, "head")

    command.downgrade(config, "0003")
    assert "trip_assessments" not in _tables(url)
    assert _count(url, "SELECT count(*) FROM relevance_rule_sets") == 1

    command.downgrade(config, "0002")

    assert _current_version(url) == "0002"
    assert _tables(url) >= RULE_TABLES
    assert _count(url, "SELECT count(*) FROM relevance_rule_sets") == 0
    assert _count(url, "SELECT count(*) FROM relevance_criteria") == 0
    assert _count(url, "SELECT count(*) FROM airports") == 0

    command.downgrade(config, "0001")

    assert _current_version(url) == "0001"
    assert not RULE_TABLES & _tables(url)
