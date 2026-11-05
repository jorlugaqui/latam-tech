"""Local record of human cases (design D8)."""

from dataclasses import dataclass
from typing import Any, Protocol

from companion.schemas.handoff import CaseReason, CaseStatus, HumanCase


class CasesUnavailable(Exception):
    """The case record cannot be read or written."""


@dataclass(frozen=True)
class NewCase:
    booking_id: str
    reason: CaseReason
    option_id: str | None
    assessment_id: str
    evidence: dict[str, Any]
    request_id: str


class CaseRepository(Protocol):
    def open_or_get_active(self, case: NewCase) -> tuple[HumanCase, bool]:
        """Insert as REQUESTED and return (case, True), or return (active case, False)
        when the booking already has one. Raises ``CasesUnavailable``."""
        ...

    def transition(
        self,
        case_id: str,
        target: CaseStatus,
        external_case_id: str | None = None,
        queue: str | None = None,
        sla_minutes: int | None = None,
    ) -> HumanCase:
        """Move through the state machine only. Raises ``IllegalTransition`` or
        ``CasesUnavailable``."""
        ...
