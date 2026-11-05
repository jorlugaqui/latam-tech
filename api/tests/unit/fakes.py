"""Test doubles for ports. Each must be substitutable for the real adapter (LSP)."""

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from companion.ports.rules import RulesUnavailable
from companion.ports.tools import BookingNotFound, PolicyNotFound, ToolUnavailable
from companion.schemas.assessment import AirportInfo, RelevanceRuleSet
from companion.schemas.tools import (
    EligibleOptions,
    OperationalEvents,
    PolicyRules,
    TripContext,
)


@dataclass
class FakeDatabaseProbe:
    reachable: bool = True

    def is_reachable(self) -> bool:
        return self.reachable


# ---- trip status ports ------------------------------------------------------------


@dataclass
class FakeToolsClient:
    """Implements TripContextReader, OperationalEventsReader, PolicyReader, OptionsReader.

    ``options`` is a list of payloads returned in order (the last one repeats), so tests
    can model a TTL refetch.
    """

    contexts: dict[str, dict[str, Any]]
    events: dict[str, Any] | None = None
    context_error: type[Exception] | None = None
    events_error: type[Exception] | None = None
    policies: dict[str, dict[str, Any]] = field(default_factory=dict)
    policy_error: type[Exception] | None = None
    options: list[dict[str, Any]] = field(default_factory=list)
    options_error: type[Exception] | None = None
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

    def get_policy_rules(self, scenario: str) -> PolicyRules:
        self.calls.append(f"policy:{scenario}")
        if self.policy_error is not None:
            raise self.policy_error
        if scenario not in self.policies:
            raise PolicyNotFound
        return PolicyRules.model_validate(self.policies[scenario])

    def get_eligible_options(self, context: TripContext) -> EligibleOptions:
        served = sum(call.startswith("options:") for call in self.calls)
        self.calls.append(f"options:{context.booking_id}")
        if self.options_error is not None:
            raise self.options_error
        if not self.options:
            raise ToolUnavailable
        return EligibleOptions.model_validate(self.options[min(served, len(self.options) - 1)])


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
    records: list[tuple[str, Any, str, str]] = field(default_factory=list)

    def record(self, booking_id: str, assessment: Any, request_id: str) -> str:
        from companion.ports.audit import AssessmentNotRecorded

        if self.fail:
            raise AssessmentNotRecorded
        record_id = f"A-{len(self.records) + 1}"
        self.records.append((booking_id, assessment, request_id, record_id))
        return record_id


# ---- human hand-off ports ---------------------------------------------------------


@dataclass
class FakeCaseRepository:
    """In-memory CaseRepository with the same one-active-case semantics as SQL."""

    journal: list[str] = field(default_factory=list)
    fail: bool = False
    rows: dict[str, Any] = field(default_factory=dict)
    new_cases: list[Any] = field(default_factory=list)

    def open_or_get_active(self, case: Any) -> tuple[Any, bool]:
        from companion.ports.cases import CasesUnavailable
        from companion.schemas.case_states import ACTIVE
        from companion.schemas.handoff import CaseStatus, HumanCase

        if self.fail:
            raise CasesUnavailable
        for row in self.rows.values():
            if row.booking_id == case.booking_id and row.status in ACTIVE:
                return row, False
        self.journal.append("insert")
        self.new_cases.append(case)
        row = HumanCase(
            id=f"L-{len(self.rows) + 1}",
            booking_id=case.booking_id,
            reason=case.reason,
            status=CaseStatus.REQUESTED,
            option_id=case.option_id,
            created_at=dt.datetime(2026, 9, 15, 11, 3, tzinfo=dt.UTC),
        )
        self.rows[row.id] = row
        return row, True

    def transition(
        self,
        case_id: str,
        target: Any,
        external_case_id: str | None = None,
        queue: str | None = None,
        sla_minutes: int | None = None,
    ) -> Any:
        from companion.schemas.case_states import transition

        row = self.rows[case_id]
        transition(row.status, target)
        updates: dict[str, Any] = {"status": target}
        if external_case_id is not None:
            updates.update(case_id=external_case_id, queue=queue, sla_minutes=sla_minutes)
        self.rows[case_id] = row.model_copy(update=updates)
        return self.rows[case_id]


@dataclass
class FakeCaseWriter:
    """HumanCaseWriter: ``outcome`` is "created", "indeterminate" or "rejected"."""

    journal: list[str] = field(default_factory=list)
    outcome: str = "created"
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def create(self, reason: str, evidence: dict[str, Any]) -> Any:
        from companion.ports.handoff import CreatedCase, HandoffIndeterminate, HandoffRejected

        self.journal.append("create")
        self.calls.append((reason, evidence))
        if self.outcome == "indeterminate":
            raise HandoffIndeterminate
        if self.outcome == "rejected":
            raise HandoffRejected
        return CreatedCase(case_id=f"HC-{len(self.calls)}", queue="DISRUPTION_L2", sla_minutes=45)
