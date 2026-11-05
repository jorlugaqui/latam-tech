"""Relevance rules and airport reference data (design D3, D12)."""

import datetime as dt
from typing import Protocol

from companion.schemas.assessment import AirportInfo, RelevanceRuleSet


class RulesUnavailable(Exception):
    """No rule set is in effect, or it cannot be read."""


class RuleSetRepository(Protocol):
    def get_effective(self, now: dt.datetime) -> RelevanceRuleSet:
        """The rule set in effect at ``now``; raises ``RulesUnavailable``."""
        ...


class AirportDirectory(Protocol):
    def find(self, codes: set[str]) -> dict[str, AirportInfo]:
        """Known airports among ``codes``; unknown ones are omitted. Raises
        ``RulesUnavailable`` if the reference data cannot be read."""
        ...
