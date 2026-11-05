"""Facts that policy conditions may refer to: a registry of providers (design D3, OCP).

A provider reads only the verified trip and its assessment. ``None`` means unknown, which
the interpreter never treats as true. A new fact is a new entry here.
"""

from collections.abc import Callable

from companion.schemas.assessment import (
    Assessment,
    ConnectionStatus,
    SegmentStatus,
    TripFacts,
)
from companion.services.policy.conditions import FactValue

FactProvider = Callable[[TripFacts, Assessment], FactValue]
_MINOR_TYPES = {"CHILD", "INFANT"}


def _delay_minutes(_: TripFacts, assessment: Assessment) -> FactValue:
    delays = [
        s.delay_minutes
        for s in assessment.segments
        if s.status is SegmentStatus.DELAYED and s.delay_minutes is not None
    ]
    return max(delays, default=0)


def _missed_connection(_: TripFacts, assessment: Assessment) -> FactValue:
    return any(
        s.connection is not None and s.connection.status is ConnectionStatus.MISSED
        for s in assessment.segments
    )


def _group_includes_minor(trip: TripFacts, _: Assessment) -> FactValue:
    return any(p.type in _MINOR_TYPES for p in trip.passengers)


def _compensation_requested(_: TripFacts, __: Assessment) -> FactValue:
    return False  # not collected from the passenger in this version


def _international(_: TripFacts, __: Assessment) -> FactValue:
    return None  # airports carry no country yet (future work)


FACT_PROVIDERS: dict[str, FactProvider] = {
    "delay_minutes": _delay_minutes,
    "missed_connection": _missed_connection,
    "international": _international,
    "compensation_requested": _compensation_requested,
    "group_includes_minor": _group_includes_minor,
}


def collect_facts(trip: TripFacts, assessment: Assessment) -> dict[str, FactValue]:
    return {name: provider(trip, assessment) for name, provider in FACT_PROVIDERS.items()}
