"""Spec api-errors: generic 500, JSON 404, 422 without echoing submitted values."""

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from companion.presentation.errors import install_error_handlers
from companion.presentation.request_id import RequestIdMiddleware

boom = APIRouter()


@boom.get("/boom")
def raise_unexpected() -> None:
    raise RuntimeError("db password=secret")


@boom.get("/items")
def list_items(limit: int) -> dict[str, int]:
    return {"limit": limit}


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(boom)
    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_exception_returns_generic_500(client: TestClient) -> None:
    response = client.get("/boom")

    assert response.status_code == 500
    request_id = response.headers["X-Request-ID"]
    assert response.json() == {"error": "internal_error", "request_id": request_id}
    assert "secret" not in response.text
    assert "RuntimeError" not in response.text


def test_unhandled_exception_keeps_incoming_request_id(client: TestClient) -> None:
    response = client.get("/boom", headers={"X-Request-ID": "demo-123"})

    assert response.json()["request_id"] == "demo-123"
    assert response.headers["X-Request-ID"] == "demo-123"


def test_unknown_route_returns_json_404(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"error": "not_found"}


def test_validation_error_does_not_echo_values(client: TestClient) -> None:
    response = client.get("/items", params={"limit": "maria.silva@example.com"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["fields"] == [{"loc": ["query", "limit"], "msg": body["fields"][0]["msg"]}]
    assert "maria.silva@example.com" not in response.text
