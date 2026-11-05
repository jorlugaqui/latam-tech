"""Relevance rules and airport reference data from SQL (design D3, D12).

Every failure (database error, no version in effect, malformed row) becomes
``RulesUnavailable`` so the assessment fails closed. Bound parameters only.
"""

import datetime as dt
import logging

from pydantic import ValidationError
from sqlalchemy import Engine, or_, select
from sqlalchemy.exc import SQLAlchemyError

from companion.ports.rules import RulesUnavailable
from companion.repositories.sql.tables import airports, relevance_criteria, relevance_rule_sets
from companion.schemas.assessment import AirportInfo, CriterionConfig, RelevanceRuleSet

logger = logging.getLogger(__name__)


def _utc(value: dt.datetime | None) -> dt.datetime | None:
    """SQLite returns naive datetimes (stored as UTC); PostgreSQL returns aware ones."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.UTC)
    return value.astimezone(dt.UTC)


class SqlRuleSetRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_effective(self, now: dt.datetime) -> RelevanceRuleSet:
        moment = now.astimezone(dt.UTC)
        header_query = (
            select(relevance_rule_sets)
            .where(relevance_rule_sets.c.effective_from <= moment)
            .where(
                or_(
                    relevance_rule_sets.c.effective_to.is_(None),
                    relevance_rule_sets.c.effective_to > moment,
                )
            )
            .order_by(relevance_rule_sets.c.effective_from.desc())
            .limit(1)
        )
        try:
            with self._engine.connect() as connection:
                header = connection.execute(header_query).mappings().first()
                if header is None:
                    raise RulesUnavailable("no rule set in effect")
                rows = connection.execute(
                    select(relevance_criteria)
                    .where(relevance_criteria.c.rule_set_version == header["version"])
                    .order_by(relevance_criteria.c.criterion_key)
                ).mappings()
                criteria = [
                    CriterionConfig(
                        key=row["criterion_key"],
                        enabled=row["enabled"],
                        tier=row["tier"],
                        params=row["params"],
                    )
                    for row in rows
                ]
            return RelevanceRuleSet(
                version=header["version"],
                effective_from=_utc(header["effective_from"]),
                effective_to=_utc(header["effective_to"]),
                freshness_max_age_minutes=header["freshness_max_age_minutes"],
                criteria=criteria,
            )
        except (SQLAlchemyError, ValidationError) as exc:
            logger.error("cannot read relevance rules: %s", type(exc).__name__)
            raise RulesUnavailable from exc


class SqlAirportDirectory:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find(self, codes: set[str]) -> dict[str, AirportInfo]:
        if not codes:
            return {}
        try:
            with self._engine.connect() as connection:
                rows = connection.execute(
                    select(airports).where(airports.c.iata.in_(sorted(codes)))
                ).mappings()
                return {
                    row["iata"]: AirportInfo(iata=row["iata"], iana_tz=row["iana_tz"])
                    for row in rows
                }
        except SQLAlchemyError as exc:
            logger.error("cannot read airports: %s", type(exc).__name__)
            raise RulesUnavailable from exc
