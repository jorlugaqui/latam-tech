"""Recommendation (spec recommendation, design D1, D5, D6). Deterministic, read-only.

It never executes anything and never receives a write port: every proposal needs a
person's approval through the human hand-off (v1).
"""

import datetime as dt
import logging

from companion.ports.clock import Clock
from companion.ports.tools import OptionsReader, PolicyNotFound, PolicyReader, ToolUnavailable
from companion.schemas.assessment import Explanation, NextStep, Relevance
from companion.schemas.recommendation import (
    Entitlement,
    OptionView,
    Recommendation,
    RecommendationReason,
    RecommendationStatus,
)
from companion.schemas.tools import EligibleOptions, PolicyRules
from companion.services.assessment.criteria import missed_connection_params
from companion.services.options.selection import Selection, build_context, select
from companion.services.policy.entitlements import evaluate_rules
from companion.services.policy.facts import collect_facts
from companion.services.trip_access import NEXT_STEP, TripAccess, VerifiedTrip

logger = logging.getLogger(__name__)

_ENTITLEMENT_TEXT = {
    "REBOOK_NO_FEE": "rebooking at no extra cost",
    "PRIORITY_HANDLING": "priority handling",
    "MEAL_VOUCHER": "a meal voucher",
    "CASH_COMPENSATION": "cash compensation",
}
_NEEDS_AGENT_TEXT = {
    RecommendationReason.POLICY_UNAVAILABLE: (
        "We can't confirm which policy applies to your trip automatically."
    ),
    RecommendationReason.OPTIONS_UNAVAILABLE: "We can't load alternative flights right now.",
    RecommendationReason.OPTIONS_EXPIRED: "The available flights changed while we checked.",
    RecommendationReason.NO_ELIGIBLE_OPTION: (
        "None of the available flights fits your trip and your entitlements."
    ),
}


def _scenario(reason_codes: set[str]) -> str:
    return "CANCELLATION" if "CANCELLATION" in reason_codes else "DELAY"


def _hhmm(moment: dt.datetime | None) -> str:
    return moment.strftime("%H:%M") if moment else ""


def _proposed_explanation(
    policy: PolicyRules, entitlements: list[Entitlement], best: OptionView
) -> Explanation:
    details = [
        f"Under policy {policy.version}, rule {e.rule_id} gives you "
        f"{_ENTITLEMENT_TEXT.get(e.code, e.code)}"
        + (", reviewed by an agent." if e.requires_human_approval else ".")
        for e in entitlements
    ]
    details.append(
        f"Recommended: {best.flight_number} from {best.origin} to {best.destination}, "
        f"departing {best.departure.date().isoformat() if best.departure else ''} at "
        f"{_hhmm(best.departure)} (local time)."
    )
    details.append("An agent confirms any change before it is made.")
    return Explanation(headline="Here is what your fare's policy gives you.", details=details)


class RecommendationService:
    def __init__(
        self,
        access: TripAccess,
        policies: PolicyReader,
        options: OptionsReader,
        clock: Clock,
    ) -> None:
        self._access = access
        self._policies = policies
        self._options = options
        self._clock = clock

    def recommend(self, booking_id: str, last_name: str, request_id: str) -> Recommendation:
        trip = self._access.verified_assessment(booking_id, last_name, request_id)
        return self.recommend_for(trip)

    def recommend_for(self, trip: VerifiedTrip) -> Recommendation:
        """For a trip already verified and recorded (shared with the human hand-off)."""
        relevance = trip.assessment.relevance
        if relevance is not Relevance.DISRUPTIVE:
            return Recommendation(
                status=RecommendationStatus.NOT_APPLICABLE,
                explanation=Explanation(
                    headline="There are no options to review for this trip.",
                    details=(
                        ["We're confirming your flight status. An agent can help you."]
                        if relevance is Relevance.UNVERIFIED
                        else []
                    ),
                ),
                next_step=NEXT_STEP[relevance],
            )

        policy = self._policy(trip)
        if policy is None:
            return self._needs_agent(trip, RecommendationReason.POLICY_UNAVAILABLE)
        outcome = evaluate_rules(policy, collect_facts(trip.facts, trip.assessment))
        base = {
            "policy_version": policy.version,
            "entitlements": outcome.entitlements,
            "unevaluated_rules": outcome.unevaluated_rules,
        }

        try:
            options = self._fresh_options(trip)
        except ToolUnavailable:
            return self._needs_agent(trip, RecommendationReason.OPTIONS_UNAVAILABLE, **base)
        expires_at = self._expiry(options)
        if expires_at < self._clock.now():
            return self._needs_agent(trip, RecommendationReason.OPTIONS_EXPIRED, **base)

        if trip.rules is None:  # cannot happen for DISRUPTIVE; fail closed if it ever does
            return self._needs_agent(trip, RecommendationReason.POLICY_UNAVAILABLE, **base)
        ctx = build_context(
            trip.facts,
            trip.assessment,
            outcome.entitlements,
            policy,
            trip.airports,
            missed_connection_params(trip.rules.criteria),
        )
        selection = select(options.options, ctx)
        self._log(trip, policy, selection)
        if not selection.eligible:
            return self._needs_agent(
                trip,
                RecommendationReason.NO_ELIGIBLE_OPTION,
                excluded=selection.excluded,
                options_expire_at=expires_at,
                **base,
            )
        return Recommendation(
            status=RecommendationStatus.PROPOSED,
            options=selection.eligible,
            excluded=selection.excluded,
            options_expire_at=expires_at,
            explanation=_proposed_explanation(policy, outcome.entitlements, selection.eligible[0]),
            next_step=NextStep.RECOMMENDATION,
            **base,
        )

    def _policy(self, trip: VerifiedTrip) -> PolicyRules | None:
        scenario = _scenario({r.code for r in trip.assessment.reasons})
        try:
            policy = self._policies.get_policy_rules(scenario)
        except (PolicyNotFound, ToolUnavailable):
            logger.warning(
                "no usable policy booking=%s scenario=%s", trip.facts.booking_id, scenario
            )
            return None
        if policy.effective_from > trip.now.date():
            logger.warning("policy %s not yet in effect", policy.version)
            return None
        return policy

    @staticmethod
    def _expiry(options: EligibleOptions) -> dt.datetime:
        return options.meta.retrieved_at + dt.timedelta(seconds=options.meta.ttl_seconds)

    def _fresh_options(self, trip: VerifiedTrip) -> EligibleOptions:
        """Options are candidates with a TTL: an expired answer is fetched once more."""
        options = self._options.get_eligible_options(trip.context)
        if self._expiry(options) < self._clock.now():
            options = self._options.get_eligible_options(trip.context)
        return options

    @staticmethod
    def _needs_agent(
        trip: VerifiedTrip, reason: RecommendationReason, **fields: object
    ) -> Recommendation:
        logger.info(
            "recommendation booking=%s status=NEEDS_AGENT reason=%s", trip.facts.booking_id, reason
        )
        return Recommendation(
            status=RecommendationStatus.NEEDS_AGENT,
            reason=reason,
            explanation=Explanation(
                headline="An agent needs to review your options.",
                details=[_NEEDS_AGENT_TEXT[reason], "An agent can help you with your trip."],
            ),
            next_step=NextStep.HUMAN_ASSISTANCE,
            **fields,
        )

    @staticmethod
    def _log(trip: VerifiedTrip, policy: PolicyRules, selection: Selection) -> None:
        logger.info(
            "recommendation booking=%s policy=%s eligible=%s excluded=%s",
            trip.facts.booking_id,
            policy.version,
            ",".join(o.option_id for o in selection.eligible) or "-",
            ",".join(f"{e.option_id}:{'+'.join(e.codes)}" for e in selection.excluded) or "-",
        )
