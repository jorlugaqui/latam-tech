"""Booking verification by last name (spec trip-status, design D6). Deterministic.

The surname is taken as the trailing word(s) of a passenger's full ``name``, because the
contract has no surname field (assumption, to confirm with the identity owner). Inputs are
normalized (accents removed, case-folded, whitespace collapsed) and compared in constant
time; every candidate is checked even after a match.
"""

import hmac
import unicodedata


def _words(value: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold().split()


def surname_matches(last_name: str, full_names: list[str]) -> bool:
    wanted = _words(last_name)
    if not wanted:
        return False
    expected = " ".join(wanted).encode()
    matched = False
    for name in full_names:
        words = _words(name)
        # At least one word (the first name) must remain before the surname.
        candidate = " ".join(words[-len(wanted) :]) if len(words) > len(wanted) else ""
        matched |= hmac.compare_digest(candidate.encode(), expected)
    return matched
