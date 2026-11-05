"""Spec human-handoff: reasons, evidence, intent first, outcomes, duplicates, logging."""

import json
import logging
from typing import Any

import pytest

from companion.ports.tools import ToolUnavailable
from companion.schemas.handoff import CaseReason, CaseStatus
from companion.services.assessment.solver import DeterministicSolver
from companion.services.handoff import (
    HandoffUnavailable,
    HumanCaseService,
    NothingToEscalate,
    OptionNotEligible,
)
from companion.services.recommendation import RecommendationService
from companion.services.trip_access import TripAccess, TripNotFound
from tests.unit.data.brief import (
    NOW,
    events_payload,
    options_payload,
    policy_payload,
    trip_context_payload,
)
from tests.unit.data.reference import AIRPORTS, rel_2026_09
from tests.unit.fakes import (
    FakeAirportDirectory,
    FakeAssessmentLog,
    FakeCaseRepository,
    FakeCaseWriter,
    FakeRuleSetRepository,
    FakeToolsClient,
    FixedClock,
)

PII = ["Silva", "María", "Tomás", "maria.silva@example.com", "12.345.678-9", "+56 9 8765 4321"]


class World:
    def __init__(self, **tool_overrides: Any) -> None:
        values: dict[str, Any] = {
            "contexts": {"ABC123": trip_context_payload()},
            "events": events_payload(),
            "policies": {"DELAY": policy_payload()},
            "options": [options_payload()],
        }
        values.update(tool_overrides)
        self.tools = FakeToolsClient(**values)
        self.journal: list[str] = []
        self.cases = FakeCaseRepository(journal=self.journal)
        self.writer = FakeCaseWriter(journal=self.journal)
        self.log = FakeAssessmentLog()

    def service(self) -> HumanCaseService:
        access = TripAccess(
            trips=self.tools,
            events=self.tools,
            rules=FakeRuleSetRepository(rel_2026_09()),
            airports=FakeAirportDirectory(AIRPORTS),
            clock=FixedClock(NOW),
            solver=DeterministicSolver(),
            assessment_log=self.log,
        )
        recommendations = RecommendationService(access, self.tools, self.tools, FixedClock(NOW))
        return HumanCaseService(access, recommendations, self.cases, self.writer)

    def request(self, option_id: str | None = "O1", surname: str = "Silva") -> Any:
        return self.service().request("ABC123", surname, option_id, "req-1")


def _unverified_events() -> dict[str, Any]:
    payload = events_payload()
    payload["events"] = [
        {
            "event_id": "E-3001",
            "segment_id": "S1",
            "type": "DELAY",
            "delay_minutes": 90,
            "new_departure": "16:00",
            "source": "OPS_CORE",
            "recorded_at": "2026-09-15T10:50:00Z",
        },
        {
            "event_id": "E-3002",
            "segment_id": "S1",
            "type": "STATUS",
            "status": "ON_TIME",
            "source": "AIRPORT_FEED",
            "recorded_at": "2026-09-15T10:52:00Z",
        },
    ]
    return payload


def _on_time_events() -> dict[str, Any]:
    payload = events_payload()
    payload["events"] = [
        {
            "event_id": "E-1",
            "segment_id": s,
            "type": "STATUS",
            "status": "ON_TIME",
            "source": "OPS_CORE",
            "recorded_at": "2026-09-15T10:50:00Z",
        }
        for s in ("S1", "S2")
    ]
    return payload


def test_option_approval_opens_a_case() -> None:
    world = World()

    result = world.request("O1")

    assert result.created is True
    assert result.case.status is CaseStatus.OPEN
    assert result.case.reason is CaseReason.OPTION_APPROVAL
    assert result.case.case_id == "HC-1"
    assert result.case.sla_minutes == 45
    assert world.writer.calls[0][0] == "OPTION_APPROVAL"


def test_intent_is_recorded_before_the_tool_is_called() -> None:
    world = World()

    world.request("O1")

    assert world.journal == ["insert", "create"]


def test_evidence_references_verified_data_without_personal_data() -> None:
    world = World()

    world.request("O1")

    evidence = world.writer.calls[0][1]
    text = json.dumps(evidence, ensure_ascii=False)
    for expected in ["ABC123", "R3", "R5", "POL-DELAY-2026-03", "O1", "E-1001"]:
        assert expected in text
    assert evidence["party"] == {"adults": 1, "children": 1, "infants": 0, "includes_minor": True}
    assert evidence["assessment_id"] == "A-1"
    assert evidence["option"]["option_id"] == "O1"
    assert evidence["option"]["expires_at"] == "2026-09-15T11:04:35Z"
    assert {e["option_id"] for e in evidence["excluded_options"]} == {"O2", "O3"}
    for value in PII:
        assert value not in text
    assert world.cases.new_cases[0].evidence == evidence


def test_ineligible_option_is_a_conflict() -> None:
    world = World()

    with pytest.raises(OptionNotEligible):
        world.request("O2")

    assert world.journal == []


def test_disruptive_without_option_asks_for_assistance() -> None:
    assert World().request(None).case.reason is CaseReason.ASSISTANCE_REQUIRED


def test_unverified_asks_for_status_verification() -> None:
    world = World(events=_unverified_events())

    assert world.request(None).case.reason is CaseReason.STATUS_VERIFICATION
    assert not any(c.startswith(("policy:", "options:")) for c in world.tools.calls)


def test_unverified_with_option_is_a_conflict() -> None:
    with pytest.raises(OptionNotEligible):
        World(events=_unverified_events()).request("O1")


def test_nothing_to_escalate() -> None:
    world = World(events=_on_time_events())

    with pytest.raises(NothingToEscalate):
        world.request(None)

    assert world.journal == []


def test_wrong_surname_creates_nothing() -> None:
    world = World()

    with pytest.raises(TripNotFound):
        world.request("O1", surname="Rojas")

    assert world.journal == []


def test_assessment_record_failure_blocks_the_case() -> None:
    world = World()
    world.log.fail = True

    with pytest.raises(HandoffUnavailable):
        world.request("O1")

    assert world.journal == []


def test_local_record_failure_blocks_the_tool() -> None:
    world = World()
    world.cases.fail = True

    with pytest.raises(HandoffUnavailable):
        world.request("O1")

    assert world.writer.calls == []


def test_indeterminate_is_not_retried_and_keeps_the_case() -> None:
    world = World()
    world.writer.outcome = "indeterminate"

    first = world.request("O1")
    second = world.request("O1")

    assert first.case.status is CaseStatus.INDETERMINATE
    assert first.case.case_id is None
    assert (second.created, second.case.status) == (False, CaseStatus.INDETERMINATE)
    assert len(world.writer.calls) == 1


def test_rejected_fails_and_a_retry_creates_a_new_case() -> None:
    world = World()
    world.writer.outcome = "rejected"

    with pytest.raises(HandoffUnavailable):
        world.request("O1")
    world.writer.outcome = "created"
    retry = world.request("O1")

    assert retry.created is True
    assert retry.case.status is CaseStatus.OPEN
    assert len(world.writer.calls) == 2


def test_double_click_reuses_the_case() -> None:
    world = World()

    first = world.request("O1")
    second = world.request("O1")

    assert (first.created, second.created) == (True, False)
    assert second.case.case_id == first.case.case_id
    assert len(world.writer.calls) == 1


def test_options_outage_still_allows_assistance() -> None:
    world = World(options_error=ToolUnavailable)

    assert world.request(None).case.reason is CaseReason.ASSISTANCE_REQUIRED


def test_logs_hold_ids_but_no_personal_data(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        World().request("O1")

    for expected in ["ABC123", "OPTION_APPROVAL", "OPEN", "HC-1"]:
        assert expected in caplog.text
    for value in PII:
        assert value not in caplog.text
