"""Recommendation DTOs (spec recommendation, design D6, D11).

``Recommendation`` is the internal result (it keeps excluded options for logs and the
case evidence); ``RecommendationResponse`` is the passenger whitelist.
"""

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from companion.schemas.assessment import Explanation, NextStep
from companion.schemas.trip_status import BookingCode, LastName


class RecommendationStatus(StrEnum):
    PROPOSED = "PROPOSED"
    NEEDS_AGENT = "NEEDS_AGENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RecommendationReason(StrEnum):
    POLICY_UNAVAILABLE = "POLICY_UNAVAILABLE"
    NO_ELIGIBLE_OPTION = "NO_ELIGIBLE_OPTION"
    OPTIONS_EXPIRED = "OPTIONS_EXPIRED"
    OPTIONS_UNAVAILABLE = "OPTIONS_UNAVAILABLE"


class Approval(StrEnum):
    # v1: the human case is the approval mechanism for every action.
    HUMAN_REQUIRED = "HUMAN_REQUIRED"


class ExclusionCode(StrEnum):
    NOT_ENTITLED = "NOT_ENTITLED"
    INSUFFICIENT_SEATS = "INSUFFICIENT_SEATS"
    FEE_CONFLICTS_ENTITLEMENT = "FEE_CONFLICTS_ENTITLEMENT"
    WRONG_ROUTE = "WRONG_ROUTE"
    DEPARTS_TOO_EARLY = "DEPARTS_TOO_EARLY"
    POLICY_SUPERSEDED = "POLICY_SUPERSEDED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class Entitlement(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    rule_id: str
    requires_human_approval: bool


class OptionView(BaseModel):
    model_config = ConfigDict(frozen=True)

    option_id: str
    type: str
    flight_number: str | None = None
    origin: str | None = None
    destination: str | None = None
    departure: dt.datetime | None = None
    fare_difference: int | None = None
    currency: str | None = None
    confidence: str


class Exclusion(BaseModel):
    model_config = ConfigDict(frozen=True)

    option_id: str
    codes: list[ExclusionCode]


class Recommendation(BaseModel):
    status: RecommendationStatus
    reason: RecommendationReason | None = None
    policy_version: str | None = None
    entitlements: list[Entitlement] = Field(default_factory=list)
    unevaluated_rules: list[str] = Field(default_factory=list)
    options: list[OptionView] = Field(default_factory=list)
    excluded: list[Exclusion] = Field(default_factory=list)
    options_expire_at: dt.datetime | None = None
    approval: Approval = Approval.HUMAN_REQUIRED
    explanation: Explanation
    next_step: NextStep


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booking_id: BookingCode
    last_name: LastName


class RecommendationResponse(BaseModel):
    status: RecommendationStatus
    reason: RecommendationReason | None = None
    policy_version: str | None = None
    entitlements: list[Entitlement]
    unevaluated_rules: list[str]
    options: list[OptionView]
    options_expire_at: dt.datetime | None = None
    approval: Approval
    explanation: Explanation
    next_step: NextStep
