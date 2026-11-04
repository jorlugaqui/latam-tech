from fastapi import APIRouter, Depends

from companion.presentation.auth import require_token
from companion.presentation.responses import PROTECTED_RESPONSES
from companion.schemas.ping import PingResponse

# Every route under /api/v1 is protected by default: new routes join this router.
api_v1_router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(require_token)],
    responses=PROTECTED_RESPONSES,
)


@api_v1_router.get("/ping", response_model=PingResponse, tags=["session"])
def ping() -> PingResponse:
    """Check that the caller's token is accepted."""
    return PingResponse()
