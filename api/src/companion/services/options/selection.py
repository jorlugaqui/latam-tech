"""Run every option specification, keep the clean ones, and rank them (design D4)."""

from dataclasses import dataclass

from companion.schemas.assessment import (
    AirportInfo,
    Assessment,
    ConnectionStatus,
    SegmentStatus,
    TripFacts,
)
from companion.schemas.recommendation import Entitlement, Exclusion, OptionView
from companion.schemas.tools import EligibleOption, PolicyRules
from companion.services.assessment.criteria import MissedConnectionCriterion
from companion.services.assessment.timeline import shift
from companion.services.options.specifications import (
    SPECIFICATIONS,
    SelectionContext,
    local_departure,
)

__all__ = ["Selection", "SelectionContext", "build_context", "select"]

_CONFIDENCE_RANK = {"HIGH": 0, "MEDIUM": 1}


@dataclass(frozen=True)
class Selection:
    eligible: list[OptionView]
    excluded: list[Exclusion]


def build_context(
    trip: TripFacts,
    assessment: Assessment,
    entitlements: list[Entitlement],
    policy: PolicyRules,
    airports: dict[str, AirportInfo],
    mct: MissedConnectionCriterion.Params,
) -> SelectionContext:
    """Anchor on the first missed connection (depart after arrival + MCT); otherwise on the
    origin of the first delayed segment, with no earliest bound."""
    anchor, earliest = None, None
    for segment in assessment.segments:
        if segment.connection is not None and segment.connection.status is ConnectionStatus.MISSED:
            arrival = segment.estimated_arrival or segment.scheduled_arrival
            anchor = segment.destination
            if arrival is not None and anchor is not None:
                earliest = shift(arrival, mct.mct_for(anchor))
            break
    else:
        delayed = [s for s in assessment.segments if s.status is SegmentStatus.DELAYED]
        anchor = delayed[0].origin if delayed else None
    final = assessment.segments[-1].destination if assessment.segments else None
    return SelectionContext(
        entitlements=frozenset(e.code for e in entitlements),
        party_size=len(trip.passengers),
        policy=policy,
        anchor_airport=anchor,
        final_destination=final,
        earliest_departure=earliest,
        airports=airports,
    )


def _view(option: EligibleOption, ctx: SelectionContext) -> OptionView:
    return OptionView(
        option_id=option.option_id,
        type=option.type,
        flight_number=option.flight_number,
        origin=option.origin,
        destination=option.destination,
        departure=local_departure(option, ctx.airports),
        fare_difference=option.fare_difference,
        currency=option.currency,
        confidence=option.confidence,
    )


def select(options: list[EligibleOption], ctx: SelectionContext) -> Selection:
    eligible: list[OptionView] = []
    excluded: list[Exclusion] = []
    for option in options:
        codes = [spec.code for spec in SPECIFICATIONS if spec.excludes(option, ctx)]
        if codes:
            excluded.append(Exclusion(option_id=option.option_id, codes=codes))
        else:
            eligible.append(_view(option, ctx))
    eligible.sort(
        key=lambda o: (
            _CONFIDENCE_RANK.get(o.confidence, len(_CONFIDENCE_RANK)),
            o.departure is None,
            o.departure.timestamp() if o.departure else 0,
        )
    )
    return Selection(eligible=eligible, excluded=excluded)
