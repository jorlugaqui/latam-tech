from typing import Literal

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Error body for every non-validation failure. ``request_id`` is set only on 500s."""

    error: str
    request_id: str | None = None


class FieldError(BaseModel):
    loc: list[str | int]
    msg: str


class ValidationErrorResponse(BaseModel):
    error: Literal["validation_error"] = "validation_error"
    fields: list[FieldError]
