"""Design D9: create_human_case over HTTP. No retries; unknown outcomes are indeterminate."""

import json
import logging

import httpx
import pytest

from companion.ports.handoff import CreatedCase, HandoffIndeterminate, HandoffRejected
from companion.repositories.tools.http import HttpCaseWriter

TOKEN = "tools-token-0123456789abcdef01234567"
EVIDENCE = {"booking_id": "ABC123", "secret_marker": "EVIDENCE-CONTENT"}


def _writer(handler) -> tuple[HttpCaseWriter, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    writer = HttpCaseWriter(
        "http://mock-tools:8001", TOKEN, timeout_seconds=3, transport=httpx.MockTransport(record)
    )
    return writer, seen


def test_created() -> None:
    body = {"case_id": "HC-4471", "queue": "DISRUPTION_L2", "sla_minutes": 45}
    writer, seen = _writer(lambda r: httpx.Response(201, json=body))

    created = writer.create("OPTION_APPROVAL", EVIDENCE)

    assert created == CreatedCase(case_id="HC-4471", queue="DISRUPTION_L2", sla_minutes=45)
    assert seen[0].url.path == "/tools/create_human_case"
    assert seen[0].headers["Authorization"] == f"Bearer {TOKEN}"
    assert json.loads(seen[0].content) == {"reason": "OPTION_APPROVAL", "evidence": EVIDENCE}


def _raise(exc: Exception):
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(503, json={"error": "UPSTREAM_TIMEOUT"}),
        lambda r: httpx.Response(500),
        _raise(httpx.ReadTimeout("slow")),
        _raise(httpx.ConnectError("down")),
        lambda r: httpx.Response(201, json={"unexpected": True}),
    ],
    ids=["503", "500", "timeout", "connect-error", "201-unreadable"],
)
def test_unknown_outcomes_are_indeterminate_and_never_retried(handler) -> None:
    writer, seen = _writer(handler)

    with pytest.raises(HandoffIndeterminate):
        writer.create("OPTION_APPROVAL", EVIDENCE)

    assert len(seen) == 1


@pytest.mark.parametrize("status", [400, 401, 409, 422])
def test_definite_refusals_are_rejected(status: int) -> None:
    writer, seen = _writer(lambda r: httpx.Response(status))

    with pytest.raises(HandoffRejected):
        writer.create("OPTION_APPROVAL", EVIDENCE)

    assert len(seen) == 1


def test_evidence_is_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    writer, _ = _writer(lambda r: httpx.Response(503))

    with caplog.at_level(logging.DEBUG), pytest.raises(HandoffIndeterminate):
        writer.create("OPTION_APPROVAL", EVIDENCE)

    assert "EVIDENCE-CONTENT" not in caplog.text
