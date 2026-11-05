"""Domain DTOs for the disruption assessment (spec disruption-assessment, design D1-D5).

``TripFacts`` is the only view of a booking the assessment receives. It holds no personal
data by construction (no names beyond first names, no contact or document data), so no
solver or composer, including a future AI one, can leak it.
"""

import datetime as dt
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Relevance(StrEnum):
    NONE = "NONE"
    INFORMATIONAL = "INFORMATIONAL"
    DISRUPTIVE = "DISRUPTIVE"
    UNVERIFIED = "UNVERIFIED"


class Tier(StrEnum):
    DISRUPTIVE = "DISRUPTIVE"
    INFORMATIONAL = "INFORMATIONAL"


class SegmentStatus(StrEnum):
    ON_SCHEDULE = "ON_SCHEDULE"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"
    UNVERIFIED = "UNVERIFIED"


class ConnectionStatus(StrEnum):
    OK = "OK"
    MISSED = "MISSED"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"


class NextStep(StrEnum):
    RECOMMENDATION = "RECOMMENDATION"
    HUMAN_ASSISTANCE = "HUMAN_ASSISTANCE"
    NONE = "NONE"


class ReasonCode(StrEnum):
    """Reasons that are not criteria. Criterion reasons use the criterion key."""

    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    INCONSISTENT_EVENT = "INCONSISTENT_EVENT"
    AIRPORT_UNKNOWN = "AIRPORT_UNKNOWN"
    CONTEXT_INCOMPLETE = "CONTEXT_INCOMPLETE"
    NO_FRESH_EVIDENCE = "NO_FRESH_EVIDENCE"
    EVENTS_UNAVAILABLE = "EVENTS_UNAVAILABLE"
    RULES_UNAVAILABLE = "RULES_UNAVAILABLE"


class RejectionReason(StrEnum):
    SOURCE_DEGRADED = "SOURCE_DEGRADED"
    SOURCE_UNKNOWN = "SOURCE_UNKNOWN"
    STALE = "STALE"


# ---- inputs -----------------------------------------------------------------------


class PassengerFacts(_Frozen):
    first_name: str
    type: str


class SegmentFacts(_Frozen):
    segment_id: str
    flight_number: str
    origin: str | None = None
    destination: str | None = None
    date: dt.date | None = None
    scheduled_departure: dt.time | None = None
    scheduled_arrival: dt.time | None = None


class TripFacts(_Frozen):
    booking_id: str
    passengers: list[PassengerFacts]
    segments: list[SegmentFacts]


class CriterionConfig(_Frozen):
    key: str
    enabled: bool
    tier: Tier
    params: dict[str, Any] = Field(default_factory=dict)


class RelevanceRuleSet(_Frozen):
    version: str
    effective_from: dt.datetime
    effective_to: dt.datetime | None = None
    freshness_max_age_minutes: int = Field(gt=0)
    criteria: list[CriterionConfig]


class AirportInfo(_Frozen):
    iata: str
    iana_tz: str


# ---- outputs ----------------------------------------------------------------------


class Reason(_Frozen):
    code: str
    segment_ids: list[str]
    event_ids: list[str] = Field(default_factory=list)


class RejectedEvent(_Frozen):
    event_id: str
    reason: RejectionReason


class ConnectionImpact(_Frozen):
    to_segment_id: str
    status: ConnectionStatus


class SegmentImpact(_Frozen):
    segment_id: str
    flight_number: str
    origin: str | None = None
    destination: str | None = None
    scheduled_departure: dt.datetime | None = None
    scheduled_arrival: dt.datetime | None = None
    estimated_departure: dt.datetime | None = None
    estimated_arrival: dt.datetime | None = None
    status: SegmentStatus
    delay_minutes: int | None = None
    gate: str | None = None
    gate_event_id: str | None = None
    unverified_reason: str | None = None
    evidence: list[str] = Field(default_factory=list)
    connection: ConnectionImpact | None = None


class Assessment(_Frozen):
    relevance: Relevance
    reasons: list[Reason]
    segments: list[SegmentImpact]
    rejected: list[RejectedEvent] = Field(default_factory=list)
    rules_version: str | None = None
    assessed_at: dt.datetime


class Explanation(_Frozen):
    headline: str
    details: list[str] = Field(default_factory=list)
