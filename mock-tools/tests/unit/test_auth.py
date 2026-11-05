"""Spec mock-tools: tool endpoints require the tools token."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from mock_tools.settings import MockToolsSettings

BODY = {"booking_id": "ABC123"}
API_TOKEN = "test-token-0123456789abcdef0123456789"


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": f"Bearer {API_TOKEN}"}, {"Authorization": "Basic abc"}],
    ids=["missing", "api-token", "wrong-scheme"],
)
def test_tool_call_without_tools_token(client: TestClient, headers: dict[str, str]) -> None:
    for path, body in [
        ("/tools/get_trip_context", BODY),
        ("/tools/get_operational_events", {"segment_ids": ["S1"]}),
    ]:
        response = client.post(path, json=body, headers=headers)

        assert response.status_code == 401
        assert response.json() == {"error": "unauthorized"}


def test_health_is_public(client: TestClient) -> None:
    assert client.get("/health/live").status_code == 200


def test_startup_fails_without_a_long_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOOLS_API_TOKEN", raising=False)
    with pytest.raises(ValidationError):
        MockToolsSettings()
    with pytest.raises(ValidationError) as exc:
        MockToolsSettings(tools_api_token="short-token")
    assert "short-token" not in str(exc.value)
