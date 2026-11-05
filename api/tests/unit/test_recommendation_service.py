"""Spec recommendation: orchestration with fakes (policy, options, TTL, fail closed)."""

import logging
from typing import Any

import pytest

from companion.ports.tools import ToolUnavailable
from companion.schemas.assessment import NextStep
from companion.schemas.recommendation import (
    Approval,
    Recommendation,
    RecommendationReason,
    RecommendationStatus,
)
from companion.services.assessment.solver import DeterministicSolver
from companion.services.recommendation import RecommendationService
from companion.services.trip_access import TripAccess
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
    FakeRuleSetRepository,
    FakeToolsClient,
    FixedClock,
)


def _tools(**overrides: Any) -> FakeToolsClient:
    values: dict[str, Any] = {
        "contexts": {"ABC123": trip_context_payload()},
        "events": events_payload(),
        "policies": {"DELAY": policy_payload()},
        "options": [options_payload()],
    }
    values.update(overrides)
    return FakeToolsClient(**values)


def _service(tools: FakeToolsClient) -> RecommendationService:
    access = TripAccess(
        trips=tools,
        events=tools,
        rules=FakeRuleSetRepository(rel_2026_09()),
        airports=FakeAirportDirectory(AIRPORTS),
        clock=FixedClock(NOW),
        solver=DeterministicSolver(),
        assessment_log=FakeAssessmentLog(),
    )
    return RecommendationService(access, tools, tools, FixedClock(NOW))


def _recommend(tools: FakeToolsClient) -> Recommendation:
    return _service(tools).recommend("ABC123", "Silva", "req-1")


def _status_events(s1_status: str) -> dict[str, Any]:
    payload = events_payload()
    payload["events"] = [
        {
            "event_id": "E-1",
            "segment_id": "S1",
            "type": "STATUS",
            "status": s1_status,
            "source": "OPS_CORE",
            "recorded_at": "2026-09-15T10:50:00Z",
        },
        {
            "event_id": "E-2",
            "segment_id": "S2",
            "type": "STATUS",
            "status": "SCHEDULED",
            "source": "OPS_CORE",
            "recorded_at": "2026-09-15T10:50:00Z",
        },
    ]
    return payload


def test_brief_recommendation() -> None:
    result = _recommend(_tools())

    assert result.status is RecommendationStatus.PROPOSED
    assert result.policy_version == "POL-DELAY-2026-03"
    assert [(e.code, e.rule_id) for e in result.entitlements] == [
        ("REBOOK_NO_FEE", "R3"),
        ("PRIORITY_HANDLING", "R5"),
    ]
    assert [o.option_id for o in result.options] == ["O1"]
    assert {e.option_id for e in result.excluded} == {"O2", "O3"}
    assert result.approval is Approval.HUMAN_REQUIRED
    assert result.options_expire_at.isoformat() == "2026-09-15T11:04:35+00:00"
    assert result.next_step is NextStep.RECOMMENDATION
    text = " ".join([result.explanation.headline, *result.explanation.details])
    for expected in ["POL-DELAY-2026-03", "R3", "LA2412", "08:15", "agent"]:
        assert expected in text
    assert "Silva" not in text


@pytest.mark.parametrize(
    ("s1_status", "next_step"),
    [("ON_TIME", NextStep.NONE)],
)
def test_not_disruptive_is_not_applicable_without_policy_calls(
    s1_status: str, next_step: NextStep
) -> None:
    tools = _tools(events=_status_events(s1_status))

    result = _recommend(tools)

    assert result.status is RecommendationStatus.NOT_APPLICABLE
    assert result.next_step is next_step
    assert result.options == []
    assert not any(c.startswith(("policy:", "options:")) for c in tools.calls)


def test_unverified_is_not_applicable_with_agent_next_step() -> None:
    tools = _tools(events_error=ToolUnavailable)

    result = _recommend(tools)

    assert result.status is RecommendationStatus.NOT_APPLICABLE
    assert result.next_step is NextStep.HUMAN_ASSISTANCE


def test_cancellation_without_policy_needs_an_agent() -> None:
    tools = _tools(events=_status_events("CANCELLED"))

    result = _recommend(tools)

    assert "policy:CANCELLATION" in tools.calls
    assert result.status is RecommendationStatus.NEEDS_AGENT
    assert result.reason is RecommendationReason.POLICY_UNAVAILABLE
    assert result.next_step is NextStep.HUMAN_ASSISTANCE


def test_policy_tool_down_needs_an_agent() -> None:
    result = _recommend(_tools(policy_error=ToolUnavailable))

    assert result.reason is RecommendationReason.POLICY_UNAVAILABLE


def test_policy_not_yet_in_effect_needs_an_agent() -> None:
    future = policy_payload()
    future["effective_from"] = "2026-10-01"

    assert _recommend(_tools(policies={"DELAY": future})).reason is (
        RecommendationReason.POLICY_UNAVAILABLE
    )


def test_options_down_needs_an_agent() -> None:
    result = _recommend(_tools(options_error=ToolUnavailable))

    assert result.status is RecommendationStatus.NEEDS_AGENT
    assert result.reason is RecommendationReason.OPTIONS_UNAVAILABLE


def _expired() -> dict[str, Any]:
    payload = options_payload()
    payload["_meta"]["retrieved_at"] = "2026-09-15T10:00:00Z"
    return payload


def test_expired_options_are_fetched_once_more() -> None:
    tools = _tools(options=[_expired(), options_payload()])

    result = _recommend(tools)

    assert sum(c.startswith("options:") for c in tools.calls) == 2
    assert result.status is RecommendationStatus.PROPOSED


def test_still_expired_options_need_an_agent() -> None:
    tools = _tools(options=[_expired()])

    result = _recommend(tools)

    assert sum(c.startswith("options:") for c in tools.calls) == 2
    assert result.reason is RecommendationReason.OPTIONS_EXPIRED


def test_no_eligible_option_needs_an_agent() -> None:
    payload = options_payload()
    payload["options"] = payload["options"][1:]

    result = _recommend(_tools(options=[payload]))

    assert result.status is RecommendationStatus.NEEDS_AGENT
    assert result.reason is RecommendationReason.NO_ELIGIBLE_OPTION
    assert result.next_step is NextStep.HUMAN_ASSISTANCE


def test_excluded_options_are_logged_with_codes(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        _recommend(_tools())

    assert "O2:INSUFFICIENT_SEATS+FEE_CONFLICTS_ENTITLEMENT" in caplog.text
    assert "Silva" not in caplog.text
