"""Helpers for interpreting recurrence metadata."""

from __future__ import annotations

import re
from typing import Iterable

SUPPORTED_KEYWORDS = (
    "daily",
    "weekly",
    "bi-weekly",
    "monthly",
    "quarterly",
    "bi-annual",
    "yearly",
)

_INTERVAL_PATTERN = re.compile(r"^\s*(?:every\s+)?(\d+)\s+days?\s*$", re.IGNORECASE)
_ORDINAL_PATTERN = re.compile(
    r"^\s*(first|second|third|fourth|last)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s*$",
    re.IGNORECASE,
)


def normalize_recurrence_value(value: str | None) -> str | None:
    """Return a canonical recurrence string or ``None`` if the value is unsupported."""

    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None

    normalized = candidate.casefold()
    if normalized in SUPPORTED_KEYWORDS:
        return normalized

    interval_match = _INTERVAL_PATTERN.match(candidate)
    if interval_match:
        count = int(interval_match.group(1))
        if count >= 1:
            return f"every {count} days"

    ordinal_match = _ORDINAL_PATTERN.match(candidate)
    if ordinal_match:
        ordinal, weekday = ordinal_match.groups()
        return f"{ordinal.lower()} {weekday.lower()}"

    return None


def supported_recurrence_values() -> Iterable[str]:
    """Return the supported recurrence keywords in their canonical form."""

    return tuple(SUPPORTED_KEYWORDS)
