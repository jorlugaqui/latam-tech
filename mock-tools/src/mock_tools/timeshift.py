"""Fixtures are written against the brief's reference instant. When served, every UTC
instant moves by ``now - REFERENCE`` (so freshness survives a live demo) and every segment
date moves by the same number of whole days. Local scheduled times never change."""

import copy
import datetime as dt
from typing import Any

REFERENCE = dt.datetime(2026, 9, 15, 11, 2, 33, tzinfo=dt.UTC)
_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def instant(offset: dt.timedelta = dt.timedelta()) -> str:
    """An instant relative to the reference, as fixtures write it."""
    return (REFERENCE + offset).strftime(_FORMAT)


def _shift_instant(value: str, delta: dt.timedelta) -> str:
    parsed = dt.datetime.strptime(value, _FORMAT).replace(tzinfo=dt.UTC)
    return (parsed + delta).strftime(_FORMAT)


def shift_trip_context(payload: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    shifted = copy.deepcopy(payload)
    days = dt.timedelta(days=(now.date() - REFERENCE.date()).days)
    for segment in shifted["segments"]:
        if "date" in segment:
            segment["date"] = (dt.date.fromisoformat(segment["date"]) + days).isoformat()
    shifted["_meta"]["retrieved_at"] = now.strftime(_FORMAT)
    return shifted


def shift_events(payload: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    shifted = copy.deepcopy(payload)
    delta = now - REFERENCE
    for event in shifted["events"]:
        event["recorded_at"] = _shift_instant(event["recorded_at"], delta)
    shifted["_meta"]["retrieved_at"] = now.strftime(_FORMAT)
    return shifted


def shift_options(payload: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    shifted = copy.deepcopy(payload)
    days = dt.timedelta(days=(now.date() - REFERENCE.date()).days)
    for option in shifted["options"]:
        if "date" in option:
            option["date"] = (dt.date.fromisoformat(option["date"]) + days).isoformat()
    shifted["_meta"]["retrieved_at"] = now.strftime(_FORMAT)
    return shifted


def shift_policy(payload: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    shifted = copy.deepcopy(payload)
    shifted["_meta"]["retrieved_at"] = now.strftime(_FORMAT)
    return shifted
