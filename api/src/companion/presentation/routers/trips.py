"""Trip routes: lookup, recommendation, human case (specs trip-status, recommendation,
human-handoff).

A JSON body, never the URL: the surname must not reach access logs. The body is never
logged here; the service logs the decision without personal data.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from companion.composition import (
    get_human_case_service,
    get_recommendation_service,
    get_trip_status_service,
)
from companion.presentation.request_id import request_id_var
from companion.schemas.errors import ErrorResponse
from companion.schemas.handoff import CaseStatus, HumanCaseRequest, HumanCaseResponse
from companion.schemas.recommendation import RecommendationRequest, RecommendationResponse
from companion.schemas.trip_status import TripLookupRequest, TripStatusResponse
from companion.services.handoff import HumanCaseService, response_for
from companion.services.recommendation import RecommendationService
from companion.services.trip_status import TripStatusService

trips_router = APIRouter(prefix="/trips", tags=["trips"])


@trips_router.post(
    "/lookup",
    response_model=TripStatusResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Unknown booking or surname mismatch"},
        503: {"model": ErrorResponse, "description": "Trip context tool unavailable"},
    },
)
def lookup(
    body: TripLookupRequest,
    service: Annotated[TripStatusService, Depends(get_trip_status_service)],
) -> TripStatusResponse:
    """Trip context, verified disruption assessment, explanation and next step."""
    return service.lookup(body.booking_id, body.last_name, request_id_var.get())


@trips_router.post(
    "/recommendation",
    response_model=RecommendationResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Unknown booking or surname mismatch"},
        503: {"model": ErrorResponse, "description": "Trip context tool unavailable"},
    },
)
def recommendation(
    body: RecommendationRequest,
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
) -> RecommendationResponse:
    """Entitlements under the versioned policy and eligible options. Executes nothing:
    every proposal is approved by a person (human case)."""
    result = service.recommend(body.booking_id, body.last_name, request_id_var.get())
    return RecommendationResponse.model_validate(result.model_dump(exclude={"excluded"}))


@trips_router.post(
    "/human-case",
    response_model=HumanCaseResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": HumanCaseResponse, "description": "The booking's active case"},
        202: {"model": HumanCaseResponse, "description": "Outcome unknown: not retried"},
        404: {"model": ErrorResponse, "description": "Unknown booking or surname mismatch"},
        409: {"model": ErrorResponse, "description": "Option not eligible / nothing to escalate"},
        503: {"model": ErrorResponse, "description": "Trip or hand-off unavailable"},
    },
)
def human_case(
    body: HumanCaseRequest,
    response: Response,
    service: Annotated[HumanCaseService, Depends(get_human_case_service)],
) -> HumanCaseResponse:
    """Hand the trip to a person: approval of an option, assistance, or status check."""
    result = service.request(body.booking_id, body.last_name, body.option_id, request_id_var.get())
    if not result.created:
        response.status_code = status.HTTP_200_OK
    elif result.case.status is CaseStatus.INDETERMINATE:
        response.status_code = status.HTTP_202_ACCEPTED
    return response_for(result.case)
