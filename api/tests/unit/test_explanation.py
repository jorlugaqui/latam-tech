"""Spec disruption-assessment: explanations are templated from verified facts only."""

from typing import Any

import pytest

from companion.schemas.assessment import Explanation, Relevance
from companion.schemas.tools import OperationalEvents
from companion.services.assessment.explanation import TemplateComposer
from companion.services.assessment.solver import DeterministicSolver
from tests.unit.data.brief import NOW, events_payload, facts_from, trip_context_payload
from tests.unit.data.reference import AIRPORTS, rel_2026_09

FORBIDDEN = [
    "LEGACY_MIRROR",
    "OPS_CORE",
    "AIRPORT_FEED",
    "ON_TIME",
    "fee",
    "refund",
    "compensation",
    "María",
    "Silva",
    "@",
]


def _explain(events: dict[str, Any] | None) -> tuple[Relevance, Explanation]:
    facts = facts_from(trip_context_payload())
    parsed = OperationalEvents.model_validate(events) if events is not None else None
    assessment = DeterministicSolver().assess(facts, parsed, rel_2026_09(), AIRPORTS, NOW)
    return assessment.relevance, TemplateComposer().compose(assessment, facts)


def _text(explanation: Explanation) -> str:
    return " ".join([explanation.headline, *explanation.details])


def test_brief_case_explanation() -> None:
    relevance, explanation = _explain(events_payload())
    text = _text(explanation)

    assert relevance is Relevance.DISRUPTIVE
    for expected in ["LA500", "delayed", "20:35", "LA2410", "19:05", "gate 24"]:
        assert expected in text
    for forbidden in FORBIDDEN:
        assert forbidden.lower() not in text.lower()


def test_unverified_explanation_states_no_time_or_delay() -> None:
    relevance, explanation = _explain(None)
    text = _text(explanation)

    assert relevance is Relevance.UNVERIFIED
    assert "confirming" in text.lower()
    assert "agent" in text.lower()
    assert not any(char.isdigit() for char in text)
    assert "delay" not in text.lower()
    assert "cancel" not in text.lower()


def _status_events(s1: str = "ON_TIME") -> dict[str, Any]:
    payload = events_payload()
    payload["events"] = [
        {
            "event_id": "E-1",
            "segment_id": "S1",
            "type": "STATUS",
            "status": s1,
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


def test_cancellation_explanation() -> None:
    _, explanation = _explain(_status_events("CANCELLED"))
    text = _text(explanation)

    assert "LA500" in text
    assert "cancelled" in text.lower()
    assert "LA2410" in text


def test_informational_gate_change() -> None:
    events = _status_events()
    events["events"].append(
        {
            "event_id": "E-3",
            "segment_id": "S1",
            "type": "GATE_CHANGE",
            "gate": "31",
            "source": "AIRPORT_FEED",
            "recorded_at": "2026-09-15T10:55:00Z",
        }
    )

    relevance, explanation = _explain(events)

    assert relevance is Relevance.INFORMATIONAL
    assert "gate 31" in _text(explanation)


def test_on_schedule() -> None:
    relevance, explanation = _explain(_status_events())

    assert relevance is Relevance.NONE
    assert "on schedule" in explanation.headline.lower()


@pytest.mark.parametrize("relevance", list(Relevance))
def test_every_tier_has_a_headline(relevance: Relevance) -> None:
    assert TemplateComposer.HEADLINES[relevance]
