"""Trip status lookup (spec trip-status, design D6-D8). Deterministic orchestration.

Order matters: the booking is verified by surname before any operational data is read,
and personal data is stripped into ``TripFacts`` before the assessment sees anything.
"""

import datetime as dt
import logging

from companion.ports.audit import AssessmentLog, AssessmentNotRecorded
from companion.ports.clock import Clock
from companion.ports.rules import AirportDirectory, RuleSetRepository, RulesUnavailable
from companion.ports.tools import (
    BookingNotFound,
    OperationalEventsReader,
    ToolUnavailable,
    TripContextReader,
)
from companion.schemas.assessment import (
    AirportInfo,
    Assessment,
    NextStep,
    PassengerFacts,
    Relevance,
    RelevanceRuleSet,
    SegmentFacts,
    TripFacts,
)
from companion.schemas.tools import OperationalEvents, TripContext
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
from companion.services.surname import surname_matches

logger = logging.getLogger(__name__)

_NEXT_STEP = {
    Relevance.DISRUPTIVE: NextStep.RECOMMENDATION,
    Relevance.UNVERIFIED: NextStep.HUMAN_ASSISTANCE,
    Relevance.INFORMATIONAL: NextStep.NONE,
    Relevance.NONE: NextStep.NONE,
}


class TripNotFound(Exception):
    """Unknown booking or surname mismatch: deliberately indistinguishable."""


class TripContextUnavailable(Exception):
    """The trip context tool failed; nothing can be shown."""


def _facts(context: TripContext) -> TripFacts:
    return TripFacts(
        booking_id=context.booking_id,
        passengers=[
            PassengerFacts(first_name=(p.name.split() or [""])[0], type=p.type)
            for p in context.passengers
        ],
        segments=[
            SegmentFacts(
                segment_id=s.segment_id,
                flight_number=s.flight_number,
                origin=s.origin,
                destination=s.destination,
                date=s.date,
                scheduled_departure=s.scheduled_departure,
                scheduled_arrival=s.scheduled_arrival,
            )
            for s in context.segments
        ],
    )


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
        next_step=_NEXT_STEP[assessment.relevance],
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
        self._trips = trips
        self._events = events
        self._rules = rules
        self._airports = airports
        self._clock = clock
        self._solver = solver
        self._composer = composer
        self._assessment_log = assessment_log

    def lookup(self, booking_id: str, last_name: str, request_id: str) -> TripStatusResponse:
        now = self._clock.now()
        try:
            context = self._trips.get_trip_context(booking_id)
        except BookingNotFound:
            logger.info("trip lookup booking=%s outcome=not_found", booking_id)
            raise TripNotFound from None
        except ToolUnavailable:
            logger.warning("trip lookup booking=%s outcome=trip_context_unavailable", booking_id)
            raise TripContextUnavailable from None

        if not surname_matches(last_name, [p.name for p in context.passengers]):
            logger.info("trip lookup booking=%s outcome=not_found", booking_id)
            raise TripNotFound

        facts = _facts(context)
        events = self._read_events(facts)
        rules, airports = self._read_rules(facts, now)
        assessment = self._solver.assess(facts, events, rules, airports, now)
        logger.info(
            "trip lookup booking=%s relevance=%s reasons=%s rules=%s rejected=%s",
            booking_id,
            assessment.relevance,
            ",".join(r.code for r in assessment.reasons) or "-",
            assessment.rules_version or "-",
            ",".join(f"{r.event_id}:{r.reason}" for r in assessment.rejected) or "-",
        )
        self._record(booking_id, assessment, request_id)
        return _response(facts, assessment, self._composer)

    def _record(self, booking_id: str, assessment: Assessment, request_id: str) -> None:
        # Audit trail (design D15). A lookup executes nothing, so a failed record is logged
        # and the passenger still gets the answer; actions must not proceed without one.
        try:
            self._assessment_log.record(booking_id, assessment, request_id)
        except AssessmentNotRecorded:
            logger.error("assessment not recorded booking=%s", booking_id)

    def _read_events(self, facts: TripFacts) -> OperationalEvents | None:
        try:
            return self._events.get_operational_events([s.segment_id for s in facts.segments])
        except ToolUnavailable:
            logger.warning("operational events unavailable booking=%s", facts.booking_id)
            return None

    def _read_rules(
        self, facts: TripFacts, now: dt.datetime
    ) -> tuple[RelevanceRuleSet | None, dict[str, AirportInfo]]:
        codes = {c for s in facts.segments for c in (s.origin, s.destination) if c}
        try:
            return self._rules.get_effective(now), self._airports.find(codes)
        except RulesUnavailable:
            logger.error("relevance rules unavailable booking=%s", facts.booking_id)
            return None, {}
