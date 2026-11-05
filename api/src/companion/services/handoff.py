"""Human hand-off (spec human-handoff, design D7-D9). The only holder of the write port.

v1: the human case is the approval mechanism for every action. The server decides
whether and why to escalate from a recomputed assessment; the intent is recorded before
the tool is called; one active case per booking; an unknown outcome is never retried.
"""

import logging
from collections import Counter
from dataclasses import dataclass

from companion.ports.cases import CaseRepository, CasesUnavailable, NewCase
from companion.ports.handoff import HandoffIndeterminate, HandoffRejected, HumanCaseWriter
from companion.schemas.assessment import Relevance
from companion.schemas.handoff import (
    CaseReason,
    CaseStatus,
    Evidence,
    HumanCase,
    HumanCaseResponse,
    OptionSnapshot,
    PartyComposition,
)
from companion.schemas.recommendation import Recommendation
from companion.services.recommendation import RecommendationService
from companion.services.trip_access import TripAccess, VerifiedTrip

logger = logging.getLogger(__name__)

INDETERMINATE_WAIT_MINUTES = 45


class NothingToEscalate(Exception):
    """The trip has no disruption or doubt to hand to a person."""


class OptionNotEligible(Exception):
    """The requested option is not currently eligible (or not applicable)."""


class HandoffUnavailable(Exception):
    """The case could not be recorded or was definitely not created."""


@dataclass(frozen=True)
class HandoffResult:
    case: HumanCase
    created: bool


def _party(trip: VerifiedTrip) -> PartyComposition:
    counts = Counter(p.type for p in trip.facts.passengers)
    return PartyComposition(
        adults=counts["ADULT"],
        children=counts["CHILD"],
        infants=counts["INFANT"],
        includes_minor=counts["CHILD"] + counts["INFANT"] > 0,
    )


def _evidence(
    trip: VerifiedTrip,
    assessment_id: str,
    recommendation: Recommendation | None,
    option_id: str | None,
) -> Evidence:
    option = None
    if recommendation is not None and option_id is not None:
        chosen = next(o for o in recommendation.options if o.option_id == option_id)
        option = OptionSnapshot(**chosen.model_dump(), expires_at=recommendation.options_expire_at)
    return Evidence(
        booking_id=trip.facts.booking_id,
        assessment_id=assessment_id,
        relevance=trip.assessment.relevance,
        reasons=trip.assessment.reasons,
        rules_version=trip.assessment.rules_version,
        policy_version=recommendation.policy_version if recommendation else None,
        entitlements=recommendation.entitlements if recommendation else [],
        option=option,
        excluded_options=recommendation.excluded if recommendation else [],
        party=_party(trip),
    )


def response_for(case: HumanCase) -> HumanCaseResponse:
    if case.status is CaseStatus.OPEN:
        message = (
            f"Your request was sent to an agent (case {case.case_id}). An agent will confirm "
            f"within {case.sla_minutes} minutes."
        )
    else:
        message = (
            "We're registering your request. If you don't hear from us within "
            f"{INDETERMINATE_WAIT_MINUTES} minutes, please contact the call center."
        )
    return HumanCaseResponse(
        status=case.status,
        reason=case.reason,
        case_id=case.case_id,
        queue=case.queue,
        sla_minutes=case.sla_minutes,
        message=message,
    )


class HumanCaseService:
    def __init__(
        self,
        access: TripAccess,
        recommendations: RecommendationService,
        cases: CaseRepository,
        writer: HumanCaseWriter,
    ) -> None:
        self._access = access
        self._recommendations = recommendations
        self._cases = cases
        self._writer = writer

    def request(
        self, booking_id: str, last_name: str, option_id: str | None, request_id: str
    ) -> HandoffResult:
        trip = self._access.verified_assessment(booking_id, last_name, request_id)
        reason, recommendation = self._reason(trip, option_id)
        if trip.assessment_id is None:
            # An action must be traceable to the decision it was based on.
            logger.error("human case refused booking=%s: assessment not recorded", booking_id)
            raise HandoffUnavailable
        evidence = _evidence(trip, trip.assessment_id, recommendation, option_id)

        try:
            case, created = self._cases.open_or_get_active(
                NewCase(
                    booking_id=booking_id,
                    reason=reason,
                    option_id=option_id,
                    assessment_id=trip.assessment_id,
                    evidence=evidence.model_dump(mode="json"),
                    request_id=request_id,
                )
            )
        except CasesUnavailable:
            raise HandoffUnavailable from None
        if not created:
            self._log(case, "existing")
            return HandoffResult(case, created=False)

        case = self._create(case, reason, evidence)
        self._log(case, "created")
        if case.status is CaseStatus.FAILED:
            raise HandoffUnavailable
        return HandoffResult(case, created=True)

    def _reason(
        self, trip: VerifiedTrip, option_id: str | None
    ) -> tuple[CaseReason, Recommendation | None]:
        relevance = trip.assessment.relevance
        if relevance is Relevance.UNVERIFIED:
            if option_id is not None:
                raise OptionNotEligible
            return CaseReason.STATUS_VERIFICATION, None
        if relevance is not Relevance.DISRUPTIVE:
            raise NothingToEscalate
        recommendation = self._recommendations.recommend_for(trip)
        if option_id is None:
            return CaseReason.ASSISTANCE_REQUIRED, recommendation
        if option_id not in {o.option_id for o in recommendation.options}:
            raise OptionNotEligible
        return CaseReason.OPTION_APPROVAL, recommendation

    def _create(self, case: HumanCase, reason: CaseReason, evidence: Evidence) -> HumanCase:
        try:
            created = self._writer.create(reason.value, evidence.model_dump(mode="json"))
        except HandoffIndeterminate:
            return self._move(case, CaseStatus.INDETERMINATE)  # never retried
        except HandoffRejected:
            return self._move(case, CaseStatus.FAILED)
        return self._move(
            case, CaseStatus.OPEN, created.case_id, created.queue, created.sla_minutes
        )

    def _move(
        self,
        case: HumanCase,
        target: CaseStatus,
        case_id: str | None = None,
        queue: str | None = None,
        sla_minutes: int | None = None,
    ) -> HumanCase:
        try:
            return self._cases.transition(case.id, target, case_id, queue, sla_minutes)
        except CasesUnavailable:
            # The tool already answered: tell the passenger the truth even if our record
            # lags behind (it stays REQUESTED, so the booking stays blocked from duplicates).
            logger.error("human case %s not updated to %s", case.id, target)
            return case.model_copy(
                update={
                    "status": target,
                    "case_id": case_id,
                    "queue": queue,
                    "sla_minutes": sla_minutes,
                }
            )

    @staticmethod
    def _log(case: HumanCase, outcome: str) -> None:
        logger.info(
            "human case booking=%s reason=%s status=%s case_id=%s outcome=%s",
            case.booking_id,
            case.reason,
            case.status,
            case.case_id or "-",
            outcome,
        )
