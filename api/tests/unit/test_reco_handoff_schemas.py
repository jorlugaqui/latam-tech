"""Specs recommendation / human-handoff: request validation and safe response shapes."""

import pytest
from pydantic import ValidationError

from companion.schemas.handoff import Evidence, HumanCaseRequest, HumanCaseResponse
from companion.schemas.recommendation import RecommendationRequest, RecommendationResponse
from tests.unit.test_trip_status_schemas import FORBIDDEN_FIELDS, _field_names


def test_recommendation_request_upper_cases_and_forbids_extras() -> None:
    assert RecommendationRequest(booking_id="abc123", last_name="Silva").booking_id == "ABC123"
    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate(
            {"booking_id": "ABC123", "last_name": "Silva", "relevance": "DISRUPTIVE"}
        )


@pytest.mark.parametrize("option_id", ["O1", "O-12", "OPT1234567890123"])
def test_valid_option_ids(option_id: str) -> None:
    request = HumanCaseRequest(booking_id="ABC123", last_name="Silva", option_id=option_id)

    assert request.option_id == option_id


@pytest.mark.parametrize("option_id", ["", "O 1", "O1;DROP", "x" * 17])
def test_invalid_option_ids(option_id: str) -> None:
    with pytest.raises(ValidationError):
        HumanCaseRequest(booking_id="ABC123", last_name="Silva", option_id=option_id)


def test_option_id_is_optional() -> None:
    assert HumanCaseRequest(booking_id="ABC123", last_name="Silva").option_id is None


@pytest.mark.parametrize("model", [RecommendationResponse, HumanCaseResponse, Evidence])
def test_no_personal_data_fields(model: type) -> None:
    assert _field_names(model) & (FORBIDDEN_FIELDS - {"source"}) == set()
