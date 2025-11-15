"""Calendar page for viewing linked calendar events."""

# pylint: disable=duplicate-code

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from calendar_integration import Event, load_events
from config import config, PROJECT_ROOT
from utils.logging import configure_logger
from utils.tasks import resolve_energy_cost, task_due_date
from tasks import read_tasks

router = APIRouter()
templates = Jinja2Templates(directory=PROJECT_ROOT / "templates")

LOG_FILE = Path(config.LOG_DIR) / "calendar_page.log"
logger = configure_logger(__name__, LOG_FILE)


def _is_all_day_event(event: Event) -> bool:
    """Detect whether the event spans a full day without specific time."""

    duration = event.end - event.start
    return (
        event.start.time() == time.min
        and event.end.time() == time.min
        and duration >= timedelta(hours=23, minutes=30)
    )


def _events_overlap(event: Event, candidate: Event) -> bool:
    """Return ``True`` if two events share at least one moment."""

    return event.start < candidate.end and candidate.start < event.end


def _assign_event_lanes(events: Iterable[Event]) -> tuple[list[dict], int]:
    """Assign horizontal "lanes" for overlapping timed events."""

    sorted_events = sorted(events, key=lambda item: item.start)
    if not sorted_events:
        return [], 0

    lanes_end: list[datetime] = []
    assignments: list[tuple[Event, int]] = []
    for event in sorted_events:
        lane_index: int | None = None
        for idx, lane_end in enumerate(lanes_end):
            if event.start >= lane_end:
                lane_index = idx
                lanes_end[idx] = event.end
                break
        if lane_index is None:
            lane_index = len(lanes_end)
            lanes_end.append(event.end)
        assignments.append((event, lane_index))

    total_lanes = len(lanes_end)
    timed_events: list[dict] = []
    for event, lane_index in assignments:
        overlaps = any(
            other is not event and _events_overlap(event, other)
            for other in sorted_events
        )
        timed_events.append(
            {
                "summary": event.summary,
                "start": event.start,
                "end": event.end,
                "lane_index": lane_index,
                "total_lanes": total_lanes,
                "overlaps": overlaps,
            }
        )
    return timed_events, total_lanes


@router.get("/calendar", response_class=HTMLResponse)
def calendar_page(request: Request):
    """Display events pulled from linked calendars."""

    logger.info("GET /calendar")
    start = date.today()
    end = start + timedelta(days=7)
    events = sorted(load_events(start, end), key=lambda e: (e.start.date(), e.start))

    events_by_date: dict[date, list[Event]] = defaultdict(list)
    for event in events:
        events_by_date[event.start.date()].append(event)

    tasks = read_tasks()
    tasks_by_date: dict[date, list[dict]] = defaultdict(list)
    for task in tasks:
        if str(task.get("status", "")).lower() == "complete":
            continue
        due_date = task_due_date(task)
        if due_date:
            tasks_by_date[due_date].append(task)

    calendar_days: list[dict] = []
    current_day = start
    while current_day <= end:
        day_events = events_by_date.get(current_day, [])
        all_day_events: list[dict] = []
        timed_candidates: list[Event] = []
        for event in day_events:
            if _is_all_day_event(event):
                duration_days = max(1, (event.end.date() - event.start.date()).days)
                all_day_events.append(
                    {"summary": event.summary, "duration_days": duration_days}
                )
            else:
                timed_candidates.append(event)

        timed_events, peak_overlap = _assign_event_lanes(timed_candidates)
        due_tasks = [
            {
                "title": str(task.get("title") or "Task"),
                "project": str(task.get("project") or ""),
                "energy_cost": resolve_energy_cost(task),
            }
            for task in tasks_by_date.get(current_day, [])
        ]
        calendar_days.append(
            {
                "date": current_day,
                "count": len(day_events),
                "all_day_events": all_day_events,
                "timed_events": timed_events,
                "has_overlaps": peak_overlap > 1,
                "peak_overlap": peak_overlap,
                "tasks_due": due_tasks,
                "tasks_total": len(due_tasks),
            }
        )
        current_day += timedelta(days=1)

    busiest_day: dict | None = None
    if events_by_date:
        busiest_date, busiest_events = max(
            events_by_date.items(),
            key=lambda item: (
                len(item[1]),
                -item[0].toordinal(),
            ),
        )
        busiest_day = {"date": busiest_date, "count": len(busiest_events)}

    next_event = events[0] if events else None
    total_events = len(events)
    range_days = (end - start).days + 1

    return templates.TemplateResponse(
        "calendar.html",
        {
            "request": request,
            "start_date": start,
            "end_date": end,
            "events": events,
            "calendar_days": calendar_days,
            "total_events": total_events,
            "busiest_day": busiest_day,
            "next_event": next_event,
            "range_days": range_days,
        },
    )
