"""Upstream DTOs for get_policy_rules and get_eligible_options (brief section 2)."""

from datetime import UTC, date, datetime, time

import pytest
from pydantic import ValidationError

from companion.schemas.tools import EligibleOptions, PolicyRules
from tests.unit.data.brief import options_payload, policy_payload


def test_brief_policy_parses() -> None:
    policy = PolicyRules.model_validate(policy_payload())

    assert policy.version == "POL-DELAY-2026-03"
    assert policy.effective_from == date(2026, 3, 1)
    assert [r.rule_id for r in policy.rules] == ["R1", "R2", "R3", "R4", "R5"]
    assert policy.rules[4].requires_human_approval is True
    assert policy.meta.superseded_versions == ["POL-DELAY-2025-11"]


def test_brief_options_parse_both_shapes() -> None:
    options = EligibleOptions.model_validate(options_payload())

    o1, o2, o3 = options.options
    assert (o1.type, o1.departure, o1.date, o1.seats_available) == (
        "REBOOK",
        time(8, 15),
        date(2026, 9, 16),
        4,
    )
    assert (o2.fare_difference, o2.currency) == (180000, "CLP")
    assert o3.type == "REFUND"
    assert o3.flight_number is None
    assert o3.seats_available is None
    assert options.meta.ttl_seconds == 120
    assert options.meta.retrieved_at == datetime(2026, 9, 15, 11, 2, 35, tzinfo=UTC)


def test_negative_ttl_is_rejected() -> None:
    payload = options_payload()
    payload["_meta"]["ttl_seconds"] = -1

    with pytest.raises(ValidationError):
        EligibleOptions.model_validate(payload)
