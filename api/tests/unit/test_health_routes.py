"""Specs api-health (liveness, readiness) and api-authentication (health is public)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.composition import get_health_service
from companion.services.health import HealthService
from tests.unit.fakes import FakeDatabaseProbe


def _with_database(app: FastAPI, *, reachable: bool) -> TestClient:
    service = HealthService(probe=FakeDatabaseProbe(reachable=reachable))
    app.dependency_overrides[get_health_service] = lambda: service
    return TestClient(app)


def test_live_without_token_even_when_database_down(app: FastAPI) -> None:
    client = _with_database(app, reachable=False)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_database_reachable(app: FastAPI) -> None:
    client = _with_database(app, reachable=True)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_not_ready_when_database_unreachable(app: FastAPI) -> None:
    client = _with_database(app, reachable=False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.text == '{"status":"not_ready"}'


def test_ready_against_real_sqlite_probe(client: TestClient) -> None:
    # No override: the composition root wires SqlDatabaseProbe to the test SQLite file.
    response = client.get("/health/ready")

    assert response.status_code == 200
