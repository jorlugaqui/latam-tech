"""Spec mock-tools: timestamps are relative to the request time."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from mock_tools.main import create_app
from mock_tools.settings import MockToolsSettings
from tests.unit.conftest import TOOLS_TOKEN

LIVE = datetime(2026, 11, 4, 15, 0, 0, tzinfo=UTC)


def _client() -> TestClient:
    return TestClient(
        create_app(MockToolsSettings(tools_api_token=TOOLS_TOKEN), clock=lambda: LIVE)
    )


def test_events_keep_their_distance_from_retrieval() -> None:
    body = (
        _client()
        .post(
            "/tools/get_operational_events",
            json={"segment_ids": ["S1", "S2"]},
            headers={"Authorization": f"Bearer {TOOLS_TOKEN}"},
        )
        .json()
    )

    by_id = {e["event_id"]: e for e in body["events"]}
    assert by_id["E-1001"]["recorded_at"] == "2026-11-04T14:45:27Z"
    assert by_id["E-1012"]["recorded_at"] == "2026-11-04T13:27:27Z"
    assert body["_meta"]["retrieved_at"] == "2026-11-04T15:00:00Z"


def test_segment_dates_move_by_whole_days_and_local_times_stay() -> None:
    body = (
        _client()
        .post(
            "/tools/get_trip_context",
            json={"booking_id": "ABC123"},
            headers={"Authorization": f"Bearer {TOOLS_TOKEN}"},
        )
        .json()
    )

    s1 = body["segments"][0]
    assert s1["date"] == "2026-11-04"
    assert s1["scheduled_departure"] == "14:30"
    assert s1["scheduled_arrival"] == "17:55"
    assert body["_meta"]["retrieved_at"] == "2026-11-04T15:00:00Z"
