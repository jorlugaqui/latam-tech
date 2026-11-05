"""Spec recommendation: option filters (Specification) with every reason, and ranking."""

from typing import Any

from companion.schemas.recommendation import Entitlement, ExclusionCode
from companion.schemas.tools import EligibleOptions, OperationalEvents, PolicyRules
from companion.services.assessment.criteria import missed_connection_params
from companion.services.assessment.solver import DeterministicSolver
from companion.services.options.selection import SelectionContext, build_context, select
from tests.unit.data.brief import (
    NOW,
    events_payload,
    facts_from,
    options_payload,
    policy_payload,
    trip_context_payload,
)
from tests.unit.data.reference import AIRPORTS, rel_2026_09

REBOOK_NO_FEE = Entitlement(code="REBOOK_NO_FEE", rule_id="R3", requires_human_approval=False)
PRIORITY = Entitlement(code="PRIORITY_HANDLING", rule_id="R5", requires_human_approval=True)


def _context(entitlements: list[Entitlement] | None = None) -> SelectionContext:
    facts = facts_from(trip_context_payload())
    assessment = DeterministicSolver().assess(
        facts, OperationalEvents.model_validate(events_payload()), rel_2026_09(), AIRPORTS, NOW
    )
    return build_context(
        facts,
        assessment,
        entitlements if entitlements is not None else [REBOOK_NO_FEE, PRIORITY],
        PolicyRules.model_validate(policy_payload()),
        AIRPORTS,
        missed_connection_params(rel_2026_09().criteria),
    )


def _options(*extra: dict[str, Any]) -> EligibleOptions:
    payload = options_payload()
    payload["options"].extend(extra)
    return EligibleOptions.model_validate(payload)


def _codes(selection: Any) -> dict[str, list[ExclusionCode]]:
    return {e.option_id: e.codes for e in selection.excluded}


def test_context_anchors_on_the_missed_connection() -> None:
    ctx = _context()

    assert ctx.anchor_airport == "LIM"
    assert ctx.final_destination == "MEX"
    assert ctx.party_size == 2
    assert ctx.earliest_departure.isoformat() == "2026-09-15T21:35:00-05:00"


def test_brief_matrix() -> None:
    selection = select(_options().options, _context())

    assert [o.option_id for o in selection.eligible] == ["O1"]
    assert selection.eligible[0].departure.isoformat() == "2026-09-16T08:15:00-05:00"
    assert _codes(selection) == {
        "O2": [ExclusionCode.INSUFFICIENT_SEATS, ExclusionCode.FEE_CONFLICTS_ENTITLEMENT],
        "O3": [ExclusionCode.NOT_ENTITLED, ExclusionCode.LOW_CONFIDENCE],
    }


def _rebook(option_id: str, **fields: Any) -> dict[str, Any]:
    option = {
        "option_id": option_id,
        "type": "REBOOK",
        "flight_number": "LA9",
        "origin": "LIM",
        "destination": "MEX",
        "date": "2026-09-16",
        "departure": "10:00",
        "fare_difference": 0,
        "seats_available": 9,
        "policy_ref": "POL-DELAY-2026-03",
        "confidence": "HIGH",
    }
    option.update(fields)
    return option


def test_departs_before_the_passenger_can_connect() -> None:
    early = _rebook("O4", date="2026-09-15", departure="20:50")

    assert _codes(select(_options(early).options, _context()))["O4"] == [
        ExclusionCode.DEPARTS_TOO_EARLY
    ]


def test_wrong_route() -> None:
    wrong = _rebook("O5", origin="SCL")

    assert ExclusionCode.WRONG_ROUTE in _codes(select(_options(wrong).options, _context()))["O5"]


def test_superseded_policy() -> None:
    old = _rebook("O6", policy_ref="POL-DELAY-2025-11")

    assert _codes(select(_options(old).options, _context()))["O6"] == [
        ExclusionCode.POLICY_SUPERSEDED
    ]


def test_rebook_without_entitlement() -> None:
    selection = select(_options().options, _context(entitlements=[PRIORITY]))

    assert selection.eligible == []
    assert ExclusionCode.NOT_ENTITLED in _codes(selection)["O1"]


def test_ranking_by_confidence_then_departure() -> None:
    medium_early = _rebook("O7", confidence="MEDIUM", departure="06:00")
    high_late = _rebook("O8", departure="12:00")

    selection = select(_options(medium_early, high_late).options, _context())

    assert [o.option_id for o in selection.eligible] == ["O1", "O8", "O7"]
