"""Option filters with the Specification pattern (spec recommendation, design D4).

Each filter is one small object with a reason code. Adding a rule means adding a class to
``SPECIFICATIONS``; the selector never changes. Route and time checks apply to REBOOK
options only (a REFUND has no flight).
"""

import datetime as dt
from dataclasses import dataclass
from typing import ClassVar, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from companion.schemas.assessment import AirportInfo
from companion.schemas.recommendation import ExclusionCode
from companion.schemas.tools import EligibleOption, PolicyRules

REBOOK = "REBOOK"
REBOOK_ENTITLEMENT = "REBOOK_NO_FEE"


@dataclass(frozen=True)
class SelectionContext:
    entitlements: frozenset[str]
    party_size: int
    policy: PolicyRules
    anchor_airport: str | None
    final_destination: str | None
    earliest_departure: dt.datetime | None
    airports: dict[str, AirportInfo]


def local_departure(option: EligibleOption, airports: dict[str, AirportInfo]) -> dt.datetime | None:
    """The option's departure as an aware datetime at its origin airport."""
    if option.date is None or option.departure is None or option.origin not in airports:
        return None
    try:
        zone = ZoneInfo(airports[option.origin].iana_tz)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return dt.datetime.combine(option.date, option.departure, zone)


class OptionSpecification(Protocol):
    code: ClassVar[ExclusionCode]

    def excludes(self, option: EligibleOption, ctx: SelectionContext) -> bool: ...


class NotEntitled:
    code = ExclusionCode.NOT_ENTITLED

    def excludes(self, option: EligibleOption, ctx: SelectionContext) -> bool:
        # REFUND is never offered in this version; REBOOK needs a rebook entitlement.
        return not (option.type == REBOOK and REBOOK_ENTITLEMENT in ctx.entitlements)


class InsufficientSeats:
    code = ExclusionCode.INSUFFICIENT_SEATS

    def excludes(self, option: EligibleOption, ctx: SelectionContext) -> bool:
        # The party is never split across options.
        return option.type == REBOOK and (option.seats_available or 0) < ctx.party_size


class FeeConflictsEntitlement:
    code = ExclusionCode.FEE_CONFLICTS_ENTITLEMENT

    def excludes(self, option: EligibleOption, ctx: SelectionContext) -> bool:
        return (
            option.type == REBOOK
            and REBOOK_ENTITLEMENT in ctx.entitlements
            and (option.fare_difference or 0) > 0
        )


class WrongRoute:
    code = ExclusionCode.WRONG_ROUTE

    def excludes(self, option: EligibleOption, ctx: SelectionContext) -> bool:
        return option.type == REBOOK and (
            option.origin != ctx.anchor_airport or option.destination != ctx.final_destination
        )


class DepartsTooEarly:
    code = ExclusionCode.DEPARTS_TOO_EARLY

    def excludes(self, option: EligibleOption, ctx: SelectionContext) -> bool:
        if option.type != REBOOK or ctx.earliest_departure is None:
            return False
        departure = local_departure(option, ctx.airports)
        # A departure we cannot place in time cannot be shown to be reachable.
        return departure is None or departure < ctx.earliest_departure


class PolicySuperseded:
    code = ExclusionCode.POLICY_SUPERSEDED

    def excludes(self, option: EligibleOption, ctx: SelectionContext) -> bool:
        return option.policy_ref in ctx.policy.meta.superseded_versions


class LowConfidence:
    code = ExclusionCode.LOW_CONFIDENCE

    def excludes(self, option: EligibleOption, ctx: SelectionContext) -> bool:
        return option.confidence == "LOW"


SPECIFICATIONS: tuple[OptionSpecification, ...] = (
    NotEntitled(),
    InsufficientSeats(),
    FeeConflictsEntitlement(),
    WrongRoute(),
    DepartsTooEarly(),
    PolicySuperseded(),
    LowConfidence(),
)
