"""The write port for the human hand-off (design D9). Kept apart from every read port:
an import-linter contract forbids read-only services from importing this module."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CreatedCase:
    case_id: str
    queue: str
    sla_minutes: int


class HandoffIndeterminate(Exception):
    """The outcome is unknown (timeout, 5xx, unreadable 201): never retry blindly."""


class HandoffRejected(Exception):
    """The tool definitely did not create a case."""


class HumanCaseWriter(Protocol):
    def create(self, reason: str, evidence: dict[str, Any]) -> CreatedCase: ...
