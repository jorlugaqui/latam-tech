"""Design D7: read tool client over HTTP (httpx.MockTransport, no network)."""

import json
from collections.abc import Callable

import httpx
import pytest

from companion.ports.tools import BookingNotFound, ToolUnavailable
from companion.repositories.tools.http import HttpToolsClient
from tests.unit.data.brief import events_payload, trip_context_payload

TOKEN = "tools-token-0123456789abcdef01234567"
Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler) -> tuple[HttpToolsClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = HttpToolsClient(
        "http://mock-tools:8001", TOKEN, timeout_seconds=3, transport=httpx.MockTransport(record)
    )
    return client, seen


def test_trip_context_request_and_parsing() -> None:
    client, seen = _client(lambda r: httpx.Response(200, json=trip_context_payload()))

    context = client.get_trip_context("ABC123")

    assert context.booking_id == "ABC123"
    request = seen[0]
    assert request.method == "POST"
    assert request.url == "http://mock-tools:8001/tools/get_trip_context"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert json.loads(request.content) == {"booking_id": "ABC123"}


def test_events_request_and_parsing() -> None:
    client, seen = _client(lambda r: httpx.Response(200, json=events_payload()))

    events = client.get_operational_events(["S1", "S2"])

    assert len(events.events) == 4
    assert seen[0].url.path == "/tools/get_operational_events"
    assert json.loads(seen[0].content) == {"segment_ids": ["S1", "S2"]}


def test_not_found() -> None:
    client, _ = _client(lambda r: httpx.Response(404, json={"error": "BOOKING_NOT_FOUND"}))

    with pytest.raises(BookingNotFound):
        client.get_trip_context("NOTF01")


def _raise(exc: Exception) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(503, json={"error": "UPSTREAM_UNAVAILABLE"}),
        lambda r: httpx.Response(401),
        lambda r: httpx.Response(200, json={"booking_id": "ABC123"}),
        lambda r: httpx.Response(200, content=b"not json"),
        _raise(httpx.ReadTimeout("slow")),
        _raise(httpx.ConnectError("down")),
    ],
    ids=["503", "401", "invalid-body", "not-json", "timeout", "connect-error"],
)
def test_failures_are_tool_unavailable_and_not_retried(handler: Handler) -> None:
    client, seen = _client(handler)

    with pytest.raises(ToolUnavailable):
        client.get_trip_context("ABC123")
    with pytest.raises(ToolUnavailable):
        client.get_operational_events(["S1"])

    assert len(seen) == 2


def test_events_not_found_is_unavailable() -> None:
    client, _ = _client(lambda r: httpx.Response(404))

    with pytest.raises(ToolUnavailable):
        client.get_operational_events(["S1"])


def _many_events(count: int) -> dict:
    payload = events_payload()
    template = payload["events"][3]
    payload["events"] = [{**template, "event_id": f"E-{i}"} for i in range(count)]
    return payload


def test_oversized_body_is_unavailable_and_not_read_in_full() -> None:
    chunks_sent: list[int] = []

    def stream() -> object:
        for _ in range(100):  # up to 1.6 MB, 16 KiB at a time
            chunks_sent.append(1)
            yield b"x" * 16_384

    client, _ = _client(lambda r: httpx.Response(200, content=stream()))

    with pytest.raises(ToolUnavailable):
        client.get_trip_context("ABC123")

    assert len(chunks_sent) < 100


def test_too_many_events_is_unavailable() -> None:
    client, _ = _client(lambda r: httpx.Response(200, json=_many_events(201)))

    with pytest.raises(ToolUnavailable):
        client.get_operational_events(["S1"])


def test_two_hundred_events_are_accepted() -> None:
    client, _ = _client(lambda r: httpx.Response(200, json=_many_events(200)))

    assert len(client.get_operational_events(["S1"]).events) == 200


# ---- policy and options reads (add-recommendation-and-handoff) --------------------

from companion.ports.tools import PolicyNotFound  # noqa: E402
from companion.schemas.tools import TripContext  # noqa: E402
from tests.unit.data.brief import options_payload, policy_payload  # noqa: E402


def test_policy_request_and_parsing() -> None:
    client, seen = _client(lambda r: httpx.Response(200, json=policy_payload()))

    policy = client.get_policy_rules("DELAY")

    assert policy.version == "POL-DELAY-2026-03"
    assert seen[0].url.path == "/tools/get_policy_rules"
    assert json.loads(seen[0].content) == {"scenario": "DELAY"}


def test_policy_not_found() -> None:
    client, _ = _client(lambda r: httpx.Response(404, json={"error": "POLICY_NOT_FOUND"}))

    with pytest.raises(PolicyNotFound):
        client.get_policy_rules("CANCELLATION")


def test_options_send_the_trip_context() -> None:
    client, seen = _client(lambda r: httpx.Response(200, json=options_payload()))
    context = TripContext.model_validate(trip_context_payload())

    options = client.get_eligible_options(context)

    assert [o.option_id for o in options.options] == ["O1", "O2", "O3"]
    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/tools/get_eligible_options"
    assert body["booking_id"] == "ABC123"
    assert body["_meta"]["completeness"] == "PARTIAL"


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(503),
        lambda r: httpx.Response(200, json={"options": "nope"}),
        lambda r: httpx.Response(200, content=b"x" * (300 * 1024)),
    ],
    ids=["503", "invalid", "oversized"],
)
def test_policy_and_options_failures_are_unavailable(handler: Handler) -> None:
    client, _ = _client(handler)

    with pytest.raises(ToolUnavailable):
        client.get_policy_rules("DELAY")
    with pytest.raises(ToolUnavailable):
        client.get_eligible_options(TripContext.model_validate(trip_context_payload()))
