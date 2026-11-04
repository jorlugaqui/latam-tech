"""Request correlation (spec api-errors, design D5).

A pure ASGI middleware assigns each request an ID, reusing a well-formed incoming
``X-Request-ID``. The ID is exposed through a context variable (for log records), stored in
``scope["state"]`` (for the 500 handler, which runs outside this middleware), and echoed on
the response.
"""

import logging
import re
import uuid
from contextvars import ContextVar

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = "X-Request-ID"
NO_REQUEST = "-"
_VALID = re.compile(r"^[A-Za-z0-9-]{1,64}$")

request_id_var: ContextVar[str] = ContextVar("request_id", default=NO_REQUEST)


def _resolve(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name == b"x-request-id":
            candidate = value.decode("latin-1")
            if _VALID.fullmatch(candidate):
                return candidate
            break
    return uuid.uuid4().hex


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _resolve(scope)
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[HEADER] = request_id
            await send(message)

        token = request_id_var.set(request_id)
        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)


_installed = False


def install_request_id_logging() -> None:
    """Give every log record a ``request_id`` attribute (idempotent)."""
    global _installed
    if _installed:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args: object, **kwargs: object) -> logging.LogRecord:
        record = previous(*args, **kwargs)
        record.request_id = request_id_var.get()
        return record

    logging.setLogRecordFactory(factory)
    _installed = True
