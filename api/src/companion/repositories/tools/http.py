"""Read tool client over HTTP (design D7). Implements both read ports.

Timeouts: 1 s connect, ``timeout_seconds`` overall per call. Responses are bounded: the
body is streamed and abandoned past ``MAX_RESPONSE_BYTES``, and an events response with
more than ``MAX_EVENTS`` events is rejected (OWASP API4/API10). No retries: read failures
are handled explicitly by the caller, and retrying only adds latency for the passenger.
Response bodies are never logged.
"""

import logging
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from companion.ports.tools import BookingNotFound, ToolUnavailable
from companion.schemas.tools import OperationalEvents, TripContext

logger = logging.getLogger(__name__)
CONNECT_TIMEOUT_SECONDS = 1.0
MAX_RESPONSE_BYTES = 256 * 1024
MAX_EVENTS = 200


class HttpToolsClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=httpx.Timeout(timeout_seconds, connect=CONNECT_TIMEOUT_SECONDS),
            transport=transport,
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def get_trip_context(self, booking_id: str) -> TripContext:
        return self._call(
            "get_trip_context", {"booking_id": booking_id}, TripContext, not_found=True
        )

    def get_operational_events(self, segment_ids: list[str]) -> OperationalEvents:
        events = self._call(
            "get_operational_events", {"segment_ids": segment_ids}, OperationalEvents
        )
        if len(events.events) > MAX_EVENTS:
            logger.warning("tool get_operational_events returned too many events")
            raise ToolUnavailable
        return events

    def _call[T: BaseModel](
        self, tool: str, body: dict[str, Any], model: type[T], not_found: bool = False
    ) -> T:
        try:
            with self._client.stream("POST", f"/tools/{tool}", json=body) as response:
                if response.status_code == 404 and not_found:
                    raise BookingNotFound
                if response.status_code != 200:
                    logger.warning("tool %s returned %s", tool, response.status_code)
                    raise ToolUnavailable
                content = self._read_bounded(tool, response)
        except httpx.HTTPError as exc:
            logger.warning("tool %s failed: %s", tool, type(exc).__name__)
            raise ToolUnavailable from exc
        try:
            return model.model_validate_json(content)
        except ValidationError as exc:
            logger.warning("tool %s returned a body outside its contract", tool)
            raise ToolUnavailable from exc

    @staticmethod
    def _read_bounded(tool: str, response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                logger.warning("tool %s response exceeds %s bytes", tool, MAX_RESPONSE_BYTES)
                raise ToolUnavailable
            chunks.append(chunk)
        return b"".join(chunks)
