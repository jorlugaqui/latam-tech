"""Spec mock-tools: policy, options, human case, and the CASERR scenario."""

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from mock_tools.main import create_app
from mock_tools.settings import MockToolsSettings
from tests.unit.conftest import TOOLS_TOKEN


def _post(client: TestClient, auth: dict[str, str], tool: str, body: dict[str, Any]) -> Any:
    return client.post(f"/tools/{tool}", json=body, headers=auth)


def _context(client: TestClient, auth: dict[str, str], code: str) -> dict[str, Any]:
    return _post(client, auth, "get_trip_context", {"booking_id": code}).json()


def test_delay_policy(client: TestClient, auth: dict[str, str]) -> None:
    body = _post(client, auth, "get_policy_rules", {"scenario": "DELAY"}).json()

    assert body["version"] == "POL-DELAY-2026-03"
    assert body["effective_from"] == "2026-03-01"
    assert [r["rule_id"] for r in body["rules"]] == ["R1", "R2", "R3", "R4", "R5"]
    assert body["rules"][1]["condition"] == "delay_minutes >= 240 AND international"
    assert body["rules"][4]["requires_human_approval"] is True
    assert body["_meta"]["superseded_versions"] == ["POL-DELAY-2025-11"]


def test_cancellation_has_no_policy(client: TestClient, auth: dict[str, str]) -> None:
    response = _post(client, auth, "get_policy_rules", {"scenario": "CANCELLATION"})

    assert response.status_code == 404
    assert response.json() == {"error": "POLICY_NOT_FOUND"}


def test_brief_options(client: TestClient, auth: dict[str, str]) -> None:
    body = _post(client, auth, "get_eligible_options", _context(client, auth, "ABC123")).json()

    o1, o2, o3 = body["options"]
    assert (o1["option_id"], o1["flight_number"], o1["date"], o1["departure"]) == (
        "O1",
        "LA2412",
        "2026-09-16",
        "08:15",
    )
    assert (o1["seats_available"], o1["fare_difference"], o1["confidence"]) == (4, 0, "HIGH")
    assert (o2["seats_available"], o2["fare_difference"], o2["currency"]) == (1, 180000, "CLP")
    assert (o3["type"], o3["policy_ref"], o3["confidence"]) == (
        "REFUND",
        "POL-REFUND-2026-01",
        "LOW",
    )
    assert body["_meta"]["ttl_seconds"] == 120


def test_booking_without_options(client: TestClient, auth: dict[str, str]) -> None:
    body = _post(client, auth, "get_eligible_options", _context(client, auth, "OKAY01")).json()

    assert body["options"] == []


def test_options_for_cancellation_and_overnight(client: TestClient, auth: dict[str, str]) -> None:
    for code in ("CANC01", "NITE01"):
        body = _post(client, auth, "get_eligible_options", _context(client, auth, code)).json()
        assert body["options"], code


def test_option_dates_move_with_the_request_date() -> None:
    live = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)
    client = TestClient(
        create_app(MockToolsSettings(tools_api_token=TOOLS_TOKEN), clock=lambda: live)
    )
    auth = {"Authorization": f"Bearer {TOOLS_TOKEN}"}

    body = _post(client, auth, "get_eligible_options", _context(client, auth, "ABC123")).json()

    assert body["options"][0]["date"] == "2026-11-05"
    assert body["_meta"]["retrieved_at"] == "2026-11-04T15:00:00Z"


def test_case_created(client: TestClient, auth: dict[str, str]) -> None:
    body = {"reason": "OPTION_APPROVAL", "evidence": {"booking_id": "ABC123"}}

    first = _post(client, auth, "create_human_case", body)
    second = _post(client, auth, "create_human_case", body)

    assert first.status_code == 201
    assert first.json()["case_id"].startswith("HC-")
    assert first.json()["queue"] == "DISRUPTION_L2"
    assert first.json()["sla_minutes"] == 45
    assert second.json()["case_id"] != first.json()["case_id"]


def test_case_outage_fixture(client: TestClient, auth: dict[str, str]) -> None:
    body = {"reason": "OPTION_APPROVAL", "evidence": {"booking_id": "CASERR"}}

    response = _post(client, auth, "create_human_case", body)

    assert response.status_code == 503
    assert response.json() == {"error": "UPSTREAM_TIMEOUT"}


def test_caserr_mirrors_abc123(client: TestClient, auth: dict[str, str]) -> None:
    abc = _context(client, auth, "ABC123")
    caserr = _context(client, auth, "CASERR")

    assert caserr["booking_id"] == "CASERR"
    assert [s["segment_id"] for s in caserr["segments"]] == ["CASERR-S1", "CASERR-S2"]
    strip = lambda ctx: [{k: v for k, v in s.items() if k != "segment_id"} for s in ctx["segments"]]  # noqa: E731
    assert strip(caserr) == strip(abc)
    assert caserr["_meta"]["completeness"] == "PARTIAL"
    events = _post(
        client, auth, "get_operational_events", {"segment_ids": ["CASERR-S1", "CASERR-S2"]}
    ).json()["events"]
    assert [e["event_id"] for e in events] == [
        "E-CASERR-1001",
        "E-CASERR-1007",
        "E-CASERR-1012",
        "E-CASERR-2003",
    ]
    options = _post(client, auth, "get_eligible_options", caserr).json()["options"]
    assert [o["option_id"] for o in options] == ["O1", "O2", "O3"]


def test_new_tools_require_the_token(client: TestClient) -> None:
    for tool, body in [
        ("get_policy_rules", {"scenario": "DELAY"}),
        ("get_eligible_options", {"booking_id": "ABC123"}),
        ("create_human_case", {"reason": "X", "evidence": {}}),
    ]:
        assert client.post(f"/tools/{tool}", json=body).status_code == 401
