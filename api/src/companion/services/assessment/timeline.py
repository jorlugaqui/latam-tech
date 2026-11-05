"""Time resolution (spec disruption-assessment, design D5). Deterministic.

Schedule fields are local wall times at the airport they refer to (departure at the
origin, arrival at the destination). They become aware datetimes in that airport's IANA
zone. All arithmetic happens in UTC, so DST changes and midnight rollovers are exact.
"""

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from companion.schemas.assessment import AirportInfo, ReasonCode, SegmentFacts

_MINUTES_PER_DAY = 24 * 60
_MAX_ARRIVAL_DAYS_AFTER_DEPARTURE = 2


@dataclass(frozen=True)
class ResolvedSegment:
    facts: SegmentFacts
    departure: dt.datetime | None = None
    arrival: dt.datetime | None = None
    unresolved_reason: ReasonCode | None = None


def _zone(code: str, airports: dict[str, AirportInfo]) -> ZoneInfo | None:
    airport = airports.get(code)
    if airport is None:
        return None
    try:
        return ZoneInfo(airport.iana_tz)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def resolve_segment(segment: SegmentFacts, airports: dict[str, AirportInfo]) -> ResolvedSegment:
    if (
        segment.origin is None
        or segment.destination is None
        or segment.date is None
        or segment.scheduled_departure is None
        or segment.scheduled_arrival is None
    ):
        return ResolvedSegment(segment, unresolved_reason=ReasonCode.CONTEXT_INCOMPLETE)

    origin_zone = _zone(segment.origin, airports)
    destination_zone = _zone(segment.destination, airports)
    if origin_zone is None or destination_zone is None:
        return ResolvedSegment(segment, unresolved_reason=ReasonCode.AIRPORT_UNKNOWN)

    departure = dt.datetime.combine(segment.date, segment.scheduled_departure, origin_zone)
    # The contract has no arrival date: the arrival is the first matching local time
    # after departure.
    arrival = dt.datetime.combine(segment.date, segment.scheduled_arrival, destination_zone)
    for _ in range(_MAX_ARRIVAL_DAYS_AFTER_DEPARTURE):
        if arrival > departure:
            break
        arrival = dt.datetime.combine(
            arrival.date() + dt.timedelta(days=1), segment.scheduled_arrival, destination_zone
        )
    return ResolvedSegment(segment, departure=departure, arrival=arrival)


def shift(moment: dt.datetime, minutes: int) -> dt.datetime:
    """Add minutes in UTC and come back to the same zone (aware + timedelta is wall time)."""
    shifted = moment.astimezone(dt.UTC) + dt.timedelta(minutes=minutes)
    return shifted.astimezone(moment.tzinfo)


def estimate(resolved: ResolvedSegment, delay_minutes: int) -> tuple[dt.datetime, dt.datetime]:
    """Estimated departure and arrival; assumes the flight duration does not change."""
    if resolved.departure is None or resolved.arrival is None:
        raise ValueError("segment times are not resolved")
    return shift(resolved.departure, delay_minutes), shift(resolved.arrival, delay_minutes)


def delay_is_consistent(
    scheduled_departure: dt.time, delay_minutes: int, new_departure: dt.time | None
) -> bool:
    """``scheduled + delay == new_departure`` on the local clock, modulo one day."""
    if new_departure is None:
        return True
    scheduled = scheduled_departure.hour * 60 + scheduled_departure.minute
    reported = new_departure.hour * 60 + new_departure.minute
    return (scheduled + delay_minutes) % _MINUTES_PER_DAY == reported
