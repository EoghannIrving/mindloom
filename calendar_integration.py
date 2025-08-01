"""Utilities for loading calendar events from .ics files."""

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

CACHE_PATH = PROJECT_ROOT / "data/calendar_cache.json"
ICS_PATHS = [
    Path(p).expanduser()
    for p in os.getenv(
        "CALENDAR_ICS_PATH", str(PROJECT_ROOT / "data/calendar.ics")
    ).split(os.pathsep)
]
TIME_ZONE = os.getenv("TIME_ZONE", getattr(config, "TIME_ZONE", "UTC"))

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


def load_events(start: date, end: date) -> List[Event]:
    """Return events between ``start`` and ``end`` inclusive."""
    logger.info("Loading events between %s and %s", start, end)
    events = [e for e in _read_ics_events() if start <= e.start.date() <= end]
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as handle:
        json.dump([asdict(e) for e in events], handle, default=str, ensure_ascii=False)
    logger.info("Cached %d events to %s", len(events), CACHE_PATH)
    return events
