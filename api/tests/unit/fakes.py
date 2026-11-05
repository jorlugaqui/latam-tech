"""Test doubles for ports. Each must be substitutable for the real adapter (LSP)."""

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from companion.ports.rules import RulesUnavailable
from companion.ports.tools import BookingNotFound, ToolUnavailable
from companion.schemas.assessment import AirportInfo, RelevanceRuleSet
from companion.schemas.tools import OperationalEvents, TripContext


@dataclass
class FakeDatabaseProbe:
    reachable: bool = True

    def is_reachable(self) -> bool:
        return self.reachable


# ---- trip status ports ------------------------------------------------------------


@dataclass
class FakeToolsClient:
    """Implements TripContextReader and OperationalEventsReader."""

    contexts: dict[str, dict[str, Any]]
    events: dict[str, Any] | None = None
    context_error: type[Exception] | None = None
    events_error: type[Exception] | None = None
    calls: list[str] = field(default_factory=list)

    def get_trip_context(self, booking_id: str) -> TripContext:
        self.calls.append(f"context:{booking_id}")
        if self.context_error is not None:
            raise self.context_error
        if booking_id not in self.contexts:
            raise BookingNotFound
        return TripContext.model_validate(self.contexts[booking_id])

    def get_operational_events(self, segment_ids: list[str]) -> OperationalEvents:
        self.calls.append("events:" + ",".join(segment_ids))
        if self.events_error is not None:
            raise self.events_error
        if self.events is None:
            raise ToolUnavailable
        return OperationalEvents.model_validate(self.events)


@dataclass
class FakeRuleSetRepository:
    rule_set: RelevanceRuleSet | None

    def get_effective(self, now: dt.datetime) -> RelevanceRuleSet:
        if self.rule_set is None:
            raise RulesUnavailable
        return self.rule_set


@dataclass
class FakeAirportDirectory:
    airports: dict[str, AirportInfo]
    fail: bool = False

    def find(self, codes: set[str]) -> dict[str, AirportInfo]:
        if self.fail:
            raise RulesUnavailable
        return {code: info for code, info in self.airports.items() if code in codes}


@dataclass
class FixedClock:
    moment: dt.datetime

    def now(self) -> dt.datetime:
        return self.moment


@dataclass
class FakeAssessmentLog:
    fail: bool = False
    records: list[tuple[str, Any, str]] = field(default_factory=list)

    def record(self, booking_id: str, assessment: Any, request_id: str) -> None:
        from companion.ports.audit import AssessmentNotRecorded

        if self.fail:
            raise AssessmentNotRecorded
        self.records.append((booking_id, assessment, request_id))
