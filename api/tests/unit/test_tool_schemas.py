"""Upstream contract DTOs parse the brief's payloads, including partial data."""

from datetime import UTC, datetime, time

from companion.schemas.tools import EventType, OperationalEvents, TripContext
from tests.unit.data.brief import events_payload, trip_context_payload


def test_brief_trip_context_parses() -> None:
    context = TripContext.model_validate(trip_context_payload())

    assert context.booking_id == "ABC123"
    assert context.meta.completeness == "PARTIAL"
    assert context.meta.missing_fields == ["fare_conditions.change_penalty_amount"]
    assert context.meta.retrieved_at == datetime(2026, 9, 15, 11, 2, 31, tzinfo=UTC)
    assert context.passengers[0].email == "maria.silva@example.com"
    assert context.passengers[1].email is None
    assert context.passengers[1].age == 7
    s1 = context.segments[0]
    assert s1.scheduled_departure == time(14, 30)
    assert s1.date.isoformat() == "2026-09-15"


def test_partial_segment_fields_are_optional() -> None:
    payload = trip_context_payload()
    del payload["segments"][0]["scheduled_arrival"]
    del payload["fare_conditions"]

    context = TripContext.model_validate(payload)

    assert context.segments[0].scheduled_arrival is None
    assert context.fare_conditions is None


def test_brief_events_parse_every_type() -> None:
    events = OperationalEvents.model_validate(events_payload())

    by_id = {event.event_id: event for event in events.events}
    assert by_id["E-1001"].type is EventType.DELAY
    assert by_id["E-1001"].delay_minutes == 160
    assert by_id["E-1001"].new_departure == time(17, 10)
    assert by_id["E-1007"].gate == "24"
    assert by_id["E-1012"].status == "ON_TIME"
    assert events.meta.sources_degraded == ["LEGACY_MIRROR"]


def test_cancelled_status_parses() -> None:
    payload = events_payload()
    payload["events"][3]["status"] = "CANCELLED"

    events = OperationalEvents.model_validate(payload)

    assert events.events[3].status == "CANCELLED"


def test_unknown_extra_fields_are_ignored() -> None:
    payload = trip_context_payload()
    payload["unexpected"] = "x"
    payload["segments"][0]["aircraft"] = "A320"

    context = TripContext.model_validate(payload)

    assert not hasattr(context, "unexpected")
