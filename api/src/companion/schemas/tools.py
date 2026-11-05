"""Upstream read-tool contracts (brief section 2), as DTOs.

Fields the brief marks as possibly partial are optional. Unknown fields are ignored, so a
new upstream field never breaks parsing. An unknown event ``type`` does fail validation:
the client then reports the tool as unavailable, which the assessment treats as
unverified (fail closed). PII fields are parsed here and stripped by the trip status
service before anything reaches the assessment.
"""

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class _Upstream(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)


class Passenger(_Upstream):
    passenger_id: str
    name: str
    type: str
    email: str | None = None
    phone: str | None = None
    document_id: str | None = None
    loyalty_tier: str | None = None
    age: int | None = None


class Segment(_Upstream):
    segment_id: str
    flight_number: str
    origin: str | None = None
    destination: str | None = None
    date: dt.date | None = None
    scheduled_departure: dt.time | None = None
    scheduled_arrival: dt.time | None = None


class FareConditions(_Upstream):
    changeable: bool | None = None
    refundable: bool | None = None
    fare_family: str | None = None


class TripMeta(_Upstream):
    retrieved_at: dt.datetime
    completeness: str
    missing_fields: list[str] = Field(default_factory=list)


class TripContext(_Upstream):
    booking_id: str
    passengers: list[Passenger]
    segments: list[Segment]
    fare_conditions: FareConditions | None = None
    meta: TripMeta = Field(alias="_meta")


class EventType(StrEnum):
    DELAY = "DELAY"
    GATE_CHANGE = "GATE_CHANGE"
    STATUS = "STATUS"


class OperationalEvent(_Upstream):
    event_id: str
    segment_id: str
    type: EventType
    source: str
    recorded_at: dt.datetime
    delay_minutes: int | None = Field(default=None, ge=0)
    new_departure: dt.time | None = None
    gate: str | None = None
    status: str | None = None


class EventsMeta(_Upstream):
    retrieved_at: dt.datetime
    sources_available: list[str] = Field(default_factory=list)
    sources_degraded: list[str] = Field(default_factory=list)


class OperationalEvents(_Upstream):
    events: list[OperationalEvent]
    meta: EventsMeta = Field(alias="_meta")


# ---- get_policy_rules -------------------------------------------------------------


class PolicyRule(_Upstream):
    rule_id: str
    condition: str = Field(max_length=500)
    entitlement: str
    requires_human_approval: bool


class PolicyMeta(_Upstream):
    retrieved_at: dt.datetime
    superseded_versions: list[str] = Field(default_factory=list)


class PolicyRules(_Upstream):
    scenario: str
    version: str
    effective_from: dt.date
    rules: list[PolicyRule]
    meta: PolicyMeta = Field(alias="_meta")


# ---- get_eligible_options ---------------------------------------------------------


class EligibleOption(_Upstream):
    """A candidate, not a decision. REFUND options carry no flight fields."""

    option_id: str
    type: str
    policy_ref: str
    confidence: str
    flight_number: str | None = None
    origin: str | None = None
    destination: str | None = None
    date: dt.date | None = None
    departure: dt.time | None = None
    fare_difference: int | None = None
    currency: str | None = None
    seats_available: int | None = Field(default=None, ge=0)


class OptionsMeta(_Upstream):
    retrieved_at: dt.datetime
    ttl_seconds: int = Field(ge=0)


class EligibleOptions(_Upstream):
    options: list[EligibleOption]
    meta: OptionsMeta = Field(alias="_meta")
