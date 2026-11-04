"""Bearer token authentication (spec api-authentication, design D4)."""

import hmac
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from companion.composition import get_settings
from companion.config import Settings
from companion.presentation.errors import Unauthorized

# auto_error=False: the scheme is still documented in OpenAPI, but every failure goes
# through our single Unauthorized path, so all 401s are identical.
bearer_scheme = HTTPBearer(auto_error=False, description="API token (see .env.example)")


def require_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if credentials is None or not credentials.credentials:
        raise Unauthorized
    expected = settings.api_token.get_secret_value().encode()
    if not hmac.compare_digest(credentials.credentials.encode(), expected):
        raise Unauthorized
