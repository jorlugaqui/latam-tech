"""Spec mock-tools: contracts and the scenario catalog (design D9)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

PASSENGER_KEYS = {"passenger_id", "name", "type"}


def _context(client: TestClient, auth: dict[str, str], code: str) -> Any:
    return client.post("/tools/get_trip_context", json={"booking_id": code}, headers=auth)


def _events(client: TestClient, auth: dict[str, str], *ids: str) -> Any:
    return client.post(
        "/tools/get_operational_events", json={"segment_ids": list(ids)}, headers=auth
    )


def test_brief_trip_context(client: TestClient, auth: dict[str, str]) -> None:
    body = _context(client, auth, "ABC123").json()

    assert body["booking_id"] == "ABC123"
    assert body["passengers"][0] == {
        "passenger_id": "P1",
        "name": "María Silva",
        "type": "ADULT",
        "email": "maria.silva@example.com",
        "phone": "+56 9 8765 4321",
        "document_id": "12.345.678-9",
        "loyalty_tier": "GOLD",
    }
    assert body["passengers"][1] == {
        "passenger_id": "P2",
        "name": "Tomás Silva",
        "type": "CHILD",
        "age": 7,
    }
    assert [s["segment_id"] for s in body["segments"]] == ["S1", "S2"]
    assert body["fare_conditions"] == {
        "changeable": True,
        "refundable": False,
        "fare_family": "LIGHT",
    }
    assert body["_meta"] == {
        "retrieved_at": "2026-09-15T11:02:33Z",
        "completeness": "PARTIAL",
        "missing_fields": ["fare_conditions.change_penalty_amount"],
    }


def test_brief_events(client: TestClient, auth: dict[str, str]) -> None:
    body = _events(client, auth, "S1", "S2").json()

    assert [e["event_id"] for e in body["events"]] == ["E-1001", "E-1007", "E-1012", "E-2003"]
    assert body["events"][0] == {
        "event_id": "E-1001",
        "segment_id": "S1",
        "type": "DELAY",
        "delay_minutes": 160,
        "new_departure": "17:10",
        "source": "OPS_CORE",
        "recorded_at": "2026-09-15T10:48:00Z",
    }
    assert body["_meta"]["sources_available"] == ["OPS_CORE", "AIRPORT_FEED", "LEGACY_MIRROR"]
    assert body["_meta"]["sources_degraded"] == ["LEGACY_MIRROR"]


@pytest.mark.parametrize("code", ["ZZZ999", "NOTF01"])
def test_unknown_booking(client: TestClient, auth: dict[str, str], code: str) -> None:
    response = _context(client, auth, code)

    assert response.status_code == 404
    assert response.json() == {"error": "BOOKING_NOT_FOUND"}


def test_unknown_segments(client: TestClient, auth: dict[str, str]) -> None:
    response = _events(client, auth, "NOPE-S1")

    assert response.status_code == 200
    assert response.json()["events"] == []


@pytest.mark.parametrize(
    "code", ["OKAY01", "GATE01", "CONF01", "STAL01", "CANC01", "NITE01", "EVTERR"]
)
def test_catalog_contexts(client: TestClient, auth: dict[str, str], code: str) -> None:
    body = _context(client, auth, code).json()

    assert body["booking_id"] == code
    assert [s["segment_id"] for s in body["segments"]] == [f"{code}-S1", f"{code}-S2"]
    assert [s["flight_number"] for s in body["segments"]] == ["LA500", "LA2410"]
    assert {p["name"] for p in body["passengers"]} == {"María Silva", "Tomás Silva"}
    assert body["_meta"]["completeness"] == "COMPLETE"


def _by_segment(body: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for event in body["events"]:
        result.setdefault(event["segment_id"], []).append(event)
    return result


def test_on_time_fixture(client: TestClient, auth: dict[str, str]) -> None:
    events = _by_segment(_events(client, auth, "OKAY01-S1", "OKAY01-S2").json())

    assert [(e["type"], e["status"], e["source"]) for e in events["OKAY01-S1"]] == [
        ("STATUS", "ON_TIME", "OPS_CORE")
    ]
    assert [(e["type"], e["status"]) for e in events["OKAY01-S2"]] == [("STATUS", "SCHEDULED")]
    assert events["OKAY01-S1"][0]["recorded_at"] == "2026-09-15T10:52:33Z"


def test_gate_change_fixture(client: TestClient, auth: dict[str, str]) -> None:
    events = _by_segment(_events(client, auth, "GATE01-S1", "GATE01-S2").json())

    gate = [e for e in events["GATE01-S1"] if e["type"] == "GATE_CHANGE"]
    assert [(e["gate"], e["source"]) for e in gate] == [("31", "AIRPORT_FEED")]


def test_conflict_fixture(client: TestClient, auth: dict[str, str]) -> None:
    body = _events(client, auth, "CONF01-S1", "CONF01-S2").json()
    s1 = _by_segment(body)["CONF01-S1"]

    assert {(e["type"], e["source"]) for e in s1} == {
        ("DELAY", "OPS_CORE"),
        ("STATUS", "AIRPORT_FEED"),
    }
    delay = next(e for e in s1 if e["type"] == "DELAY")
    assert (delay["delay_minutes"], delay["new_departure"]) == (90, "16:00")
    assert not {"OPS_CORE", "AIRPORT_FEED"} & set(body["_meta"]["sources_degraded"])


def test_stale_fixture(client: TestClient, auth: dict[str, str]) -> None:
    body = _events(client, auth, "STAL01-S1", "STAL01-S2").json()

    assert body["events"]
    assert all(e["recorded_at"] == "2026-09-15T09:02:33Z" for e in body["events"])


def test_cancellation_fixture(client: TestClient, auth: dict[str, str]) -> None:
    s1 = _by_segment(_events(client, auth, "CANC01-S1", "CANC01-S2").json())["CANC01-S1"]

    assert [(e["type"], e["status"], e["source"]) for e in s1] == [
        ("STATUS", "CANCELLED", "OPS_CORE")
    ]
    assert "new_departure" not in s1[0]


def test_overnight_fixture(client: TestClient, auth: dict[str, str]) -> None:
    s1, s2 = _context(client, auth, "NITE01").json()["segments"]

    assert (s1["scheduled_departure"], s1["scheduled_arrival"]) == ("20:25", "22:30")
    assert s2["date"] == s1["date"]
    assert s2["scheduled_departure"] == "23:50"
    delay = _events(client, auth, "NITE01-S1").json()["events"][0]
    assert (delay["delay_minutes"], delay["new_departure"]) == (120, "22:25")


def test_trip_context_outage(client: TestClient, auth: dict[str, str]) -> None:
    response = _context(client, auth, "CTXERR")

    assert response.status_code == 503
    assert response.json() == {"error": "UPSTREAM_UNAVAILABLE"}


def test_events_outage(client: TestClient, auth: dict[str, str]) -> None:
    response = _events(client, auth, "EVTERR-S1", "EVTERR-S2")

    assert response.status_code == 503
    assert response.json() == {"error": "UPSTREAM_UNAVAILABLE"}
