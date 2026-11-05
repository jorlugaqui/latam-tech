"""Source reconciliation (spec disruption-assessment, design D2). Deterministic.

1. Reject events from sources that are unknown, degraded or stale, with a reason.
2. Per segment and source, keep the latest timing event (DELAY or STATUS).
3. Normalize each to ON_SCHEDULE / DELAYED(n) / CANCELLED.
4. If sources disagree, the segment is in conflict and no timing state is chosen.

Source trust comes from each response's ``_meta``, never from a hard-coded ranking.
"""

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum

from companion.schemas.assessment import RejectedEvent, RejectionReason
from companion.schemas.tools import EventType, OperationalEvent, OperationalEvents

_ON_SCHEDULE_STATUSES = {"ON_TIME", "SCHEDULED"}
_CANCELLED_STATUSES = {"CANCELLED"}


class TimingKind(StrEnum):
    ON_SCHEDULE = "ON_SCHEDULE"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class TimingState:
    kind: TimingKind
    delay_minutes: int | None = None
    new_departure: dt.time | None = None

    def same_state_as(self, other: "TimingState") -> bool:
        return (self.kind, self.delay_minutes) == (other.kind, other.delay_minutes)


@dataclass
class SegmentEvidence:
    timing: TimingState | None = None
    timing_event_ids: list[str] = field(default_factory=list)
    conflict: bool = False
    gate: str | None = None
    gate_event_id: str | None = None


@dataclass
class Evidence:
    segments: dict[str, SegmentEvidence]
    rejected: list[RejectedEvent]


def _rejection(
    event: OperationalEvent, events: OperationalEvents, window: dt.timedelta, now: dt.datetime
) -> RejectionReason | None:
    if event.source not in events.meta.sources_available:
        return RejectionReason.SOURCE_UNKNOWN
    if event.source in events.meta.sources_degraded:
        return RejectionReason.SOURCE_DEGRADED
    if now - event.recorded_at > window:
        return RejectionReason.STALE
    return None


def _timing_state(event: OperationalEvent) -> TimingState | None:
    """Unknown statuses (e.g. BOARDING) carry no timing claim and are ignored."""
    if event.type is EventType.DELAY:
        return TimingState(TimingKind.DELAYED, event.delay_minutes, event.new_departure)
    if event.status in _ON_SCHEDULE_STATUSES:
        return TimingState(TimingKind.ON_SCHEDULE)
    if event.status in _CANCELLED_STATUSES:
        return TimingState(TimingKind.CANCELLED)
    return None


def reconcile(
    events: OperationalEvents, freshness_max_age_minutes: int, now: dt.datetime
) -> Evidence:
    window = dt.timedelta(minutes=freshness_max_age_minutes)
    rejected: list[RejectedEvent] = []
    latest_timing: dict[tuple[str, str], tuple[OperationalEvent, TimingState]] = {}
    latest_gate: dict[str, OperationalEvent] = {}
    segments: dict[str, SegmentEvidence] = {}

    for event in events.events:
        reason = _rejection(event, events, window, now)
        if reason is not None:
            rejected.append(RejectedEvent(event_id=event.event_id, reason=reason))
            continue
        segments.setdefault(event.segment_id, SegmentEvidence())
        if event.type is EventType.GATE_CHANGE:
            current = latest_gate.get(event.segment_id)
            if current is None or event.recorded_at > current.recorded_at:
                latest_gate[event.segment_id] = event
            continue
        state = _timing_state(event)
        if state is None:
            continue
        key = (event.segment_id, event.source)
        current_timing = latest_timing.get(key)
        if current_timing is None or event.recorded_at > current_timing[0].recorded_at:
            latest_timing[key] = (event, state)

    for (segment_id, _source), (event, state) in latest_timing.items():
        evidence = segments[segment_id]
        evidence.timing_event_ids.append(event.event_id)
        if evidence.conflict:
            continue
        if evidence.timing is None:
            evidence.timing = state
        elif not evidence.timing.same_state_as(state):
            evidence.conflict = True
            evidence.timing = None

    for segment_id, event in latest_gate.items():
        segments[segment_id].gate = event.gate
        segments[segment_id].gate_event_id = event.event_id

    return Evidence(segments=segments, rejected=rejected)
