"""Spec api-health: readiness reflects the database; failure detail stays internal."""

import logging
from pathlib import Path

import pytest

from companion.repositories.sql.engine import build_engine
from companion.repositories.sql.probe import SqlDatabaseProbe


def test_reachable_against_sqlite_file(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite+pysqlite:///{tmp_path / 'probe.db'}")

    assert SqlDatabaseProbe(engine).is_reachable() is True


def test_unreachable_returns_false_and_logs_no_connection_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = build_engine("postgresql+psycopg://probe-user:probe-secret-pw@127.0.0.1:1/companion")

    with caplog.at_level(logging.WARNING):
        reachable = SqlDatabaseProbe(engine).is_reachable()

    assert reachable is False
    assert caplog.records, "the failure must be logged"
    logged = caplog.text
    assert "probe-secret-pw" not in logged
    assert "probe-user" not in logged
    assert "127.0.0.1" not in logged
