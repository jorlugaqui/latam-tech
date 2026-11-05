"""Disruption solver (spec disruption-assessment, design D1 and D4). Deterministic.

``DisruptionSolver`` is the Strategy seam; ``DeterministicSolver`` is the only
implementation. It builds per-segment impact facts (status, estimated times, gate,
connection outcome) from accepted evidence, then applies the enabled criteria of the rule
set and the tier precedence DISRUPTIVE > UNVERIFIED > INFORMATIONAL > NONE.
"""

import datetime as dt
from typing import Protocol

from companion.schemas.assessment import (
    AirportInfo,
    Assessment,
    ConnectionImpact,
    ConnectionStatus,
    Reason,
    ReasonCode,
    Relevance,
    RelevanceRuleSet,
    SegmentImpact,
    SegmentStatus,
    Tier,
    TripFacts,
)
from companion.schemas.tools import OperationalEvents
from companion.services.assessment.criteria import (
    Criterion,
    InvalidRuleSet,
    MissedConnectionCriterion,
    build_criteria,
    missed_connection_params,
)
from companion.services.assessment.reconciliation import (
    Evidence,
    SegmentEvidence,
    TimingKind,
    reconcile,
)
from companion.services.assessment.timeline import (
    ResolvedSegment,
    delay_is_consistent,
    estimate,
    resolve_segment,
    shift,
)


class DisruptionSolver(Protocol):
    def assess(
        self,
        facts: TripFacts,
        events: OperationalEvents | None,
        rules: RelevanceRuleSet | None,
        airports: dict[str, AirportInfo],
        now: dt.datetime,
    ) -> Assessment: ...


def _base(resolved: ResolvedSegment) -> dict[str, object]:
    segment = resolved.facts
    return {
        "segment_id": segment.segment_id,
        "flight_number": segment.flight_number,
        "origin": segment.origin,
        "destination": segment.destination,
        "scheduled_departure": resolved.departure,
        "scheduled_arrival": resolved.arrival,
    }


def _unverified(resolved: ResolvedSegment, reason: str, evidence: list[str]) -> SegmentImpact:
    return SegmentImpact(
        **_base(resolved),
        status=SegmentStatus.UNVERIFIED,
        unverified_reason=reason,
        evidence=evidence,
    )


def _impact(resolved: ResolvedSegment, evidence: SegmentEvidence | None) -> SegmentImpact:
    if resolved.unresolved_reason is not None:
        return _unverified(resolved, resolved.unresolved_reason, [])
    if evidence is None or (evidence.timing is None and not evidence.conflict):
        return _unverified(resolved, ReasonCode.NO_FRESH_EVIDENCE, [])
    ids = sorted(evidence.timing_event_ids)
    if evidence.conflict:
        return _unverified(resolved, ReasonCode.SOURCE_CONFLICT, ids)

    gate = {"gate": evidence.gate, "gate_event_id": evidence.gate_event_id}
    timing = evidence.timing
    if timing.kind is TimingKind.CANCELLED:
        return SegmentImpact(
            **_base(resolved), status=SegmentStatus.CANCELLED, evidence=ids, **gate
        )
    if timing.kind is TimingKind.ON_SCHEDULE:
        return SegmentImpact(
            **_base(resolved), status=SegmentStatus.ON_SCHEDULE, evidence=ids, **gate
        )
    scheduled = resolved.facts.scheduled_departure
    if timing.delay_minutes is None or not delay_is_consistent(
        scheduled, timing.delay_minutes, timing.new_departure
    ):
        return _unverified(resolved, ReasonCode.INCONSISTENT_EVENT, ids)
    departure, arrival = estimate(resolved, timing.delay_minutes)
    return SegmentImpact(
        **_base(resolved),
        status=SegmentStatus.DELAYED,
        delay_minutes=timing.delay_minutes,
        estimated_departure=departure,
        estimated_arrival=arrival,
        evidence=ids,
        **gate,
    )


def _connection(
    current: SegmentImpact,
    following: SegmentImpact,
    cancelled_before: bool,
    mct: MissedConnectionCriterion.Params,
) -> ConnectionStatus:
    if cancelled_before or current.status is SegmentStatus.CANCELLED:
        return ConnectionStatus.UNREACHABLE
    if SegmentStatus.UNVERIFIED in (current.status, following.status):
        return ConnectionStatus.UNKNOWN
    arrival = current.estimated_arrival or current.scheduled_arrival
    departure = following.estimated_departure or following.scheduled_departure
    if arrival is None or departure is None:
        return ConnectionStatus.UNKNOWN
    ready = shift(arrival, mct.mct_for(current.destination or ""))
    return ConnectionStatus.MISSED if ready > departure else ConnectionStatus.OK


def _with_connections(
    impacts: list[SegmentImpact], mct: MissedConnectionCriterion.Params
) -> list[SegmentImpact]:
    result: list[SegmentImpact] = []
    cancelled_before = False
    for index, current in enumerate(impacts):
        following = impacts[index + 1] if index + 1 < len(impacts) else None
        if following is not None and current.destination == following.origin:
            status = _connection(current, following, cancelled_before, mct)
            current = current.model_copy(
                update={
                    "connection": ConnectionImpact(
                        to_segment_id=following.segment_id, status=status
                    )
                }
            )
        cancelled_before = cancelled_before or current.status is SegmentStatus.CANCELLED
        result.append(current)
    return result


def _segment_reasons(impacts: list[SegmentImpact]) -> list[Reason]:
    return [
        Reason(code=i.unverified_reason, segment_ids=[i.segment_id], event_ids=i.evidence)
        for i in impacts
        if i.status is SegmentStatus.UNVERIFIED and i.unverified_reason is not None
    ]


def _reasons_for(tier: Tier, criteria: list[tuple[Tier, Criterion]], impacts) -> list[Reason]:
    return [r for t, c in criteria if t is tier for r in c.evaluate(impacts)]


class DeterministicSolver:
    def assess(
        self,
        facts: TripFacts,
        events: OperationalEvents | None,
        rules: RelevanceRuleSet | None,
        airports: dict[str, AirportInfo],
        now: dt.datetime,
    ) -> Assessment:
        resolved = [resolve_segment(segment, airports) for segment in facts.segments]

        try:
            if rules is None:
                raise InvalidRuleSet("no rule set in effect")
            criteria = build_criteria(rules.criteria)
            mct = missed_connection_params(rules.criteria)
        except InvalidRuleSet:
            return self._global_failure(resolved, ReasonCode.RULES_UNAVAILABLE, None, now)
        if events is None:
            return self._global_failure(resolved, ReasonCode.EVENTS_UNAVAILABLE, rules.version, now)

        evidence: Evidence = reconcile(events, rules.freshness_max_age_minutes, now)
        impacts = _with_connections(
            [_impact(r, evidence.segments.get(r.facts.segment_id)) for r in resolved], mct
        )

        disruptive = _reasons_for(Tier.DISRUPTIVE, criteria, impacts)
        if disruptive:
            relevance, reasons = Relevance.DISRUPTIVE, disruptive
        elif unverified := _segment_reasons(impacts):
            relevance, reasons = Relevance.UNVERIFIED, unverified
        elif informational := _reasons_for(Tier.INFORMATIONAL, criteria, impacts):
            relevance, reasons = Relevance.INFORMATIONAL, informational
        else:
            relevance, reasons = Relevance.NONE, []

        return Assessment(
            relevance=relevance,
            reasons=reasons,
            segments=impacts,
            rejected=evidence.rejected,
            rules_version=rules.version,
            assessed_at=now,
        )

    @staticmethod
    def _global_failure(
        resolved: list[ResolvedSegment], code: ReasonCode, version: str | None, now: dt.datetime
    ) -> Assessment:
        impacts = [_unverified(r, code, []) for r in resolved]
        impacts = _with_connections(
            impacts, MissedConnectionCriterion.Params(default_mct_minutes=0)
        )
        return Assessment(
            relevance=Relevance.UNVERIFIED,
            reasons=[Reason(code=code, segment_ids=[r.facts.segment_id for r in resolved])],
            segments=impacts,
            rules_version=version,
            assessed_at=now,
        )
