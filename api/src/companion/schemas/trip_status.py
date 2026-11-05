"""HTTP DTOs for the trip lookup (spec trip-status, design D10).

``TripStatusResponse`` is the whitelist of what a passenger may see: nothing else can be
serialized, because routes declare it as ``response_model``.
"""

import datetime as dt
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from companion.schemas.assessment import (
    ConnectionStatus,
    Explanation,
    NextStep,
    Relevance,
    SegmentStatus,
)

BookingCode = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9]{6}$"),
    AfterValidator(str.upper),
]
LastName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=60, pattern=r"^[\p{L}' \-]+$"),
]


class TripLookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booking_id: BookingCode
    last_name: LastName


class PassengerView(BaseModel):
    first_name: str
    type: str


class ConnectionView(BaseModel):
    to_segment_id: str
    status: ConnectionStatus


class SegmentView(BaseModel):
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
    connection: ConnectionView | None = None


class ReasonView(BaseModel):
    code: str
    segment_ids: list[str]
    event_ids: list[str] = Field(default_factory=list)


class AssessmentView(BaseModel):
    relevance: Relevance
    reasons: list[ReasonView]
    rules_version: str | None = None
    assessed_at: dt.datetime


class TripStatusResponse(BaseModel):
    booking_id: str
    passengers: list[PassengerView]
    segments: list[SegmentView]
    assessment: AssessmentView
    explanation: Explanation
    next_step: NextStep
