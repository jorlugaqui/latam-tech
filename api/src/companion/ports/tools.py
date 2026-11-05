"""Read-tool ports (design D7). Write tools get separate Protocols (ISP, least privilege)."""

from typing import Protocol

from companion.schemas.tools import EligibleOptions, OperationalEvents, PolicyRules, TripContext


class BookingNotFound(Exception):
    """The trip context tool does not know the booking."""


class ToolUnavailable(Exception):
    """A tool timed out, failed, or returned a body that does not match its contract."""


class PolicyNotFound(Exception):
    """No policy exists for the requested scenario."""


class TripContextReader(Protocol):
    def get_trip_context(self, booking_id: str) -> TripContext: ...


class OperationalEventsReader(Protocol):
    def get_operational_events(self, segment_ids: list[str]) -> OperationalEvents: ...


class PolicyReader(Protocol):
    def get_policy_rules(self, scenario: str) -> PolicyRules:
        """Raises ``PolicyNotFound`` or ``ToolUnavailable``."""
        ...


class OptionsReader(Protocol):
    def get_eligible_options(self, context: TripContext) -> EligibleOptions:
        """Candidates, not decisions. Raises ``ToolUnavailable``."""
        ...
