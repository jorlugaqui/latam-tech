"""POST /api/v1/trips/lookup (spec trip-status, design D6, D10).

A JSON body, never the URL: the surname must not reach access logs. The body is never
logged here; the service logs the decision without personal data.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from companion.composition import get_trip_status_service
from companion.presentation.request_id import request_id_var
from companion.schemas.errors import ErrorResponse
from companion.schemas.trip_status import TripLookupRequest, TripStatusResponse
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
