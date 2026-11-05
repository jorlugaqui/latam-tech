"""Spec human-handoff: case outcomes follow an explicit state machine."""

import pytest

from companion.schemas.case_states import ACTIVE, IllegalTransition, transition
from companion.schemas.handoff import CaseStatus

S = CaseStatus


@pytest.mark.parametrize("target", [S.OPEN, S.INDETERMINATE, S.FAILED])
def test_requested_can_resolve(target: CaseStatus) -> None:
    assert transition(S.REQUESTED, target) is target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.OPEN, S.INDETERMINATE),
        (S.OPEN, S.FAILED),
        (S.INDETERMINATE, S.OPEN),
        (S.FAILED, S.OPEN),
        (S.REQUESTED, S.REQUESTED),
        (S.OPEN, S.REQUESTED),
    ],
)
def test_illegal_transitions(current: CaseStatus, target: CaseStatus) -> None:
    with pytest.raises(IllegalTransition):
        transition(current, target)


def test_active_statuses_block_a_new_case() -> None:
    assert frozenset({S.REQUESTED, S.OPEN, S.INDETERMINATE}) == ACTIVE
