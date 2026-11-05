"""Specs recommendation / human-handoff: HTTP contract of the two new routes."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.composition import get_human_case_service, get_recommendation_service
from companion.services.assessment.solver import DeterministicSolver
from companion.services.handoff import HumanCaseService
from companion.services.recommendation import RecommendationService
from companion.services.trip_access import TripAccess
from tests.unit.data.brief import (
    NOW,
    events_payload,
    options_payload,
    policy_payload,
    trip_context_payload,
)
from tests.unit.data.reference import AIRPORTS, rel_2026_09
from tests.unit.fakes import (
    FakeAirportDirectory,
    FakeAssessmentLog,
    FakeCaseRepository,
    FakeCaseWriter,
    FakeRuleSetRepository,
    FakeToolsClient,
    FixedClock,
)

RECO = "/api/v1/trips/recommendation"
CASE = "/api/v1/trips/human-case"
BRIEF = {"booking_id": "ABC123", "last_name": "Silva"}
PII = ["maria.silva@example.com", "12.345.678-9", "Silva", "Tomás"]


@pytest.fixture
def tools() -> FakeToolsClient:
    return FakeToolsClient(
        {"ABC123": trip_context_payload()},
        events_payload(),
        policies={"DELAY": policy_payload()},
        options=[options_payload()],
    )


@pytest.fixture
def writer() -> FakeCaseWriter:
    return FakeCaseWriter()


@pytest.fixture
def api(app: FastAPI, tools: FakeToolsClient, writer: FakeCaseWriter) -> TestClient:
    access = TripAccess(
        trips=tools,
        events=tools,
        rules=FakeRuleSetRepository(rel_2026_09()),
        airports=FakeAirportDirectory(AIRPORTS),
        clock=FixedClock(NOW),
        solver=DeterministicSolver(),
        assessment_log=FakeAssessmentLog(),
    )
    recommendations = RecommendationService(access, tools, tools, FixedClock(NOW))
    handoff = HumanCaseService(access, recommendations, FakeCaseRepository(), writer)
    app.dependency_overrides[get_recommendation_service] = lambda: recommendations
    app.dependency_overrides[get_human_case_service] = lambda: handoff
    return TestClient(app, raise_server_exceptions=False)


def test_recommendation(api: TestClient, auth_headers: dict[str, str]) -> None:
    response = api.post(RECO, json=BRIEF, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PROPOSED"
    assert body["policy_version"] == "POL-DELAY-2026-03"
    assert [o["option_id"] for o in body["options"]] == ["O1"]
    assert body["options"][0]["departure"] == "2026-09-16T08:15:00-05:00"
    assert body["approval"] == "HUMAN_REQUIRED"
    assert "excluded" not in body
    for value in [*PII, "O2", "O3", "INSUFFICIENT_SEATS"]:
        assert value not in response.text


@pytest.mark.parametrize("url", [RECO, CASE])
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}])
def test_unauthorized_calls_no_tool(
    api: TestClient, tools: FakeToolsClient, url: str, headers: dict[str, str]
) -> None:
    response = api.post(url, json=BRIEF, headers=headers)

    assert response.status_code == 401
    assert tools.calls == []


@pytest.mark.parametrize(
    ("url", "body"),
    [
        (RECO, {**BRIEF, "relevance": "DISRUPTIVE"}),
        (RECO, {"booking_id": "ABC-12", "last_name": "Silva"}),
        (CASE, {**BRIEF, "option_id": "O1;DROP"}),
    ],
)
def test_invalid_input_is_not_echoed(
    api: TestClient,
    tools: FakeToolsClient,
    auth_headers: dict[str, str],
    url: str,
    body: dict[str, Any],
) -> None:
    response = api.post(url, json=body, headers=auth_headers)

    assert response.status_code == 422
    assert "Silva" not in response.text
    assert "ABC-12" not in response.text
    assert tools.calls == []


@pytest.mark.parametrize("url", [RECO, CASE])
def test_wrong_surname_is_not_found(
    api: TestClient, auth_headers: dict[str, str], writer: FakeCaseWriter, url: str
) -> None:
    response = api.post(
        url, json={"booking_id": "ABC123", "last_name": "Rojas"}, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json() == {"error": "not_found"}
    assert writer.calls == []


def test_case_created_then_reused(api: TestClient, auth_headers: dict[str, str]) -> None:
    first = api.post(CASE, json={**BRIEF, "option_id": "O1"}, headers=auth_headers)
    second = api.post(CASE, json={**BRIEF, "option_id": "O1"}, headers=auth_headers)

    assert first.status_code == 201
    assert first.json()["status"] == "OPEN"
    assert first.json()["case_id"] == "HC-1"
    assert first.json()["sla_minutes"] == 45
    assert second.status_code == 200
    assert second.json()["case_id"] == "HC-1"
    for value in PII:
        assert value not in first.text


def test_indeterminate_is_202(
    api: TestClient, auth_headers: dict[str, str], writer: FakeCaseWriter
) -> None:
    writer.outcome = "indeterminate"

    response = api.post(CASE, json={**BRIEF, "option_id": "O1"}, headers=auth_headers)

    assert response.status_code == 202
    assert response.json()["status"] == "INDETERMINATE"
    assert response.json()["case_id"] is None
    assert "call center" in response.json()["message"]


def test_rejected_is_503(
    api: TestClient, auth_headers: dict[str, str], writer: FakeCaseWriter
) -> None:
    writer.outcome = "rejected"

    response = api.post(CASE, json={**BRIEF, "option_id": "O1"}, headers=auth_headers)

    assert response.status_code == 503
    assert response.json() == {"error": "handoff_unavailable"}


def test_ineligible_option_is_409(api: TestClient, auth_headers: dict[str, str]) -> None:
    response = api.post(CASE, json={**BRIEF, "option_id": "O2"}, headers=auth_headers)

    assert response.status_code == 409
    assert response.json() == {"error": "option_not_eligible"}


def test_nothing_to_escalate_is_409(
    api: TestClient, tools: FakeToolsClient, auth_headers: dict[str, str]
) -> None:
    on_time = events_payload()
    on_time["events"] = [
        {
            "event_id": "E-1",
            "segment_id": s,
            "type": "STATUS",
            "status": "ON_TIME",
            "source": "OPS_CORE",
            "recorded_at": "2026-09-15T10:50:00Z",
        }
        for s in ("S1", "S2")
    ]
    tools.events = on_time

    response = api.post(CASE, json=BRIEF, headers=auth_headers)

    assert response.status_code == 409
    assert response.json() == {"error": "nothing_to_escalate"}
