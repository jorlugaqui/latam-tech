from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from companion.composition import get_health_service
from companion.presentation.responses import PUBLIC_RESPONSES
from companion.schemas.health import LiveStatus, ReadyStatus
from companion.services.health import HealthService

# Mounted outside /api: public for orchestration probes (spec api-authentication).
health_router = APIRouter(prefix="/health", tags=["health"], responses=PUBLIC_RESPONSES)


@health_router.get("/live", response_model=LiveStatus)
def live() -> LiveStatus:
    """The process is running. Checks no dependency."""
    return LiveStatus()


@health_router.get(
    "/ready",
    response_model=ReadyStatus,
    responses={503: {"model": ReadyStatus, "description": "The database is unreachable"}},
)
def ready(
    response: Response,
    service: Annotated[HealthService, Depends(get_health_service)],
) -> ReadyStatus:
    """The API can serve requests (the database answers)."""
    result = service.readiness()
    if result.status != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
