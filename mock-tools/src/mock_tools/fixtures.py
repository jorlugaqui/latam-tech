"""Scenario catalog (spec mock-tools, design D9), selected by booking code.

Every scenario uses the brief's passengers and route. Only ``ABC123`` keeps the brief's
segment ids (S1, S2); the others use ``<code>-S1`` / ``<code>-S2`` so the events tool can
tell scenarios apart from segment ids alone.
"""

import datetime as dt
from typing import Any

from mock_tools.timeshift import instant

UNAVAILABLE_CONTEXTS = {"CTXERR"}
UNAVAILABLE_EVENTS = {"EVTERR"}
SOURCES_AVAILABLE = ["OPS_CORE", "AIRPORT_FEED", "LEGACY_MIRROR"]
SOURCES_DEGRADED = ["LEGACY_MIRROR"]

PASSENGERS: list[dict[str, Any]] = [
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
]
FARE = {"changeable": True, "refundable": False, "fare_family": "LIGHT"}
MIN = dt.timedelta(minutes=1)


def _segments(prefix: str, s1: tuple[str, str], s2: tuple[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "segment_id": f"{prefix}S1",
            "flight_number": "LA500",
            "origin": "SCL",
            "destination": "LIM",
            "date": "2026-09-15",
            "scheduled_departure": s1[0],
            "scheduled_arrival": s1[1],
        },
        {
            "segment_id": f"{prefix}S2",
            "flight_number": "LA2410",
            "origin": "LIM",
            "destination": "MEX",
            "date": "2026-09-15",
            "scheduled_departure": s2[0],
            "scheduled_arrival": s2[1],
        },
    ]


def _context(code: str, segments: list[dict[str, Any]], partial: bool = False) -> dict:
    return {
        "booking_id": code,
        "passengers": PASSENGERS,
        "segments": segments,
        "fare_conditions": FARE,
        "_meta": {
            "retrieved_at": instant(),
            "completeness": "PARTIAL" if partial else "COMPLETE",
            "missing_fields": ["fare_conditions.change_penalty_amount"] if partial else [],
        },
    }


def _status(event_id: str, segment: str, status: str, source: str, ago: dt.timedelta) -> dict:
    return {
        "event_id": event_id,
        "segment_id": segment,
        "type": "STATUS",
        "status": status,
        "source": source,
        "recorded_at": instant(-ago),
    }


def _delay(event_id: str, segment: str, minutes: int, new: str, ago: dt.timedelta) -> dict:
    return {
        "event_id": event_id,
        "segment_id": segment,
        "type": "DELAY",
        "delay_minutes": minutes,
        "new_departure": new,
        "source": "OPS_CORE",
        "recorded_at": instant(-ago),
    }


def _gate(event_id: str, segment: str, gate: str, ago: dt.timedelta) -> dict:
    return {
        "event_id": event_id,
        "segment_id": segment,
        "type": "GATE_CHANGE",
        "gate": gate,
        "source": "AIRPORT_FEED",
        "recorded_at": instant(-ago),
    }


def _on_time(code: str, ago: dt.timedelta = 10 * MIN) -> list[dict]:
    return [
        _status(f"E-{code}-1", f"{code}-S1", "ON_TIME", "OPS_CORE", ago),
        _status(f"E-{code}-2", f"{code}-S2", "SCHEDULED", "OPS_CORE", ago),
    ]


BRIEF_ROUTE = (("14:30", "17:55"), ("19:05", "23:40"))

TRIP_CONTEXTS: dict[str, dict[str, Any]] = {
    "ABC123": _context("ABC123", _segments("", *BRIEF_ROUTE), partial=True),
    **{
        code: _context(code, _segments(f"{code}-", *BRIEF_ROUTE))
        for code in ("OKAY01", "GATE01", "CONF01", "STAL01", "CANC01", "EVTERR")
    },
    "NITE01": _context("NITE01", _segments("NITE01-", ("20:25", "22:30"), ("23:50", "04:20"))),
    # ABC123 again, whose human case creation times out (indeterminate outcome).
    "CASERR": _context("CASERR", _segments("CASERR-", *BRIEF_ROUTE), partial=True),
}

# The brief's events, recorded at the brief's times (offsets from the reference instant).
_BRIEF_EVENTS = [
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
    _status("E-1012", "S1", "ON_TIME", "LEGACY_MIRROR", dt.timedelta(minutes=92, seconds=33)),
    {
        "event_id": "E-2003",
        "segment_id": "S2",
        "type": "STATUS",
        "status": "SCHEDULED",
        "source": "OPS_CORE",
        "recorded_at": "2026-09-15T10:48:00Z",
    },
]

EVENTS: list[dict[str, Any]] = [
    *_BRIEF_EVENTS,
    *[
        {
            **e,
            "event_id": f"E-CASERR-{e['event_id'][2:]}",
            "segment_id": f"CASERR-{e['segment_id']}",
        }
        for e in _BRIEF_EVENTS
    ],
    *_on_time("OKAY01"),
    *_on_time("GATE01"),
    _gate("E-GATE01-3", "GATE01-S1", "31", 8 * MIN),
    _delay("E-CONF01-1", "CONF01-S1", 90, "16:00", 12 * MIN),
    _status("E-CONF01-2", "CONF01-S1", "ON_TIME", "AIRPORT_FEED", 10 * MIN),
    _status("E-CONF01-3", "CONF01-S2", "SCHEDULED", "OPS_CORE", 10 * MIN),
    *_on_time("STAL01", ago=120 * MIN),
    _status("E-CANC01-1", "CANC01-S1", "CANCELLED", "OPS_CORE", 10 * MIN),
    _status("E-CANC01-2", "CANC01-S2", "SCHEDULED", "OPS_CORE", 10 * MIN),
    _delay("E-NITE01-1", "NITE01-S1", 120, "22:25", 10 * MIN),
    _status("E-NITE01-2", "NITE01-S2", "SCHEDULED", "OPS_CORE", 10 * MIN),
]


def events_for(segment_ids: list[str]) -> dict[str, Any]:
    wanted = set(segment_ids)
    return {
        "events": [e for e in EVENTS if e["segment_id"] in wanted],
        "_meta": {
            "retrieved_at": instant(),
            "sources_available": SOURCES_AVAILABLE,
            "sources_degraded": SOURCES_DEGRADED,
        },
    }


def events_unavailable(segment_ids: list[str]) -> bool:
    return any(s.split("-", 1)[0] in UNAVAILABLE_EVENTS for s in segment_ids)


# ---- policies, options, human cases (add-recommendation-and-handoff) --------------

UNAVAILABLE_CASES = {"CASERR"}

# Only DELAY exists: cancellations have no policy yet (Policy/Legal to provide one).
POLICIES: dict[str, dict[str, Any]] = {
    "DELAY": {
        "scenario": "DELAY",
        "version": "POL-DELAY-2026-03",
        "effective_from": "2026-03-01",
        "rules": [
            {
                "rule_id": "R1",
                "condition": "delay_minutes >= 180",
                "entitlement": "REBOOK_NO_FEE",
                "requires_human_approval": False,
            },
            {
                "rule_id": "R2",
                "condition": "delay_minutes >= 240 AND international",
                "entitlement": "MEAL_VOUCHER",
                "requires_human_approval": False,
            },
            {
                "rule_id": "R3",
                "condition": "missed_connection == true",
                "entitlement": "REBOOK_NO_FEE",
                "requires_human_approval": False,
            },
            {
                "rule_id": "R4",
                "condition": "compensation_requested == true",
                "entitlement": "CASH_COMPENSATION",
                "requires_human_approval": True,
            },
            {
                "rule_id": "R5",
                "condition": "group_includes_minor == true",
                "entitlement": "PRIORITY_HANDLING",
                "requires_human_approval": True,
            },
        ],
        "_meta": {"retrieved_at": instant(), "superseded_versions": ["POL-DELAY-2025-11"]},
    }
}


def _rebook(
    option_id: str,
    flight: str,
    route: tuple[str, str],
    date: str,
    departure: str,
    seats: int,
    confidence: str,
    fare: int = 0,
) -> dict[str, Any]:
    option: dict[str, Any] = {
        "option_id": option_id,
        "type": "REBOOK",
        "flight_number": flight,
        "origin": route[0],
        "destination": route[1],
        "date": date,
        "departure": departure,
        "fare_difference": fare,
        "seats_available": seats,
        "policy_ref": "POL-DELAY-2026-03",
        "confidence": confidence,
    }
    if fare:
        option["currency"] = "CLP"
    return option


_BRIEF_OPTIONS = [
    _rebook("O1", "LA2412", ("LIM", "MEX"), "2026-09-16", "08:15", 4, "HIGH"),
    _rebook("O2", "LA2450", ("LIM", "MEX"), "2026-09-15", "23:40", 1, "MEDIUM", fare=180000),
    {"option_id": "O3", "type": "REFUND", "policy_ref": "POL-REFUND-2026-01", "confidence": "LOW"},
]

OPTIONS: dict[str, list[dict[str, Any]]] = {
    "ABC123": _BRIEF_OPTIONS,
    "CASERR": _BRIEF_OPTIONS,
    "NITE01": [_rebook("O1", "LA2412", ("LIM", "MEX"), "2026-09-16", "08:15", 4, "HIGH")],
    # Unused while cancellations have no policy; present so the agent path is the reason.
    "CANC01": [
        _rebook("O1", "LA530", ("SCL", "LIM"), "2026-09-15", "19:00", 6, "HIGH"),
        _rebook("O2", "LA532", ("SCL", "LIM"), "2026-09-16", "07:30", 9, "HIGH"),
    ],
}


def options_for(booking_id: str) -> dict[str, Any]:
    return {
        "options": OPTIONS.get(booking_id, []),
        "_meta": {"retrieved_at": instant(), "ttl_seconds": 120},
    }
