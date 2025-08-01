"""Calendar page for viewing cached events."""

# pylint: disable=duplicate-code

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import config, PROJECT_ROOT

CACHE_PATH = PROJECT_ROOT / "data/calendar_cache.json"

router = APIRouter()
templates = Jinja2Templates(directory=PROJECT_ROOT / "templates")

LOG_FILE = Path(config.LOG_DIR) / "calendar_page.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class Event:  # pylint: disable=too-few-public-methods
    """Simple container for calendar events."""

    def __init__(self, summary: str, start: datetime, end: datetime):
        self.summary = summary
        self.start = start
        self.end = end


def _read_cached_events() -> List[Event]:
    if not CACHE_PATH.exists():
        logger.info("%s does not exist", CACHE_PATH)
        return []
    with open(CACHE_PATH, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    events = []
    for item in data:
        try:
            start = datetime.fromisoformat(item["start"])
            end = datetime.fromisoformat(item["end"])
            events.append(Event(item.get("summary", ""), start, end))
        except Exception as exc:  # pragma: no cover - invalid data
            logger.warning("Failed parsing event %s: %s", item, exc)
    return events


@router.get("/calendar", response_class=HTMLResponse)
def calendar_page(request: Request):
    """Display events loaded from the calendar cache."""
    logger.info("GET /calendar")
    events = sorted(_read_cached_events(), key=lambda e: e.start)
    return templates.TemplateResponse(
        "calendar.html", {"request": request, "events": events}
    )
