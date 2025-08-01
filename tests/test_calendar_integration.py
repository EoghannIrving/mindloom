"""Tests for calendar integration module."""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import pytest


def test_load_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ics = tmp_path / "cal.ics"
    ics.write_text(
        """BEGIN:VCALENDAR
PRODID:-//Test//EN
VERSION:2.0
BEGIN:VEVENT
UID:1
DTSTAMP:20250101T120000Z
DTSTART;TZID=America/New_York:20250101T090000
DTEND;TZID=America/New_York:20250101T100000
SUMMARY:Meeting
END:VEVENT
BEGIN:VEVENT
UID:2
DTSTAMP:20250102T120000Z
DTSTART;TZID=America/New_York:20250102T090000
DTEND;TZID=America/New_York:20250102T100000
SUMMARY:Next Day
END:VEVENT
END:VCALENDAR""",
        encoding="utf-8",
    )

    monkeypatch.setenv("CALENDAR_ICS_PATH", str(ics))
    monkeypatch.setenv("TIME_ZONE", "UTC")

    import config as cfg

    importlib.reload(cfg)
    import calendar_integration as ci

    importlib.reload(ci)

    events = ci.load_events(date(2025, 1, 1), date(2025, 1, 1))
    assert len(events) == 1
    ev = events[0]
    assert ev.summary == "Meeting"
    from datetime import timedelta

    assert ev.start.tzinfo.utcoffset(ev.start) == timedelta(0)
    assert ev.start.hour == 14
