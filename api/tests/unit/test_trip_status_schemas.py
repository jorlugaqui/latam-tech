"""Spec trip-status: lookup input validation and the passenger-safe response shape."""

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from companion.schemas.trip_status import TripLookupRequest, TripStatusResponse

FORBIDDEN_FIELDS = {
    "email",
    "phone",
    "document_id",
    "loyalty_tier",
    "age",
    "passenger_id",
    "name",
    "fare_conditions",
    "source",
    "rejected",
}


def test_booking_code_is_upper_cased() -> None:
    request = TripLookupRequest(booking_id="abc123", last_name="Silva")

    assert request.booking_id == "ABC123"


@pytest.mark.parametrize("booking_id", ["ABC-12", "ABC12", "ABC1234", "", "ABC 12"])
def test_malformed_booking_code_is_rejected(booking_id: str) -> None:
    with pytest.raises(ValidationError):
        TripLookupRequest(booking_id=booking_id, last_name="Silva")


@pytest.mark.parametrize("last_name", ["Silva", "Silva Pérez", "O'Brien", "Smith-Jones", "Ñúñez"])
def test_valid_last_names(last_name: str) -> None:
    assert TripLookupRequest(booking_id="ABC123", last_name=last_name).last_name == last_name


@pytest.mark.parametrize("last_name", ["", "x" * 61, "Silva1", "<script>", "Silva;"])
def test_invalid_last_names(last_name: str) -> None:
    with pytest.raises(ValidationError):
        TripLookupRequest(booking_id="ABC123", last_name=last_name)


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        TripLookupRequest.model_validate(
            {"booking_id": "ABC123", "last_name": "Silva", "relevance": "DISRUPTIVE"}
        )


def _field_names(model: type[BaseModel], seen: set[type] | None = None) -> set[str]:
    seen = seen or set()
    if model in seen:
        return set()
    seen.add(model)
    names = set(model.model_fields)
    for field in model.model_fields.values():
        for candidate in _nested_models(field.annotation):
            names |= _field_names(candidate, seen)
    return names


def _nested_models(annotation: Any) -> list[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return [m for arg in getattr(annotation, "__args__", ()) for m in _nested_models(arg)]


def test_response_has_no_forbidden_field() -> None:
    names = _field_names(TripStatusResponse)

    assert names & FORBIDDEN_FIELDS == set()
    assert {"first_name", "next_step", "rules_version", "explanation"} <= names
