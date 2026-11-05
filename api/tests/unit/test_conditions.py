"""Spec recommendation: rule conditions are parsed and evaluated safely (Kleene logic)."""

import pytest

from companion.services.policy.conditions import Tri, evaluate, parse

FACTS = {
    "delay_minutes": 160,
    "missed_connection": True,
    "international": None,
    "compensation_requested": False,
    "group_includes_minor": True,
}


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ("delay_minutes >= 180", Tri.FALSE),
        ("delay_minutes >= 240 AND international", Tri.FALSE),
        ("missed_connection == true", Tri.TRUE),
        ("compensation_requested == true", Tri.FALSE),
        ("group_includes_minor == true", Tri.TRUE),
    ],
    ids=["R1", "R2", "R3", "R4", "R5"],
)
def test_brief_rules(condition: str, expected: Tri) -> None:
    assert evaluate(condition, FACTS) is expected


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ("delay_minutes > 159", Tri.TRUE),
        ("delay_minutes < 160", Tri.FALSE),
        ("delay_minutes <= 160", Tri.TRUE),
        ("delay_minutes == 160", Tri.TRUE),
        ("missed_connection", Tri.TRUE),
        ("compensation_requested == false", Tri.TRUE),
    ],
)
def test_operators(condition: str, expected: Tri) -> None:
    assert evaluate(condition, FACTS) is expected


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ("missed_connection AND international", Tri.UNKNOWN),  # TRUE AND UNKNOWN
        ("compensation_requested AND international", Tri.FALSE),  # FALSE AND UNKNOWN
        ("international AND delay_minutes >= 240", Tri.FALSE),  # UNKNOWN AND FALSE
        ("missed_connection AND group_includes_minor", Tri.TRUE),
    ],
)
def test_kleene_and(condition: str, expected: Tri) -> None:
    assert evaluate(condition, FACTS) is expected


def test_unknown_fact_is_unknown() -> None:
    assert evaluate("is_vip == true", FACTS) is Tri.UNKNOWN


def test_type_mismatch_is_unknown() -> None:
    assert evaluate("missed_connection >= 3", FACTS) is Tri.UNKNOWN
    assert evaluate("delay_minutes == true", FACTS) is Tri.UNKNOWN


@pytest.mark.parametrize(
    "condition",
    [
        "__import__('os').system('x')",
        "delay_minutes >= 180 OR true",
        "delay_minutes >= 1e3",
        "delay_minutes >= 180 and missed_connection",
        "delay_minutes.__class__ == true",
        "",
        "AND",
        "delay_minutes >=",
    ],
)
def test_unparsable_conditions_are_unknown_and_never_executed(condition: str) -> None:
    assert parse(condition) is None
    assert evaluate(condition, FACTS) is Tri.UNKNOWN
