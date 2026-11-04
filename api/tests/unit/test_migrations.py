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
    assert _current_version(url) == "0001"

    command.downgrade(config, "base")
    assert _current_version(url) is None
