"""Spec disruption-assessment: accepted evidence, supersession, conflicts."""

from datetime import UTC, datetime
from typing import Any

from companion.schemas.assessment import RejectedEvent, RejectionReason
from companion.schemas.tools import OperationalEvents
from companion.services.assessment.reconciliation import TimingKind, reconcile
from tests.unit.data.brief import NOW, events_payload

WINDOW = 30


def _events(payload: dict[str, Any]) -> OperationalEvents:
    return OperationalEvents.model_validate(payload)


def _event(event_id: str, segment: str, source: str, recorded: str, **fields: Any) -> dict:
    return {
        "event_id": event_id,
        "segment_id": segment,
        "source": source,
        "recorded_at": recorded,
        **fields,
    }


def test_brief_degraded_source_is_discarded() -> None:
    evidence = reconcile(_events(events_payload()), WINDOW, NOW)

    assert RejectedEvent(event_id="E-1012", reason=RejectionReason.SOURCE_DEGRADED) in (
        evidence.rejected
    )
    s1 = evidence.segments["S1"]
    assert s1.timing is not None
    assert s1.timing.kind is TimingKind.DELAYED
    assert s1.timing.delay_minutes == 160
    assert s1.timing_event_ids == ["E-1001"]
    assert s1.gate == "24"
    assert s1.gate_event_id == "E-1007"
    assert evidence.segments["S2"].timing.kind is TimingKind.ON_SCHEDULE


def test_stale_event_is_discarded() -> None:
    payload = events_payload()
    payload["events"] = [
        _event("E-9", "S1", "OPS_CORE", "2026-09-15T10:20:00Z", type="STATUS", status="ON_TIME")
    ]

    evidence = reconcile(_events(payload), WINDOW, NOW)

    assert evidence.rejected == [RejectedEvent(event_id="E-9", reason=RejectionReason.STALE)]
    assert "S1" not in evidence.segments


def test_unknown_source_is_discarded() -> None:
    payload = events_payload()
    payload["events"].append(
        _event("E-77", "S2", "CREW_APP", "2026-09-15T11:00:00Z", type="STATUS", status="ON_TIME")
    )

    evidence = reconcile(_events(payload), WINDOW, NOW)

    assert RejectedEvent(event_id="E-77", reason=RejectionReason.SOURCE_UNKNOWN) in (
        evidence.rejected
    )


def test_newer_report_from_same_source_supersedes() -> None:
    payload = events_payload()
    payload["events"].append(
        _event(
            "E-0990",
            "S1",
            "OPS_CORE",
            "2026-09-15T10:40:00Z",
            type="DELAY",
            delay_minutes=90,
            new_departure="16:00",
        )
    )

    evidence = reconcile(_events(payload), WINDOW, NOW)

    s1 = evidence.segments["S1"]
    assert s1.timing.delay_minutes == 160
    assert s1.timing_event_ids == ["E-1001"]
    assert not s1.conflict


def test_trusted_sources_in_conflict() -> None:
    payload = events_payload()
    payload["events"] = [
        _event(
            "E-3001",
            "S1",
            "OPS_CORE",
            "2026-09-15T10:50:00Z",
            type="DELAY",
            delay_minutes=90,
            new_departure="16:00",
        ),
        _event(
            "E-3002", "S1", "AIRPORT_FEED", "2026-09-15T10:52:00Z", type="STATUS", status="ON_TIME"
        ),
    ]

    evidence = reconcile(_events(payload), WINDOW, NOW)

    s1 = evidence.segments["S1"]
    assert s1.conflict
    assert s1.timing is None
    assert sorted(s1.timing_event_ids) == ["E-3001", "E-3002"]


def test_agreeing_sources_are_not_a_conflict() -> None:
    payload = events_payload()
    payload["events"] = [
        _event("E-1", "S2", "OPS_CORE", "2026-09-15T10:50:00Z", type="STATUS", status="SCHEDULED"),
        _event(
            "E-2", "S2", "AIRPORT_FEED", "2026-09-15T10:51:00Z", type="STATUS", status="ON_TIME"
        ),
    ]

    evidence = reconcile(_events(payload), WINDOW, NOW)

    s2 = evidence.segments["S2"]
    assert not s2.conflict
    assert s2.timing.kind is TimingKind.ON_SCHEDULE
    assert sorted(s2.timing_event_ids) == ["E-1", "E-2"]


def test_cancellation_is_a_timing_state() -> None:
    payload = events_payload()
    payload["events"] = [
        _event("E-5", "S1", "OPS_CORE", "2026-09-15T10:58:00Z", type="STATUS", status="CANCELLED")
    ]

    evidence = reconcile(_events(payload), WINDOW, datetime(2026, 9, 15, 11, 3, tzinfo=UTC))

    assert evidence.segments["S1"].timing.kind is TimingKind.CANCELLED
