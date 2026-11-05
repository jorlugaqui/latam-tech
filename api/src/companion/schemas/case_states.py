"""Human case lifecycle as an explicit transition table (design D8).

v1 only resolves a request. The back office and the rebooking flow will add states
(APPROVED, REJECTED, REBOOK_REQUESTED, ...) here without touching the services
(docs/future-work.md).
"""

from companion.schemas.handoff import CaseStatus


class IllegalTransition(Exception):
    pass


_TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.REQUESTED: frozenset({CaseStatus.OPEN, CaseStatus.INDETERMINATE, CaseStatus.FAILED}),
}

# A booking with a case in one of these has an active case: no new case is created.
ACTIVE: frozenset[CaseStatus] = frozenset(
    {CaseStatus.REQUESTED, CaseStatus.OPEN, CaseStatus.INDETERMINATE}
)


def transition(current: CaseStatus, target: CaseStatus) -> CaseStatus:
    if target not in _TRANSITIONS.get(current, frozenset()):
        raise IllegalTransition(f"{current} -> {target}")
    return target
