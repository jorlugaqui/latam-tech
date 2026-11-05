"""Spec trip-status: HTTP contract of POST /api/v1/trips/lookup."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.composition import get_trip_status_service
from companion.ports.tools import ToolUnavailable
from companion.services.assessment.explanation import TemplateComposer
from companion.services.assessment.solver import DeterministicSolver
from companion.services.trip_status import TripStatusService
from tests.unit.data.brief import NOW, events_payload, trip_context_payload
from tests.unit.data.reference import AIRPORTS, rel_2026_09
from tests.unit.fakes import (
    FakeAirportDirectory,
    FakeAssessmentLog,
    FakeRuleSetRepository,
    FakeToolsClient,
    FixedClock,
)

URL = "/api/v1/trips/lookup"
BRIEF = {"booking_id": "ABC123", "last_name": "Silva"}


@pytest.fixture
def tools() -> FakeToolsClient:
    return FakeToolsClient({"ABC123": trip_context_payload()}, events_payload())


@pytest.fixture
def log() -> FakeAssessmentLog:
    return FakeAssessmentLog()


@pytest.fixture
def api(app: FastAPI, tools: FakeToolsClient, log: FakeAssessmentLog) -> TestClient:
    service = TripStatusService(
        trips=tools,
        events=tools,
        rules=FakeRuleSetRepository(rel_2026_09()),
        airports=FakeAirportDirectory(AIRPORTS),
        clock=FixedClock(NOW),
        solver=DeterministicSolver(),
        composer=TemplateComposer(),
        assessment_log=log,
    )
    app.dependency_overrides[get_trip_status_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_brief_lookup(api: TestClient, auth_headers: dict[str, str]) -> None:
    response = api.post(URL, json=BRIEF, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["passengers"] == [
        {"first_name": "María", "type": "ADULT"},
        {"first_name": "Tomás", "type": "CHILD"},
    ]
    s1 = body["segments"][0]
    assert s1["status"] == "DELAYED"
    assert s1["delay_minutes"] == 160
    assert s1["gate"] == "24"
    assert s1["connection"] == {"to_segment_id": "S2", "status": "MISSED"}
    assert s1["scheduled_departure"] == "2026-09-15T14:30:00-03:00"
    assert s1["estimated_arrival"] == "2026-09-15T20:35:00-05:00"
    assert body["assessment"]["relevance"] == "DISRUPTIVE"
    assert body["assessment"]["assessed_at"] == "2026-09-15T11:03:00Z"
    assert body["next_step"] == "RECOMMENDATION"


def test_body_holds_no_personal_data(api: TestClient, auth_headers: dict[str, str]) -> None:
    text = api.post(URL, json=BRIEF, headers=auth_headers).text

    for value in [
        "maria.silva@example.com",
        "+56 9 8765 4321",
        "12.345.678-9",
        "GOLD",
        "LEGACY_MIRROR",
        "E-1012",
        "passenger_id",
        "fare_conditions",
    ]:
        assert value not in text


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}])
def test_unauthorized_calls_no_tool(
    api: TestClient, tools: FakeToolsClient, headers: dict[str, str]
) -> None:
    response = api.post(URL, json=BRIEF, headers=headers)

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}
    assert tools.calls == []


def test_invalid_input_is_not_echoed(
    api: TestClient, tools: FakeToolsClient, auth_headers: dict[str, str]
) -> None:
    response = api.post(
        URL, json={"booking_id": "ABC-12", "last_name": "Silva"}, headers=auth_headers
    )

    assert response.status_code == 422
    assert "ABC-12" not in response.text
    assert "Silva" not in response.text
    assert tools.calls == []


def test_query_string_is_not_accepted(api: TestClient, auth_headers: dict[str, str]) -> None:
    response = api.post(f"{URL}?booking_id=ABC123&last_name=Silva", headers=auth_headers)

    assert response.status_code == 422


def test_unknown_booking_and_wrong_surname_are_identical(
    api: TestClient, auth_headers: dict[str, str]
) -> None:
    unknown = api.post(
        URL, json={"booking_id": "NOTF01", "last_name": "Silva"}, headers=auth_headers
    )
    wrong = api.post(URL, json={"booking_id": "ABC123", "last_name": "Rojas"}, headers=auth_headers)

    assert unknown.status_code == wrong.status_code == 404
    assert unknown.json() == wrong.json() == {"error": "not_found"}
    drop = {"x-request-id", "content-length"}
    assert {k: v for k, v in unknown.headers.items() if k not in drop} == {
        k: v for k, v in wrong.headers.items() if k not in drop
    }


def test_trip_context_unavailable(
    api: TestClient, tools: FakeToolsClient, auth_headers: dict[str, str]
) -> None:
    tools.context_error = ToolUnavailable

    response = api.post(URL, json=BRIEF, headers=auth_headers)

    assert response.status_code == 503
    assert response.json() == {"error": "trip_context_unavailable"}


def test_request_id_reaches_the_assessment_record(
    api: TestClient, log: FakeAssessmentLog, auth_headers: dict[str, str]
) -> None:
    response = api.post(URL, json=BRIEF, headers={**auth_headers, "X-Request-ID": "req-abc"})

    assert response.status_code == 200
    assert [request_id for _, _, request_id in log.records] == ["req-abc"]
