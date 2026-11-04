"""Spec api-docs: toggled docs, every response documented, Bearer scheme, no secrets."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from companion.config import Settings
from companion.main import create_app
from tests.unit.conftest import TEST_TOKEN

COMMON = {"404", "422", "500"}
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture
def docs_client(make_settings: Callable[..., Settings]) -> TestClient:
    return TestClient(create_app(make_settings(enable_docs=True)))


@pytest.fixture
def spec(docs_client: TestClient) -> dict[str, Any]:
    return docs_client.get("/openapi.json").json()


def _operations(spec: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (path, method, operation)
        for path, item in spec["paths"].items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    ]


def _expected_codes(path: str) -> set[str]:
    if path.startswith("/api/"):
        return {"200", "401"} | COMMON
    if path == "/health/ready":
        return {"200", "503"} | COMMON
    return {"200"} | COMMON


def test_enabled_docs_are_public(docs_client: TestClient) -> None:
    openapi = docs_client.get("/openapi.json")
    viewer = docs_client.get("/docs")

    assert openapi.status_code == 200
    assert openapi.json()["openapi"].startswith("3.")
    assert viewer.status_code == 200


def test_docs_disabled_by_default(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


@pytest.mark.parametrize("enabled", [True, False])
def test_redoc_is_never_served(make_settings: Callable[..., Settings], enabled: bool) -> None:
    client = TestClient(create_app(make_settings(enable_docs=enabled)))

    assert client.get("/redoc").status_code == 404


def test_every_operation_documents_all_its_responses_with_a_schema(spec: dict[str, Any]) -> None:
    operations = _operations(spec)
    assert operations

    for path, method, operation in operations:
        responses = operation["responses"]
        assert set(responses) == _expected_codes(path), f"{method.upper()} {path}"
        for code, response in responses.items():
            schema = response.get("content", {}).get("application/json", {}).get("schema")
            assert schema, f"{method.upper()} {path} {code} has no schema"


def test_protected_401_uses_the_error_schema(spec: dict[str, Any]) -> None:
    unauthorized = spec["paths"]["/api/v1/ping"]["get"]["responses"]["401"]

    ref = unauthorized["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/ErrorResponse")
    assert "error" in spec["components"]["schemas"]["ErrorResponse"]["properties"]


def test_readiness_documents_both_outcomes(spec: dict[str, Any]) -> None:
    responses = spec["paths"]["/health/ready"]["get"]["responses"]

    for code in ("200", "503"):
        ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/ReadyStatus")


def test_bearer_scheme_applies_to_api_and_not_to_health(spec: dict[str, Any]) -> None:
    schemes = spec["components"]["securitySchemes"]
    bearer = [name for name, s in schemes.items() if s == {**s, "type": "http", "scheme": "bearer"}]
    assert bearer

    for path, method, operation in _operations(spec):
        security = operation.get("security", [])
        if path.startswith("/api/"):
            assert any(bearer[0] in requirement for requirement in security), f"{method} {path}"
        else:
            assert not security, f"{method} {path}"


def test_document_contains_no_secrets(spec: dict[str, Any]) -> None:
    rendered = json.dumps(spec)

    assert TEST_TOKEN not in rendered
    assert "sqlite" not in rendered
    assert "app.db" not in rendered
