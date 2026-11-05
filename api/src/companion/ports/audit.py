"""Assessment audit trail (design D15). A write port, kept apart from the read ports."""

from typing import Protocol

from companion.schemas.assessment import Assessment


class AssessmentNotRecorded(Exception):
    """The assessment record could not be written."""


class AssessmentLog(Protocol):
    def record(self, booking_id: str, assessment: Assessment, request_id: str) -> None:
        """Append one record; raises ``AssessmentNotRecorded``. Never stores personal data."""
        ...
