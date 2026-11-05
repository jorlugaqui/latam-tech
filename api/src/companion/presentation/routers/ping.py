from fastapi import APIRouter

from companion.schemas.ping import PingResponse

ping_router = APIRouter(tags=["session"])


@ping_router.get("/ping", response_model=PingResponse)
def ping() -> PingResponse:
    """Check that the caller's token is accepted."""
    return PingResponse()
