"""Error contract (spec api-errors, design D5): stable bodies, no internals, no echoed input."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from companion.presentation.request_id import HEADER, NO_REQUEST, request_id_var
from companion.schemas.errors import ErrorResponse, FieldError, ValidationErrorResponse
from companion.services.handoff import HandoffUnavailable, NothingToEscalate, OptionNotEligible
from companion.services.trip_status import TripContextUnavailable, TripNotFound

logger = logging.getLogger(__name__)

_HTTP_ERROR_CODES = {404: "not_found", 405: "method_not_allowed"}


class Unauthorized(Exception):
    """Any authentication failure. Deliberately carries no detail (spec api-authentication)."""


def _json(status: int, body: ErrorResponse, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status, content=body.model_dump(exclude_none=True), headers=headers
    )


async def _unauthorized(_: Request, __: Exception) -> JSONResponse:
    return _json(401, ErrorResponse(error="unauthorized"), {"WWW-Authenticate": "Bearer"})


async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _HTTP_ERROR_CODES.get(exc.status_code, "http_error")
    return _json(exc.status_code, ErrorResponse(error=code), exc.headers)


async def _trip_not_found(_: Request, __: Exception) -> JSONResponse:
    # Same body as an unknown route: unknown booking and wrong surname are indistinguishable.
    return _json(404, ErrorResponse(error="not_found"))


async def _trip_context_unavailable(_: Request, __: Exception) -> JSONResponse:
    return _json(503, ErrorResponse(error="trip_context_unavailable"))


async def _option_not_eligible(_: Request, __: Exception) -> JSONResponse:
    return _json(409, ErrorResponse(error="option_not_eligible"))


async def _nothing_to_escalate(_: Request, __: Exception) -> JSONResponse:
    return _json(409, ErrorResponse(error="nothing_to_escalate"))


async def _handoff_unavailable(_: Request, __: Exception) -> JSONResponse:
    return _json(503, ErrorResponse(error="handoff_unavailable"))


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Only location and message: the default handler also returns "input", which would
    # echo submitted values (possibly personal data) back to the caller.
    fields = [FieldError(loc=list(err["loc"]), msg=err["msg"]) for err in exc.errors()]
    body = ValidationErrorResponse(fields=fields)
    return JSONResponse(status_code=422, content=body.model_dump())


async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    # Runs in Starlette's outermost error middleware, after RequestIdMiddleware has exited,
    # so the ID comes from the request state and is re-bound for this log line.
    request_id = request.scope.get("state", {}).get("request_id", NO_REQUEST)
    token = request_id_var.set(request_id)
    try:
        logger.error("unhandled error", exc_info=exc)
    finally:
        request_id_var.reset(token)
    body = ErrorResponse(error="internal_error", request_id=request_id)
    return _json(500, body, {HEADER: request_id})


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(Unauthorized, _unauthorized)
    app.add_exception_handler(TripNotFound, _trip_not_found)
    app.add_exception_handler(TripContextUnavailable, _trip_context_unavailable)
    app.add_exception_handler(OptionNotEligible, _option_not_eligible)
    app.add_exception_handler(NothingToEscalate, _nothing_to_escalate)
    app.add_exception_handler(HandoffUnavailable, _handoff_unavailable)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)
