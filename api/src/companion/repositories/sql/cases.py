"""Human case records in SQL (design D8). Status changes go only through the transition
table; rows are never deleted."""

import datetime as dt
import logging
import uuid
from typing import Any

from sqlalchemy import Engine, insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from companion.ports.cases import CasesUnavailable, NewCase
from companion.repositories.sql.tables import human_cases
from companion.schemas.case_states import ACTIVE, transition
from companion.schemas.handoff import CaseStatus, HumanCase

logger = logging.getLogger(__name__)


def _utc(value: dt.datetime) -> dt.datetime:
    return value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value.astimezone(dt.UTC)


def _case(row: Any) -> HumanCase:
    return HumanCase(
        id=row["id"],
        booking_id=row["booking_id"],
        reason=row["reason"],
        status=row["status"],
        option_id=row["option_id"],
        case_id=row["case_id"],
        queue=row["queue"],
        sla_minutes=row["sla_minutes"],
        created_at=_utc(row["created_at"]),
    )


class SqlCaseRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def open_or_get_active(self, case: NewCase) -> tuple[HumanCase, bool]:
        now = dt.datetime.now(dt.UTC)
        row = {
            "id": str(uuid.uuid4()),
            "booking_id": case.booking_id,
            "active_booking_id": case.booking_id,
            "reason": case.reason.value,
            "status": CaseStatus.REQUESTED.value,
            "option_id": case.option_id,
            "assessment_id": case.assessment_id,
            "evidence": case.evidence,
            "request_id": case.request_id,
            "created_at": now,
            "updated_at": now,
        }
        try:
            with self._engine.begin() as connection:
                connection.execute(insert(human_cases).values(**row))
            return self._get(row["id"]), True
        except IntegrityError:
            # The unique active slot is taken: return that case instead of a second one.
            return self._active(case.booking_id), False
        except SQLAlchemyError as exc:
            logger.error("cannot record human case: %s", type(exc).__name__)
            raise CasesUnavailable from exc

    def transition(
        self,
        case_id: str,
        target: CaseStatus,
        external_case_id: str | None = None,
        queue: str | None = None,
        sla_minutes: int | None = None,
    ) -> HumanCase:
        current = self._get(case_id)
        transition(current.status, target)
        values: dict[str, Any] = {"status": target.value, "updated_at": dt.datetime.now(dt.UTC)}
        if target not in ACTIVE:
            values["active_booking_id"] = None
        if external_case_id is not None:
            values.update(case_id=external_case_id, queue=queue, sla_minutes=sla_minutes)
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    update(human_cases)
                    .where(human_cases.c.id == case_id)
                    .where(human_cases.c.status == current.status.value)
                    .values(**values)
                )
        except SQLAlchemyError as exc:
            logger.error("cannot update human case: %s", type(exc).__name__)
            raise CasesUnavailable from exc
        return self._get(case_id)

    def _get(self, case_id: str) -> HumanCase:
        return self._one(select(human_cases).where(human_cases.c.id == case_id))

    def _active(self, booking_id: str) -> HumanCase:
        return self._one(select(human_cases).where(human_cases.c.active_booking_id == booking_id))

    def _one(self, query: Any) -> HumanCase:
        try:
            with self._engine.connect() as connection:
                row = connection.execute(query).mappings().one()
        except SQLAlchemyError as exc:
            logger.error("cannot read human case: %s", type(exc).__name__)
            raise CasesUnavailable from exc
        return _case(row)
