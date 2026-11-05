"""Design D1: one verified path (surname, recompute, record) shared by every trip call."""

import pytest

from companion.schemas.assessment import Relevance
from companion.services.assessment.solver import DeterministicSolver
from companion.services.trip_access import TripAccess, TripNotFound
from tests.unit.data.brief import NOW, events_payload, trip_context_payload
from tests.unit.data.reference import AIRPORTS, rel_2026_09
from tests.unit.fakes import (
    FakeAirportDirectory,
    FakeAssessmentLog,
    FakeRuleSetRepository,
    FakeToolsClient,
    FixedClock,
)


def _access(log: FakeAssessmentLog, tools: FakeToolsClient | None = None) -> TripAccess:
    tools = tools or FakeToolsClient({"ABC123": trip_context_payload()}, events_payload())
    return TripAccess(
        trips=tools,
        events=tools,
        rules=FakeRuleSetRepository(rel_2026_09()),
        airports=FakeAirportDirectory(AIRPORTS),
        clock=FixedClock(NOW),
        solver=DeterministicSolver(),
        assessment_log=log,
    )


def test_verified_trip_carries_the_record_id() -> None:
    log = FakeAssessmentLog()

    trip = _access(log).verified_assessment("ABC123", "Silva", "req-1")

    assert trip.assessment.relevance is Relevance.DISRUPTIVE
    assert trip.assessment_id == log.records[0][3]
    assert trip.facts.passengers[0].first_name == "María"
    assert trip.context.booking_id == "ABC123"
    assert trip.rules.version == "REL-2026-09"
    assert set(trip.airports) == {"SCL", "LIM", "MEX"}


def test_mismatch_reads_no_events_and_records_nothing() -> None:
    log = FakeAssessmentLog()
    tools = FakeToolsClient({"ABC123": trip_context_payload()}, events_payload())

    with pytest.raises(TripNotFound):
        _access(log, tools).verified_assessment("ABC123", "Rojas", "req-1")

    assert tools.calls == ["context:ABC123"]
    assert log.records == []


def test_failed_record_gives_no_id() -> None:
    trip = _access(FakeAssessmentLog(fail=True)).verified_assessment("ABC123", "Silva", "r")

    assert trip.assessment_id is None
    assert trip.assessment.relevance is Relevance.DISRUPTIVE
