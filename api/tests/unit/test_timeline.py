"""Spec disruption-assessment: airport time zones, estimated times, consistency."""

from datetime import date, time

from companion.schemas.assessment import AirportInfo, ReasonCode, SegmentFacts
from companion.services.assessment.timeline import (
    delay_is_consistent,
    estimate,
    resolve_segment,
)
from tests.unit.data.reference import AIRPORTS

S1 = SegmentFacts(
    segment_id="S1",
    flight_number="LA500",
    origin="SCL",
    destination="LIM",
    date=date(2026, 9, 15),
    scheduled_departure=time(14, 30),
    scheduled_arrival=time(17, 55),
)


def test_brief_segment_in_two_time_zones() -> None:
    resolved = resolve_segment(S1, AIRPORTS)

    assert resolved.unresolved_reason is None
    assert resolved.departure.isoformat() == "2026-09-15T14:30:00-03:00"
    assert resolved.arrival.isoformat() == "2026-09-15T17:55:00-05:00"


def test_chile_before_its_dst_change_is_utc_minus_4() -> None:
    resolved = resolve_segment(S1.model_copy(update={"date": date(2026, 8, 20)}), AIRPORTS)

    assert resolved.departure.isoformat() == "2026-08-20T14:30:00-04:00"


def test_estimated_arrival_follows_delay() -> None:
    departure, arrival = estimate(resolve_segment(S1, AIRPORTS), 160)

    assert departure.isoformat() == "2026-09-15T17:10:00-03:00"
    assert arrival.isoformat() == "2026-09-15T20:35:00-05:00"


def test_delayed_arrival_rolls_over_midnight() -> None:
    nite = S1.model_copy(
        update={"scheduled_departure": time(20, 25), "scheduled_arrival": time(22, 30)}
    )

    _, arrival = estimate(resolve_segment(nite, AIRPORTS), 120)

    assert arrival.isoformat() == "2026-09-16T00:30:00-05:00"


def test_arrival_earlier_on_the_clock_is_the_next_day() -> None:
    red_eye = S1.model_copy(
        update={"scheduled_departure": time(23, 30), "scheduled_arrival": time(1, 10)}
    )

    resolved = resolve_segment(red_eye, AIRPORTS)

    assert resolved.arrival.isoformat() == "2026-09-16T01:10:00-05:00"


def test_consistent_brief_delay() -> None:
    assert delay_is_consistent(time(14, 30), 160, time(17, 10))


def test_inconsistent_delay() -> None:
    assert not delay_is_consistent(time(14, 30), 160, time(16, 0))


def test_consistency_rolls_over_midnight() -> None:
    assert delay_is_consistent(time(23, 0), 90, time(0, 30))


def test_delay_without_new_departure_is_consistent() -> None:
    assert delay_is_consistent(time(14, 30), 160, None)


def test_unknown_airport() -> None:
    resolved = resolve_segment(S1.model_copy(update={"destination": "XXX"}), AIRPORTS)

    assert resolved.unresolved_reason is ReasonCode.AIRPORT_UNKNOWN
    assert resolved.arrival is None


def test_invalid_time_zone_counts_as_unknown_airport() -> None:
    airports = {**AIRPORTS, "LIM": AirportInfo(iata="LIM", iana_tz="Mars/Olympus")}

    assert resolve_segment(S1, airports).unresolved_reason is ReasonCode.AIRPORT_UNKNOWN


def test_missing_scheduled_arrival_is_incomplete_context() -> None:
    resolved = resolve_segment(S1.model_copy(update={"scheduled_arrival": None}), AIRPORTS)

    assert resolved.unresolved_reason is ReasonCode.CONTEXT_INCOMPLETE
