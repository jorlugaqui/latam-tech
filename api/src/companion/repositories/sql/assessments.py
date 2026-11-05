"""Append-only assessment records in SQL (design D15). Insert only: no update or delete."""

import logging
import uuid

from sqlalchemy import Engine, insert
from sqlalchemy.exc import SQLAlchemyError

from companion.ports.audit import AssessmentNotRecorded
from companion.repositories.sql.tables import trip_assessments
from companion.schemas.assessment import Assessment

logger = logging.getLogger(__name__)


class SqlAssessmentLog:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def record(self, booking_id: str, assessment: Assessment, request_id: str) -> str:
        row = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "relevance": assessment.relevance.value,
            "reasons": [r.model_dump(mode="json") for r in assessment.reasons],
            "rejected": [r.model_dump(mode="json") for r in assessment.rejected],
            "rules_version": assessment.rules_version,
            "assessed_at": assessment.assessed_at,
            "request_id": request_id,
        }
        try:
            with self._engine.begin() as connection:
                connection.execute(insert(trip_assessments).values(**row))
        except SQLAlchemyError as exc:
            logger.error("cannot record assessment: %s", type(exc).__name__)
            raise AssessmentNotRecorded from exc
        return row["id"]
