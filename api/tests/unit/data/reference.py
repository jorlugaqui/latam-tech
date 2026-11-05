"""Reference data and rule sets used across tests (mirrors the 0003 seed)."""

from datetime import UTC, datetime

from companion.schemas.assessment import AirportInfo, CriterionConfig, RelevanceRuleSet, Tier

AIRPORTS = {
    "SCL": AirportInfo(iata="SCL", iana_tz="America/Santiago"),
    "LIM": AirportInfo(iata="LIM", iana_tz="America/Lima"),
    "MEX": AirportInfo(iata="MEX", iana_tz="America/Mexico_City"),
}


def rel_2026_09() -> RelevanceRuleSet:
    return RelevanceRuleSet(
        version="REL-2026-09",
        effective_from=datetime(2026, 9, 1, tzinfo=UTC),
        freshness_max_age_minutes=30,
        criteria=[
            CriterionConfig(key="CANCELLATION", enabled=True, tier=Tier.DISRUPTIVE),
            CriterionConfig(
                key="MISSED_CONNECTION",
                enabled=True,
                tier=Tier.DISRUPTIVE,
                params={"default_mct_minutes": 60, "mct_by_airport": {"MEX": 90}},
            ),
            CriterionConfig(
                key="LONG_DELAY",
                enabled=True,
                tier=Tier.DISRUPTIVE,
                params={"min_delay_minutes": 120},
            ),
            CriterionConfig(
                key="MINOR_DELAY",
                enabled=True,
                tier=Tier.INFORMATIONAL,
                params={"min_delay_minutes": 15},
            ),
            CriterionConfig(key="GATE_CHANGE", enabled=True, tier=Tier.INFORMATIONAL),
        ],
    )
