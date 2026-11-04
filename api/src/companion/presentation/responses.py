"""Shared OpenAPI response declarations (spec api-docs, design D12).

Attached at router level, so every route documents the errors the error handlers can
actually return, and new routes inherit them.
"""

from typing import Any

from companion.schemas.errors import ErrorResponse, ValidationErrorResponse

ResponseMap = dict[int | str, dict[str, Any]]

PUBLIC_RESPONSES: ResponseMap = {
    404: {"model": ErrorResponse, "description": "Unknown route"},
    422: {"model": ValidationErrorResponse, "description": "Invalid input (values not echoed)"},
    500: {"model": ErrorResponse, "description": "Unexpected error; carries request_id"},
}

PROTECTED_RESPONSES: ResponseMap = {
    401: {"model": ErrorResponse, "description": "Missing or invalid Bearer token"},
    **PUBLIC_RESPONSES,
}
