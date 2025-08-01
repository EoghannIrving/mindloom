"""Utilities for loading calendar events from .ics files or Google Calendar."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List
from zoneinfo import ZoneInfo

from ics import Calendar

from config import config, PROJECT_ROOT

try:
    from googleapiclient.discovery import build
    from google.oauth2.service_account import Credentials
except Exception:  # pragma: no cover - optional dependency
    build = None
    Credentials = None

CACHE_PATH = PROJECT_ROOT / "data/calendar_cache.json"
ICS_PATHS = [
    Path(p).expanduser()
    for p in os.getenv(
        "CALENDAR_ICS_PATH", str(PROJECT_ROOT / "data/calendar.ics")
    ).split(os.pathsep)
]
TIME_ZONE = os.getenv("TIME_ZONE", getattr(config, "TIME_ZONE", "UTC"))
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")

LOG_FILE = Path(config.LOG_DIR) / "calendar.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@dataclass
class Event:
    """Simple calendar event."""

    summary: str
    start: datetime
    end: datetime


def _read_ics_events() -> List[Event]:
    tz = ZoneInfo(TIME_ZONE)
    events: List[Event] = []
    for path in ICS_PATHS:
        if not path.exists():
            logger.info("ICS file %s does not exist", path)
            continue
        logger.info("Parsing %s", path)
        text = path.read_text(encoding="utf-8")
        cal = Calendar(text)
        for item in cal.events:
            start = item.begin.to(TIME_ZONE).datetime
            end = item.end.to(TIME_ZONE).datetime
            events.append(Event(item.name or "", start, end))
    return events


def _read_google_calendar_events(start: date, end: date) -> List[Event]:
    """Return events from Google Calendar between start and end."""
    if not (build and Credentials and GOOGLE_CALENDAR_ID and GOOGLE_CREDENTIALS_PATH):
        logger.info("Google Calendar not configured or dependencies missing")
        return []

    tz = ZoneInfo(TIME_ZONE)
    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    )
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    start_dt = datetime.combine(start, datetime.min.time(), tz)
    end_dt = datetime.combine(end, datetime.max.time(), tz)
    items = (
        service.events()
        .list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )

    events: List[Event] = []
    for item in items:
        start_str = item.get("start", {}).get("dateTime") or item.get("start", {}).get(
            "date"
        )
        end_str = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date")
        if not (start_str and end_str):
            continue
        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(
            tz
        )
        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")).astimezone(tz)
        events.append(Event(item.get("summary", ""), start_dt, end_dt))
    return events


def load_events(start: date, end: date) -> List[Event]:
    """Return events between ``start`` and ``end`` inclusive."""
    logger.info("Loading events between %s and %s", start, end)
    events = [e for e in _read_ics_events() if start <= e.start.date() <= end]
    events.extend(_read_google_calendar_events(start, end))
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as handle:
        json.dump([asdict(e) for e in events], handle, default=str, ensure_ascii=False)
    logger.info("Cached %d events to %s", len(events), CACHE_PATH)
    return events
