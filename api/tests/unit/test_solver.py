"""Spec disruption-assessment: relevance tiers, precedence, versioned rules, fail closed."""

from typing import Any

from companion.schemas.assessment import (
    Assessment,
    ConnectionStatus,
    CriterionConfig,
    Reason,
    Relevance,
    SegmentStatus,
    Tier,
)
from companion.schemas.tools import OperationalEvents
from companion.services.assessment.solver import DeterministicSolver
from tests.unit.data.brief import NOW, events_payload, facts_from, trip_context_payload
from tests.unit.data.reference import AIRPORTS, rel_2026_09

SOLVER = DeterministicSolver()


def _assess(
    context: dict[str, Any] | None = None,
    events: dict[str, Any] | str | None = "brief",
    rules: Any = "default",
) -> Assessment:
    facts = facts_from(context or trip_context_payload())
    if events == "brief":
        events = events_payload()
    parsed = OperationalEvents.model_validate(events) if events is not None else None
    rule_set = rel_2026_09() if rules == "default" else rules
    return SOLVER.assess(facts, parsed, rule_set, AIRPORTS, NOW)


def _status(**overrides: str) -> dict[str, Any]:
    payload = events_payload()
    payload["events"] = [
        {
            "event_id": "E-1",
            "segment_id": "S1",
            "type": "STATUS",
            "status": "ON_TIME",
            "source": "OPS_CORE",
            "recorded_at": "2026-09-15T10:50:00Z",
        },
        {
            "event_id": "E-2",
            "segment_id": "S2",
            "type": "STATUS",
            "status": "SCHEDULED",
            "source": "OPS_CORE",
            "recorded_at": "2026-09-15T10:50:00Z",
        },
    ]
    for event in payload["events"]:
        if event["segment_id"] in overrides:
            event["status"] = overrides[event["segment_id"]]
    return payload


def _segment(assessment: Assessment, segment_id: str):
    return next(s for s in assessment.segments if s.segment_id == segment_id)


def test_brief_case_is_disruptive_for_two_reasons() -> None:
    result = _assess()

    assert result.relevance is Relevance.DISRUPTIVE
    assert result.reasons == [
        Reason(code="MISSED_CONNECTION", segment_ids=["S1", "S2"], event_ids=["E-1001"]),
        Reason(code="LONG_DELAY", segment_ids=["S1"], event_ids=["E-1001"]),
    ]
    s1 = _segment(result, "S1")
    assert s1.status is SegmentStatus.DELAYED
    assert s1.delay_minutes == 160
    assert s1.gate == "24"
    assert s1.estimated_departure.isoformat() == "2026-09-15T17:10:00-03:00"
    assert s1.estimated_arrival.isoformat() == "2026-09-15T20:35:00-05:00"
    assert s1.connection.status is ConnectionStatus.MISSED
    assert _segment(result, "S2").status is SegmentStatus.ON_SCHEDULE
    assert result.rules_version == "REL-2026-09"
    assert result.assessed_at == NOW
    assert [r.event_id for r in result.rejected] == ["E-1012"]


def test_missing_fare_field_does_not_matter() -> None:
    context = trip_context_payload()
    assert context["_meta"]["completeness"] == "PARTIAL"

    assert _assess(context).relevance is Relevance.DISRUPTIVE


def test_gate_change_only_is_informational() -> None:
    events = _status()
    events["events"].append(
        {
            "event_id": "E-3",
            "segment_id": "S1",
            "type": "GATE_CHANGE",
            "gate": "24",
            "source": "AIRPORT_FEED",
            "recorded_at": "2026-09-15T10:55:00Z",
        }
    )

    result = _assess(events=events)

    assert result.relevance is Relevance.INFORMATIONAL
    assert result.reasons == [Reason(code="GATE_CHANGE", segment_ids=["S1"], event_ids=["E-3"])]


def test_nothing_to_report() -> None:
    result = _assess(events=_status())

    assert result.relevance is Relevance.NONE
    assert result.reasons == []
    assert _segment(result, "S1").connection.status is ConnectionStatus.OK


def test_delay_absorbed_by_layover_is_informational() -> None:
    context = trip_context_payload()
    context["segments"][1]["scheduled_departure"] = "20:00"
    events = _status()
    events["events"][0] = {
        "event_id": "E-9",
        "segment_id": "S1",
        "type": "DELAY",
        "delay_minutes": 30,
        "new_departure": "15:00",
        "source": "OPS_CORE",
        "recorded_at": "2026-09-15T10:50:00Z",
    }

    result = _assess(context, events)

    assert _segment(result, "S1").connection.status is ConnectionStatus.OK
    assert result.relevance is Relevance.INFORMATIONAL
    assert result.reasons[0].code == "MINOR_DELAY"


def test_cancellation_with_unknown_next_segment_is_disruptive() -> None:
    events = _status(S1="CANCELLED")
    events["events"] = events["events"][:1]

    result = _assess(events=events)

    assert result.relevance is Relevance.DISRUPTIVE
    assert result.reasons == [Reason(code="CANCELLATION", segment_ids=["S1"], event_ids=["E-1"])]
    s1 = _segment(result, "S1")
    assert s1.status is SegmentStatus.CANCELLED
    assert s1.connection.status is ConnectionStatus.UNREACHABLE
    assert s1.estimated_departure is None


def test_overnight_missed_connection() -> None:
    context = trip_context_payload()
    context["segments"][0].update(scheduled_departure="20:25", scheduled_arrival="22:30")
    context["segments"][1].update(scheduled_departure="23:50", scheduled_arrival="04:20")
    events = _status()
    events["events"][0] = {
        "event_id": "E-8",
        "segment_id": "S1",
        "type": "DELAY",
        "delay_minutes": 120,
        "new_departure": "22:25",
        "source": "OPS_CORE",
        "recorded_at": "2026-09-15T10:50:00Z",
    }

    result = _assess(context, events)

    s1 = _segment(result, "S1")
    assert s1.estimated_arrival.isoformat() == "2026-09-16T00:30:00-05:00"
    assert s1.connection.status is ConnectionStatus.MISSED
    assert result.relevance is Relevance.DISRUPTIVE


def test_conflicting_sources_are_unverified() -> None:
    events = _status()
    events["events"][0] = {
        "event_id": "E-3001",
        "segment_id": "S1",
        "type": "DELAY",
        "delay_minutes": 90,
        "new_departure": "16:00",
        "source": "OPS_CORE",
        "recorded_at": "2026-09-15T10:50:00Z",
    }
    events["events"].append(
        {
            "event_id": "E-3002",
            "segment_id": "S1",
            "type": "STATUS",
            "status": "ON_TIME",
            "source": "AIRPORT_FEED",
            "recorded_at": "2026-09-15T10:52:00Z",
        }
    )

    result = _assess(events=events)

    assert result.relevance is Relevance.UNVERIFIED
    assert result.reasons == [
        Reason(code="SOURCE_CONFLICT", segment_ids=["S1"], event_ids=["E-3001", "E-3002"])
    ]
    s1 = _segment(result, "S1")
    assert s1.delay_minutes is None
    assert s1.connection.status is ConnectionStatus.UNKNOWN


def test_only_stale_evidence() -> None:
    events = _status()
    for event in events["events"]:
        event["recorded_at"] = "2026-09-15T09:00:00Z"

    result = _assess(events=events)

    assert result.relevance is Relevance.UNVERIFIED
    assert {(r.code, tuple(r.segment_ids)) for r in result.reasons} == {
        ("NO_FRESH_EVIDENCE", ("S1",)),
        ("NO_FRESH_EVIDENCE", ("S2",)),
    }


def test_inconsistent_delay_event() -> None:
    events = events_payload()
    events["events"][0]["new_departure"] = "16:00"

    result = _assess(events=events)

    assert _segment(result, "S1").unverified_reason == "INCONSISTENT_EVENT"
    assert result.relevance is Relevance.UNVERIFIED


def test_unknown_airport() -> None:
    context = trip_context_payload()
    context["segments"][1]["destination"] = "XXX"

    result = _assess(context)

    assert _segment(result, "S2").unverified_reason == "AIRPORT_UNKNOWN"


def test_missing_scheduled_arrival() -> None:
    context = trip_context_payload()
    del context["segments"][0]["scheduled_arrival"]

    result = _assess(context)

    s1 = _segment(result, "S1")
    assert s1.status is SegmentStatus.UNVERIFIED
    assert s1.unverified_reason == "CONTEXT_INCOMPLETE"
    assert s1.connection.status is ConnectionStatus.UNKNOWN


def test_a_newer_rule_set_changes_the_outcome() -> None:
    rules = rel_2026_09()
    criteria = []
    for config in rules.criteria:
        if config.key == "MISSED_CONNECTION":
            config = config.model_copy(update={"enabled": False})
        if config.key == "LONG_DELAY":
            config = config.model_copy(update={"params": {"min_delay_minutes": 180}})
        criteria.append(config)
    rules = rules.model_copy(update={"version": "REL-TEST-B", "criteria": criteria})

    result = _assess(rules=rules)

    assert result.relevance is Relevance.INFORMATIONAL
    assert result.reasons == [
        Reason(code="MINOR_DELAY", segment_ids=["S1"], event_ids=["E-1001"]),
        Reason(code="GATE_CHANGE", segment_ids=["S1"], event_ids=["E-1007"]),
    ]
    assert _segment(result, "S1").connection.status is ConnectionStatus.MISSED
    assert result.rules_version == "REL-TEST-B"


def test_no_rules_fails_closed() -> None:
    result = _assess(rules=None)

    assert result.relevance is Relevance.UNVERIFIED
    assert [r.code for r in result.reasons] == ["RULES_UNAVAILABLE"]
    assert result.rules_version is None
    assert all(s.status is SegmentStatus.UNVERIFIED for s in result.segments)


def test_unknown_criterion_fails_closed() -> None:
    rules = rel_2026_09()
    rules = rules.model_copy(
        update={
            "criteria": [
                *rules.criteria,
                CriterionConfig(key="MOON_PHASE", enabled=True, tier=Tier.DISRUPTIVE),
            ]
        }
    )

    result = _assess(rules=rules)

    assert [r.code for r in result.reasons] == ["RULES_UNAVAILABLE"]


def test_events_unavailable() -> None:
    result = _assess(events=None)

    assert result.relevance is Relevance.UNVERIFIED
    assert [r.code for r in result.reasons] == ["EVENTS_UNAVAILABLE"]
    assert all(s.delay_minutes is None for s in result.segments)
