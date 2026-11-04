"""Spec api-authentication: Bearer token on /api, uniform 401, tokens never recorded."""

import logging

import pytest
from fastapi.testclient import TestClient

from tests.unit.conftest import TEST_TOKEN

PING = "/api/v1/ping"


def test_valid_token(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(PING, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="missing-header"),
        pytest.param({"Authorization": "Basic dXNlcjpwYXNz"}, id="wrong-scheme"),
        pytest.param({"Authorization": "Bearer wrong-token"}, id="wrong-token"),
        pytest.param({"Authorization": "Bearer"}, id="empty-credentials"),
        pytest.param({"Authorization": TEST_TOKEN}, id="token-without-scheme"),
    ],
)
def test_rejected_with_401(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get(PING, headers=headers)

    assert response.status_code == 401


def test_failures_are_indistinguishable(client: TestClient) -> None:
    responses = [
        client.get(PING),
        client.get(PING, headers={"Authorization": "Basic dXNlcjpwYXNz"}),
        client.get(PING, headers={"Authorization": "Bearer wrong-token"}),
    ]

    for response in responses:
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json() == {"error": "unauthorized"}
    assert len({r.text for r in responses}) == 1


def test_rejected_token_is_not_logged_or_echoed(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        response = client.get(PING, headers={"Authorization": "Bearer wrong-token"})

    assert "wrong-token" not in caplog.text
    assert "wrong-token" not in response.text


def test_valid_token_is_not_logged(
    client: TestClient, auth_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        client.get(PING, headers=auth_headers)

    assert TEST_TOKEN not in caplog.text
