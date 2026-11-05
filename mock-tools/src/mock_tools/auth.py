"""Bearer token check for the tool endpoints (constant-time compare)."""

import hmac


class Unauthorized(Exception):
    pass


def check_bearer(header: str | None, expected: str) -> None:
    scheme, _, token = (header or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized
    if not hmac.compare_digest(token.encode(), expected.encode()):
        raise Unauthorized
