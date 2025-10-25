"""Tests for calendar integration module."""

from __future__ import annotations

import importlib
from datetime import date, datetime
from pathlib import Path
import sys

import pytest
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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


def test_directory_ics_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ics_dir = tmp_path / "cals"
    ics_dir.mkdir()
    (ics_dir / "one.ics").write_text(
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
END:VCALENDAR""",
        encoding="utf-8",
    )
    (ics_dir / "two.ics").write_text(
        """BEGIN:VCALENDAR
PRODID:-//Test//EN
VERSION:2.0
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

    monkeypatch.setenv("CALENDAR_ICS_PATH", str(ics_dir))
    monkeypatch.setenv("TIME_ZONE", "UTC")

    import config as cfg

    importlib.reload(cfg)
    import calendar_integration as ci

    importlib.reload(ci)

    events = ci.load_events(date(2025, 1, 1), date(2025, 1, 2))
    assert {e.summary for e in events} == {"Meeting", "Next Day"}


def test_google_calendar(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CALENDAR_ICS_PATH", "")
    monkeypatch.setenv("GOOGLE_CALENDAR_ID", "demo")
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", "/creds.json")
    monkeypatch.setenv("TIME_ZONE", "America/New_York")

    import config as cfg

    importlib.reload(cfg)
    import calendar_integration as ci

    importlib.reload(ci)

    items = [
        {
            "summary": "Timed Event",
            "start": {"dateTime": "2025-01-03T15:00:00Z"},
            "end": {"dateTime": "2025-01-03T16:00:00Z"},
        },
        {
            "summary": "All Day Event",
            "start": {"date": "2025-01-04"},
            "end": {"date": "2025-01-05"},
        },
    ]

    class DummyCredentials:
        @classmethod
        def from_service_account_file(cls, *args, **kwargs):
            return object()

    class DummyService:
        def __init__(self, items):
            self._items = items

        def events(self):
            return self

        def list(self, **kwargs):
            return self

        def execute(self):
            return {"items": self._items}

    monkeypatch.setattr(ci, "Credentials", DummyCredentials)
    monkeypatch.setattr(ci, "build", lambda *args, **kwargs: DummyService(items))

    events = ci.load_events(date(2025, 1, 3), date(2025, 1, 4))
    assert [event.summary for event in events] == ["Timed Event", "All Day Event"]

    tz = ZoneInfo("America/New_York")
    timed = events[0]
    assert timed.start == datetime(2025, 1, 3, 10, 0, tzinfo=tz)
    assert timed.end == datetime(2025, 1, 3, 11, 0, tzinfo=tz)

    all_day = events[1]
    assert all_day.start == datetime(2025, 1, 4, 0, 0, tzinfo=tz)
    assert all_day.end == datetime(2025, 1, 5, 0, 0, tzinfo=tz)
