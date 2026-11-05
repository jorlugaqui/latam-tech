"""Human hand-off DTOs (spec human-handoff, design D7-D9, D11).

``Evidence`` is what the agent receives: ids and codes only, never personal data.
"""

import datetime as dt
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from companion.schemas.assessment import Reason, Relevance
from companion.schemas.recommendation import Entitlement, Exclusion, OptionView
from companion.schemas.trip_status import BookingCode, LastName

OptionId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{1,16}$")]


class CaseReason(StrEnum):
    OPTION_APPROVAL = "OPTION_APPROVAL"
    ASSISTANCE_REQUIRED = "ASSISTANCE_REQUIRED"
    STATUS_VERIFICATION = "STATUS_VERIFICATION"


class CaseStatus(StrEnum):
    REQUESTED = "REQUESTED"
    OPEN = "OPEN"
    INDETERMINATE = "INDETERMINATE"
    FAILED = "FAILED"


class PartyComposition(BaseModel):
    model_config = ConfigDict(frozen=True)

    adults: int
    children: int
    infants: int
    includes_minor: bool


class OptionSnapshot(OptionView):
    expires_at: dt.datetime | None = None


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    booking_id: str
    assessment_id: str
    relevance: Relevance
    reasons: list[Reason]
    rules_version: str | None = None
    policy_version: str | None = None
    entitlements: list[Entitlement] = Field(default_factory=list)
    option: OptionSnapshot | None = None
    excluded_options: list[Exclusion] = Field(default_factory=list)
    party: PartyComposition


class HumanCase(BaseModel):
    """Our local record of a case (human_cases row)."""

    id: str
    booking_id: str
    reason: CaseReason
    status: CaseStatus
    option_id: str | None = None
    case_id: str | None = None
    queue: str | None = None
    sla_minutes: int | None = None
    created_at: dt.datetime


class HumanCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booking_id: BookingCode
    last_name: LastName
    option_id: OptionId | None = None


class HumanCaseResponse(BaseModel):
    status: CaseStatus
    reason: CaseReason
    case_id: str | None = None
    queue: str | None = None
    sla_minutes: int | None = None
    message: str
