"""Spec api-health: readiness reflects the database."""

from companion.schemas.health import ReadyStatus
from companion.services.health import HealthService
from tests.unit.fakes import FakeDatabaseProbe


def test_ready_when_database_reachable() -> None:
    service = HealthService(probe=FakeDatabaseProbe(reachable=True))

    assert service.readiness() == ReadyStatus(status="ready")


def test_not_ready_when_database_unreachable() -> None:
    service = HealthService(probe=FakeDatabaseProbe(reachable=False))

    assert service.readiness() == ReadyStatus(status="not_ready")
