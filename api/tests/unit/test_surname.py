"""Spec trip-status: the last name must match a passenger on the booking."""

import pytest

from companion.services.surname import surname_matches

BRIEF = ["María Silva", "Tomás Silva"]


@pytest.mark.parametrize("last_name", ["Silva", "silva", "SILVA", "  Silva  "])
def test_brief_surname_matches(last_name: str) -> None:
    assert surname_matches(last_name, BRIEF)


def test_accents_are_ignored_both_ways() -> None:
    assert surname_matches("Pérez", ["Ana Perez"])
    assert surname_matches("Perez", ["Ana Pérez"])


def test_compound_surname() -> None:
    assert surname_matches("Silva Perez", ["Ana Silva Pérez"])
    assert surname_matches("Pérez", ["Ana Silva Pérez"])


def test_whitespace_is_collapsed() -> None:
    assert surname_matches("Silva   Perez", ["Ana  Silva Pérez"])


@pytest.mark.parametrize("last_name", ["Rojas", "Silv", "María", "Ana Silva"])
def test_mismatch(last_name: str) -> None:
    assert not surname_matches(last_name, [*BRIEF, "Ana Silva Pérez"])


def test_no_passengers() -> None:
    assert not surname_matches("Silva", [])
