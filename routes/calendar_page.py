"""Calendar page for viewing linked calendar events."""

# pylint: disable=duplicate-code

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from calendar_integration import load_events
from config import config, PROJECT_ROOT

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


@router.get("/calendar", response_class=HTMLResponse)
def calendar_page(request: Request):
    """Display events pulled from linked calendars."""
    logger.info("GET /calendar")
    start = date.today()
    end = start + timedelta(days=7)
    events = sorted(load_events(start, end), key=lambda e: e.start)
    return templates.TemplateResponse(
        "calendar.html", {"request": request, "events": events}
    )
