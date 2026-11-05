from fastapi import APIRouter, Depends

from companion.presentation.auth import require_token
from companion.presentation.responses import PROTECTED_RESPONSES
from companion.presentation.routers.ping import ping_router
from companion.presentation.routers.trips import trips_router

# Every route under /api/v1 is protected by default: new routers are included here.
api_v1_router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(require_token)],
    responses=PROTECTED_RESPONSES,
)
api_v1_router.include_router(ping_router)
api_v1_router.include_router(trips_router)
