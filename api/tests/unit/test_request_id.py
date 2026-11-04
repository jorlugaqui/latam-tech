"""Spec api-errors: every response carries a request ID."""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.presentation.request_id import RequestIdMiddleware, install_request_id_logging

logger = logging.getLogger("tests.request_id")


@pytest.fixture
def client() -> TestClient:
    install_request_id_logging()
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/echo")
    def echo() -> dict[str, str]:
        logger.warning("handling echo")
        return {"status": "ok"}

    return TestClient(app)


def test_generated_when_absent(client: TestClient) -> None:
    response = client.get("/echo")

    assert response.headers["X-Request-ID"]


def test_generated_ids_are_unique(client: TestClient) -> None:
    first = client.get("/echo").headers["X-Request-ID"]
    second = client.get("/echo").headers["X-Request-ID"]

    assert first != second


def test_valid_id_is_reused(client: TestClient) -> None:
    response = client.get("/echo", headers={"X-Request-ID": "demo-123"})

    assert response.headers["X-Request-ID"] == "demo-123"


@pytest.mark.parametrize("invalid", ["<script>", "a" * 65, "has space", ""])
def test_invalid_id_is_replaced(client: TestClient, invalid: str) -> None:
    response = client.get("/echo", headers={"X-Request-ID": invalid})

    assert response.headers["X-Request-ID"] not in ("", invalid)


def test_request_id_is_attached_to_log_records(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="tests.request_id"):
        client.get("/echo", headers={"X-Request-ID": "demo-123"})

    records = [r for r in caplog.records if r.getMessage() == "handling echo"]
    assert records
    assert records[0].request_id == "demo-123"
