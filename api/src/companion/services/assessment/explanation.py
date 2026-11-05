"""Passenger explanation (spec disruption-assessment, design D4). Deterministic.

``ExplanationComposer`` is the Strategy seam for wording. ``TemplateComposer`` fills fixed
templates from accepted facts only: it never mentions rejected events, sources,
entitlements or personal data. A future LLM composer would reword the same structured
claims behind a deterministic verifier (README, next steps); it is not part of this demo.
"""

import datetime as dt
from typing import ClassVar, Protocol

from companion.schemas.assessment import (
    Assessment,
    ConnectionStatus,
    Explanation,
    Relevance,
    SegmentImpact,
    SegmentStatus,
    TripFacts,
)


class ExplanationComposer(Protocol):
    def compose(self, assessment: Assessment, facts: TripFacts) -> Explanation: ...


def _hhmm(moment: dt.datetime | None) -> str:
    return moment.strftime("%H:%M") if moment else ""


class TemplateComposer:
    HEADLINES: ClassVar[dict[Relevance, str]] = {
        Relevance.DISRUPTIVE: "Your trip has been affected by a change.",
        Relevance.UNVERIFIED: "We're confirming your flight status.",
        Relevance.INFORMATIONAL: "There's an update to your trip.",
        Relevance.NONE: "Your trip is on schedule.",
    }
    UNVERIFIED_DETAILS: ClassVar[list[str]] = [
        "Some information about your trip could not be verified yet, so we are not "
        "showing changes until they are confirmed.",
        "An agent can help you in the meantime.",
    ]

    def compose(self, assessment: Assessment, facts: TripFacts) -> Explanation:
        headline = self.HEADLINES[assessment.relevance]
        if assessment.relevance is Relevance.UNVERIFIED:
            return Explanation(headline=headline, details=list(self.UNVERIFIED_DETAILS))
        by_id = {s.segment_id: s for s in assessment.segments}
        details: list[str] = []
        for segment in assessment.segments:
            details.extend(self._segment_lines(segment, by_id))
        return Explanation(headline=headline, details=details)

    @staticmethod
    def _segment_lines(segment: SegmentImpact, by_id: dict[str, SegmentImpact]) -> list[str]:
        route = f"{segment.flight_number} from {segment.origin} to {segment.destination}"
        lines: list[str] = []
        if segment.status is SegmentStatus.CANCELLED:
            lines.append(f"{route} has been cancelled.")
        elif segment.status is SegmentStatus.DELAYED:
            lines.append(
                f"{route} is delayed by {segment.delay_minutes} minutes. It is now expected "
                f"to depart at {_hhmm(segment.estimated_departure)} and arrive in "
                f"{segment.destination} at {_hhmm(segment.estimated_arrival)} (local times)."
            )
        if segment.gate and segment.status is not SegmentStatus.CANCELLED:
            lines.append(f"{segment.flight_number} departs from gate {segment.gate}.")
        connection = segment.connection
        if connection is not None:
            onward = by_id[connection.to_segment_id]
            onward_text = (
                f"{onward.flight_number} departing {onward.origin} at "
                f"{_hhmm(onward.scheduled_departure)}"
            )
            if connection.status is ConnectionStatus.MISSED:
                lines.append(f"With this change you will miss your connection {onward_text}.")
            elif connection.status is ConnectionStatus.UNREACHABLE:
                lines.append(f"Your onward flight {onward_text} is affected by this change.")
        return lines
