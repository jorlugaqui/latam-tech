"""Spec recommendation: facts come from the verified trip; entitlements only from rules."""

from companion.schemas.assessment import Assessment, TripFacts
from companion.schemas.recommendation import Entitlement
from companion.schemas.tools import OperationalEvents, PolicyRules
from companion.services.assessment.solver import DeterministicSolver
from companion.services.policy.entitlements import evaluate_rules
from companion.services.policy.facts import collect_facts
from tests.unit.data.brief import (
    NOW,
    events_payload,
    facts_from,
    policy_payload,
    trip_context_payload,
)
from tests.unit.data.reference import AIRPORTS, rel_2026_09


def _brief() -> tuple[TripFacts, Assessment]:
    facts = facts_from(trip_context_payload())
    assessment = DeterministicSolver().assess(
        facts, OperationalEvents.model_validate(events_payload()), rel_2026_09(), AIRPORTS, NOW
    )
    return facts, assessment


def test_brief_facts() -> None:
    assert collect_facts(*_brief()) == {
        "delay_minutes": 160,
        "missed_connection": True,
        "international": None,
        "compensation_requested": False,
        "group_includes_minor": True,
    }


def test_adults_only_has_no_minor() -> None:
    facts, assessment = _brief()
    adults = facts.model_copy(
        update={"passengers": [p.model_copy(update={"type": "ADULT"}) for p in facts.passengers]}
    )

    assert collect_facts(adults, assessment)["group_includes_minor"] is False


def test_brief_entitlements() -> None:
    outcome = evaluate_rules(PolicyRules.model_validate(policy_payload()), collect_facts(*_brief()))

    assert outcome.entitlements == [
        Entitlement(code="REBOOK_NO_FEE", rule_id="R3", requires_human_approval=False),
        Entitlement(code="PRIORITY_HANDLING", rule_id="R5", requires_human_approval=True),
    ]
    assert outcome.unevaluated_rules == []


def test_unknown_rule_is_listed_and_grants_nothing() -> None:
    payload = policy_payload()
    payload["rules"].append(
        {
            "rule_id": "R9",
            "condition": "is_vip == true",
            "entitlement": "LOUNGE",
            "requires_human_approval": False,
        }
    )

    outcome = evaluate_rules(PolicyRules.model_validate(payload), collect_facts(*_brief()))

    assert outcome.unevaluated_rules == ["R9"]
    assert "LOUNGE" not in {e.code for e in outcome.entitlements}
