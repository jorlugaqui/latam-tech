"""Trip status lookup (spec trip-status). Deterministic orchestration.

Verification, recomputation and recording live in ``TripAccess`` (shared with the
recommendation and the human hand-off); this service only shapes the passenger response.
"""

from companion.ports.audit import AssessmentLog
from companion.ports.clock import Clock
from companion.ports.rules import AirportDirectory, RuleSetRepository
from companion.ports.tools import OperationalEventsReader, TripContextReader
from companion.schemas.assessment import Assessment, TripFacts
from companion.schemas.trip_status import (
    AssessmentView,
    ConnectionView,
    PassengerView,
    ReasonView,
    SegmentView,
    TripStatusResponse,
)
from companion.services.assessment.explanation import ExplanationComposer
from companion.services.assessment.solver import DisruptionSolver
from companion.services.trip_access import (
    NEXT_STEP,
    TripAccess,
    TripContextUnavailable,
    TripNotFound,
)

__all__ = ["TripContextUnavailable", "TripNotFound", "TripStatusService"]


def _response(
    facts: TripFacts, assessment: Assessment, composer: ExplanationComposer
) -> TripStatusResponse:
    return TripStatusResponse(
        booking_id=facts.booking_id,
        passengers=[PassengerView(first_name=p.first_name, type=p.type) for p in facts.passengers],
        segments=[
            SegmentView(
                segment_id=s.segment_id,
                flight_number=s.flight_number,
                origin=s.origin,
                destination=s.destination,
                scheduled_departure=s.scheduled_departure,
                scheduled_arrival=s.scheduled_arrival,
                estimated_departure=s.estimated_departure,
                estimated_arrival=s.estimated_arrival,
                status=s.status,
                delay_minutes=s.delay_minutes,
                gate=s.gate,
                connection=(
                    ConnectionView(
                        to_segment_id=s.connection.to_segment_id, status=s.connection.status
                    )
                    if s.connection
                    else None
                ),
            )
            for s in assessment.segments
        ],
        assessment=AssessmentView(
            relevance=assessment.relevance,
            reasons=[
                ReasonView(code=r.code, segment_ids=r.segment_ids, event_ids=r.event_ids)
                for r in assessment.reasons
            ],
            rules_version=assessment.rules_version,
            assessed_at=assessment.assessed_at,
        ),
        explanation=composer.compose(assessment, facts),
        next_step=NEXT_STEP[assessment.relevance],
    )


class TripStatusService:
    def __init__(
        self,
        trips: TripContextReader,
        events: OperationalEventsReader,
        rules: RuleSetRepository,
        airports: AirportDirectory,
        clock: Clock,
        solver: DisruptionSolver,
        composer: ExplanationComposer,
        assessment_log: AssessmentLog,
    ) -> None:
        self._access = TripAccess(trips, events, rules, airports, clock, solver, assessment_log)
        self._composer = composer

    def lookup(self, booking_id: str, last_name: str, request_id: str) -> TripStatusResponse:
        trip = self._access.verified_assessment(booking_id, last_name, request_id)
        return _response(trip.facts, trip.assessment, self._composer)
