"""Mock implementations of the brief's tool contracts (spec mock-tools).

The scenario is chosen by booking code, so the API needs no knowledge of scenarios.
"""

import datetime as dt
import uuid
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from mock_tools import fixtures
from mock_tools.auth import Unauthorized, check_bearer
from mock_tools.settings import MockToolsSettings
from mock_tools.timeshift import shift_events, shift_options, shift_policy, shift_trip_context

Clock = Callable[[], dt.datetime]


class TripContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_id: str = Field(min_length=1, max_length=16)


class EventsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    segment_ids: list[Annotated[str, Field(min_length=1, max_length=32)]] = Field(max_length=20)


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: str = Field(min_length=1, max_length=32)


class OptionsRequest(BaseModel):
    """The body is a trip context: only its booking code selects the scenario."""

    model_config = ConfigDict(extra="ignore")
    booking_id: str = Field(min_length=1, max_length=16)


class CaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=64)
    evidence: dict[str, Any]


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

    @app.post("/tools/get_policy_rules")
    def get_policy_rules(
        body: PolicyRequest, authorization: Annotated[str | None, Header()] = None
    ) -> JSONResponse:
        check_bearer(authorization, token)
        policy = fixtures.POLICIES.get(body.scenario)
        if policy is None:
            return _error(404, "POLICY_NOT_FOUND")
        return JSONResponse(shift_policy(policy, now()))

    @app.post("/tools/get_eligible_options")
    def get_eligible_options(
        body: OptionsRequest, authorization: Annotated[str | None, Header()] = None
    ) -> JSONResponse:
        check_bearer(authorization, token)
        return JSONResponse(shift_options(fixtures.options_for(body.booking_id), now()))

    @app.post("/tools/create_human_case")
    def create_human_case(
        body: CaseRequest, authorization: Annotated[str | None, Header()] = None
    ) -> JSONResponse:
        # Stateless like the brief's contract: no idempotency key, no deduplication.
        check_bearer(authorization, token)
        if body.evidence.get("booking_id") in fixtures.UNAVAILABLE_CASES:
            return _error(503, "UPSTREAM_TIMEOUT")
        case = {
            "case_id": f"HC-{uuid.uuid4().hex[:6].upper()}",
            "queue": "DISRUPTION_L2",
            "sla_minutes": 45,
        }
        return JSONResponse(status_code=201, content=case)

    return app
