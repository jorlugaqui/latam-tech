"""Mock implementations of the read tool contracts (spec mock-tools, design D9).

The scenario is chosen by booking code, so the API needs no knowledge of scenarios.
"""

import datetime as dt
from collections.abc import Callable
from typing import Annotated

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from mock_tools import fixtures
from mock_tools.auth import Unauthorized, check_bearer
from mock_tools.settings import MockToolsSettings
from mock_tools.timeshift import shift_events, shift_trip_context

Clock = Callable[[], dt.datetime]


class TripContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_id: str = Field(min_length=1, max_length=16)


class EventsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    segment_ids: list[Annotated[str, Field(min_length=1, max_length=32)]] = Field(max_length=20)


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


def create_app(settings: MockToolsSettings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings or MockToolsSettings()
    now: Clock = clock or (lambda: dt.datetime.now(dt.UTC))
    token = settings.tools_api_token.get_secret_value()
    app = FastAPI(
        title="Disruption Companion mock tools", docs_url=None, redoc_url=None, openapi_url=None
    )

    @app.exception_handler(Unauthorized)
    async def _unauthorized(_: Request, __: Exception) -> JSONResponse:
        return _error(401, "unauthorized")

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/tools/get_trip_context")
    def get_trip_context(
        body: TripContextRequest, authorization: Annotated[str | None, Header()] = None
    ) -> JSONResponse:
        check_bearer(authorization, token)
        if body.booking_id in fixtures.UNAVAILABLE_CONTEXTS:
            return _error(503, "UPSTREAM_UNAVAILABLE")
        payload = fixtures.TRIP_CONTEXTS.get(body.booking_id)
        if payload is None:
            return _error(404, "BOOKING_NOT_FOUND")
        return JSONResponse(shift_trip_context(payload, now()))

    @app.post("/tools/get_operational_events")
    def get_operational_events(
        body: EventsRequest, authorization: Annotated[str | None, Header()] = None
    ) -> JSONResponse:
        check_bearer(authorization, token)
        if fixtures.events_unavailable(body.segment_ids):
            return _error(503, "UPSTREAM_UNAVAILABLE")
        return JSONResponse(shift_events(fixtures.events_for(body.segment_ids), now()))

    return app
