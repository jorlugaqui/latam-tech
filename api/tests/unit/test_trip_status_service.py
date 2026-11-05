"""Spec trip-status: orchestration, verification, failures, next step, logging."""

import logging

import pytest

from companion.ports.tools import ToolUnavailable
from companion.schemas.assessment import ConnectionStatus, NextStep, Relevance, SegmentStatus
from companion.services.assessment.explanation import TemplateComposer
from companion.services.assessment.solver import DeterministicSolver
from companion.services.trip_status import (
    TripContextUnavailable,
    TripNotFound,
    TripStatusService,
)
from tests.unit.data.brief import NOW, events_payload, trip_context_payload
from tests.unit.data.reference import AIRPORTS, rel_2026_09
from tests.unit.fakes import (
    FakeAirportDirectory,
    FakeAssessmentLog,
    FakeRuleSetRepository,
    FakeToolsClient,
    FixedClock,
)


def _service(
    tools: FakeToolsClient | None = None,
    rules: FakeRuleSetRepository | None = None,
    airports: FakeAirportDirectory | None = None,
    log: FakeAssessmentLog | None = None,
) -> TripStatusService:
    tools = tools or FakeToolsClient({"ABC123": trip_context_payload()}, events_payload())
    return TripStatusService(
        trips=tools,
        events=tools,
        rules=rules or FakeRuleSetRepository(rel_2026_09()),
        airports=airports or FakeAirportDirectory(AIRPORTS),
        clock=FixedClock(NOW),
        solver=DeterministicSolver(),
        composer=TemplateComposer(),
        assessment_log=log if log is not None else FakeAssessmentLog(),
    )


def test_brief_lookup() -> None:
    result = _service().lookup("ABC123", "Silva", "req-test")

    assert [(p.first_name, p.type) for p in result.passengers] == [
        ("María", "ADULT"),
        ("Tomás", "CHILD"),
    ]
    s1 = result.segments[0]
    assert s1.status is SegmentStatus.DELAYED
    assert s1.delay_minutes == 160
    assert s1.gate == "24"
    assert s1.connection.status is ConnectionStatus.MISSED
    assert s1.scheduled_departure.isoformat() == "2026-09-15T14:30:00-03:00"
    assert result.assessment.relevance is Relevance.DISRUPTIVE
    assert result.assessment.rules_version == "REL-2026-09"
    assert result.next_step is NextStep.RECOMMENDATION
    assert "LA2410" in " ".join(result.explanation.details)


def test_body_holds_no_personal_data_or_rejected_evidence() -> None:
    body = _service().lookup("ABC123", "Silva", "req-test").model_dump_json()

    for value in [
        "maria.silva@example.com",
        "+56 9 8765 4321",
        "12.345.678-9",
        "GOLD",
        "LEGACY_MIRROR",
        "E-1012",
        "María Silva",
    ]:
        assert value not in body


def test_wrong_surname_is_not_found_and_events_are_not_called() -> None:
    tools = FakeToolsClient({"ABC123": trip_context_payload()}, events_payload())

    with pytest.raises(TripNotFound):
        _service(tools).lookup("ABC123", "Rojas", "req-test")

    assert tools.calls == ["context:ABC123"]


def test_unknown_booking_is_not_found() -> None:
    with pytest.raises(TripNotFound):
        _service().lookup("NOTF01", "Silva", "req-test")


def test_trip_context_unavailable() -> None:
    tools = FakeToolsClient({}, context_error=ToolUnavailable)

    with pytest.raises(TripContextUnavailable):
        _service(tools).lookup("CTXERR", "Silva", "req-test")


def test_events_unavailable_is_unverified() -> None:
    tools = FakeToolsClient({"ABC123": trip_context_payload()}, events_error=ToolUnavailable)

    result = _service(tools).lookup("ABC123", "Silva", "req-test")

    assert result.assessment.relevance is Relevance.UNVERIFIED
    assert [r.code for r in result.assessment.reasons] == ["EVENTS_UNAVAILABLE"]
    assert result.next_step is NextStep.HUMAN_ASSISTANCE
    assert all(s.delay_minutes is None for s in result.segments)


def test_rules_unavailable_is_unverified() -> None:
    result = _service(rules=FakeRuleSetRepository(None)).lookup("ABC123", "Silva", "req-test")

    assert [r.code for r in result.assessment.reasons] == ["RULES_UNAVAILABLE"]
    assert result.next_step is NextStep.HUMAN_ASSISTANCE


def test_airport_data_unavailable_is_unverified() -> None:
    airports = FakeAirportDirectory(AIRPORTS, fail=True)

    result = _service(airports=airports).lookup("ABC123", "Silva", "req-test")

    assert [r.code for r in result.assessment.reasons] == ["RULES_UNAVAILABLE"]


def test_on_schedule_next_step_is_none() -> None:
    events = events_payload()
    events["events"] = [e for e in events["events"] if e["event_id"] == "E-2003"]
    events["events"].append(
        {**events["events"][0], "event_id": "E-1", "segment_id": "S1", "status": "ON_TIME"}
    )
    tools = FakeToolsClient({"ABC123": trip_context_payload()}, events)

    result = _service(tools).lookup("ABC123", "Silva", "req-test")

    assert result.assessment.relevance is Relevance.NONE
    assert result.next_step is NextStep.NONE


def test_logs_hold_decision_but_no_personal_data(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        _service().lookup("ABC123", "Silva", "req-test")
        with pytest.raises(TripNotFound):
            _service().lookup("ABC123", "Rojas", "req-test")

    text = caplog.text
    for expected in ["ABC123", "DISRUPTIVE", "E-1012", "SOURCE_DEGRADED", "REL-2026-09"]:
        assert expected in text
    for forbidden in ["Silva", "María", "Rojas", "maria.silva@example.com"]:
        assert forbidden not in text


def test_assessment_is_recorded_with_the_request_id() -> None:
    log = FakeAssessmentLog()

    _service(log=log).lookup("ABC123", "Silva", "req-1")

    [(booking, assessment, request_id, _)] = log.records
    assert (booking, request_id) == ("ABC123", "req-1")
    assert assessment.relevance is Relevance.DISRUPTIVE


@pytest.mark.parametrize(("booking", "surname"), [("NOTF01", "Silva"), ("ABC123", "Rojas")])
def test_not_found_is_not_recorded(booking: str, surname: str) -> None:
    log = FakeAssessmentLog()

    with pytest.raises(TripNotFound):
        _service(log=log).lookup(booking, surname, "req-1")

    assert log.records == []


def test_failed_record_does_not_block_the_lookup(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        result = _service(log=FakeAssessmentLog(fail=True)).lookup("ABC123", "Silva", "req-1")

    assert result.assessment.relevance is Relevance.DISRUPTIVE
    assert "assessment not recorded" in caplog.text
