"""Spec disruption-assessment: each relevance criterion and the criteria registry."""

import pytest

from companion.schemas.assessment import (
    ConnectionImpact,
    ConnectionStatus,
    CriterionConfig,
    Reason,
    SegmentImpact,
    SegmentStatus,
    Tier,
)
from companion.services.assessment.criteria import (
    InvalidRuleSet,
    MissedConnectionCriterion,
    build_criteria,
)
from tests.unit.data.reference import rel_2026_09


def _impact(segment_id: str = "S1", **fields: object) -> SegmentImpact:
    values: dict[str, object] = {
        "segment_id": segment_id,
        "flight_number": "LA500",
        "status": SegmentStatus.ON_SCHEDULE,
    }
    values.update(fields)
    return SegmentImpact(**values)


def _evaluate(key: str, impacts: list[SegmentImpact]) -> list[Reason]:
    criteria = {c.key: c for _, c in build_criteria(rel_2026_09().criteria)}
    return criteria[key].evaluate(impacts)


def test_cancellation() -> None:
    impacts = [_impact(status=SegmentStatus.CANCELLED, evidence=["E-5"]), _impact("S2")]

    assert _evaluate("CANCELLATION", impacts) == [
        Reason(code="CANCELLATION", segment_ids=["S1"], event_ids=["E-5"])
    ]


def test_missed_connection() -> None:
    impacts = [
        _impact(
            status=SegmentStatus.DELAYED,
            delay_minutes=160,
            evidence=["E-1001"],
            connection=ConnectionImpact(to_segment_id="S2", status=ConnectionStatus.MISSED),
        ),
        _impact("S2"),
    ]

    assert _evaluate("MISSED_CONNECTION", impacts) == [
        Reason(code="MISSED_CONNECTION", segment_ids=["S1", "S2"], event_ids=["E-1001"])
    ]


def test_connection_ok_is_not_a_reason() -> None:
    impacts = [
        _impact(connection=ConnectionImpact(to_segment_id="S2", status=ConnectionStatus.OK)),
        _impact("S2"),
    ]

    assert _evaluate("MISSED_CONNECTION", impacts) == []


def test_mct_comes_from_params() -> None:
    params = MissedConnectionCriterion.Params(default_mct_minutes=60, mct_by_airport={"MEX": 90})

    assert params.mct_for("LIM") == 60
    assert params.mct_for("MEX") == 90


@pytest.mark.parametrize(
    ("delay", "long", "minor"),
    [(160, True, True), (30, False, True), (10, False, False), (120, True, True)],
)
def test_delay_thresholds(delay: int, long: bool, minor: bool) -> None:
    impacts = [_impact(status=SegmentStatus.DELAYED, delay_minutes=delay, evidence=["E-1"])]

    assert bool(_evaluate("LONG_DELAY", impacts)) is long
    assert bool(_evaluate("MINOR_DELAY", impacts)) is minor


def test_gate_change() -> None:
    impacts = [_impact(gate="24", gate_event_id="E-1007")]

    assert _evaluate("GATE_CHANGE", impacts) == [
        Reason(code="GATE_CHANGE", segment_ids=["S1"], event_ids=["E-1007"])
    ]


def test_registry_returns_enabled_criteria_with_their_tier() -> None:
    configs = rel_2026_09().criteria
    configs[1] = configs[1].model_copy(update={"enabled": False})

    built = build_criteria(configs)

    assert ("MISSED_CONNECTION" in {c.key for _, c in built}) is False
    assert (Tier.INFORMATIONAL, "GATE_CHANGE") in {(t, c.key) for t, c in built}


def test_unknown_key_is_an_invalid_rule_set() -> None:
    with pytest.raises(InvalidRuleSet):
        build_criteria([CriterionConfig(key="MOON_PHASE", enabled=True, tier=Tier.DISRUPTIVE)])


def test_invalid_params_are_an_invalid_rule_set() -> None:
    bad = CriterionConfig(
        key="LONG_DELAY", enabled=True, tier=Tier.DISRUPTIVE, params={"min_delay_minutes": -5}
    )

    with pytest.raises(InvalidRuleSet):
        build_criteria([bad])


def test_disabled_criteria_are_still_validated() -> None:
    bad = CriterionConfig(key="LONG_DELAY", enabled=False, tier=Tier.DISRUPTIVE, params={})

    with pytest.raises(InvalidRuleSet):
        build_criteria([bad])
