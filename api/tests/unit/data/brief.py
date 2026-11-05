"""The brief's ABC123 sample payloads (docs/internal/disruption_companion.pdf, section 2),
as test fixtures. Functions return fresh copies so tests can mutate them."""

import copy
from datetime import UTC, datetime
from typing import Any

# A minute after the events were retrieved: every OPS_CORE / AIRPORT_FEED event is fresh.
NOW = datetime(2026, 9, 15, 11, 3, 0, tzinfo=UTC)

_TRIP_CONTEXT: dict[str, Any] = {
    "booking_id": "ABC123",
    "passengers": [
        {
            "passenger_id": "P1",
            "name": "María Silva",
            "type": "ADULT",
            "email": "maria.silva@example.com",
            "phone": "+56 9 8765 4321",
            "document_id": "12.345.678-9",
            "loyalty_tier": "GOLD",
        },
        {"passenger_id": "P2", "name": "Tomás Silva", "type": "CHILD", "age": 7},
    ],
    "segments": [
        {
            "segment_id": "S1",
            "flight_number": "LA500",
            "origin": "SCL",
            "destination": "LIM",
            "date": "2026-09-15",
            "scheduled_departure": "14:30",
            "scheduled_arrival": "17:55",
        },
        {
            "segment_id": "S2",
            "flight_number": "LA2410",
            "origin": "LIM",
            "destination": "MEX",
            "date": "2026-09-15",
            "scheduled_departure": "19:05",
            "scheduled_arrival": "23:40",
        },
    ],
    "fare_conditions": {"changeable": True, "refundable": False, "fare_family": "LIGHT"},
    "_meta": {
        "retrieved_at": "2026-09-15T11:02:31Z",
        "completeness": "PARTIAL",
        "missing_fields": ["fare_conditions.change_penalty_amount"],
    },
}

_EVENTS: dict[str, Any] = {
    "events": [
        {
            "event_id": "E-1001",
            "segment_id": "S1",
            "type": "DELAY",
            "delay_minutes": 160,
            "new_departure": "17:10",
            "source": "OPS_CORE",
            "recorded_at": "2026-09-15T10:48:00Z",
        },
        {
            "event_id": "E-1007",
            "segment_id": "S1",
            "type": "GATE_CHANGE",
            "gate": "24",
            "source": "AIRPORT_FEED",
            "recorded_at": "2026-09-15T10:55:00Z",
        },
        {
            "event_id": "E-1012",
            "segment_id": "S1",
            "type": "STATUS",
            "status": "ON_TIME",
            "source": "LEGACY_MIRROR",
            "recorded_at": "2026-09-15T09:30:00Z",
        },
        {
            "event_id": "E-2003",
            "segment_id": "S2",
            "type": "STATUS",
            "status": "SCHEDULED",
            "source": "OPS_CORE",
            "recorded_at": "2026-09-15T10:48:00Z",
        },
    ],
    "_meta": {
        "retrieved_at": "2026-09-15T11:02:33Z",
        "sources_available": ["OPS_CORE", "AIRPORT_FEED", "LEGACY_MIRROR"],
        "sources_degraded": ["LEGACY_MIRROR"],
    },
}


def trip_context_payload() -> dict[str, Any]:
    return copy.deepcopy(_TRIP_CONTEXT)


def events_payload() -> dict[str, Any]:
    return copy.deepcopy(_EVENTS)


def facts_from(payload: dict[str, Any]):
    """TripFacts as the trip status service builds them (first names only)."""
    from companion.schemas.assessment import PassengerFacts, SegmentFacts, TripFacts
    from companion.schemas.tools import TripContext

    context = TripContext.model_validate(payload)
    return TripFacts(
        booking_id=context.booking_id,
        passengers=[
            PassengerFacts(first_name=p.name.split()[0], type=p.type) for p in context.passengers
        ],
        segments=[SegmentFacts(**s.model_dump()) for s in context.segments],
    )
