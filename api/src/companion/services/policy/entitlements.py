"""Entitlements come only from rules whose condition is TRUE (spec recommendation)."""

from collections.abc import Mapping
from dataclasses import dataclass

from companion.schemas.recommendation import Entitlement
from companion.schemas.tools import PolicyRules
from companion.services.policy.conditions import FactValue, Tri, evaluate


@dataclass(frozen=True)
class RuleOutcome:
    entitlements: list[Entitlement]
    unevaluated_rules: list[str]


def evaluate_rules(policy: PolicyRules, facts: Mapping[str, FactValue]) -> RuleOutcome:
    entitlements: list[Entitlement] = []
    unevaluated: list[str] = []
    for rule in policy.rules:
        result = evaluate(rule.condition, facts)
        if result is Tri.TRUE:
            entitlements.append(
                Entitlement(
                    code=rule.entitlement,
                    rule_id=rule.rule_id,
                    requires_human_approval=rule.requires_human_approval,
                )
            )
        elif result is Tri.UNKNOWN:
            unevaluated.append(rule.rule_id)
    return RuleOutcome(entitlements, unevaluated)
