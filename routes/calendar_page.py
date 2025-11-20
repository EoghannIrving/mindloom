"""Calendar page for viewing linked calendar events."""

# pylint: disable=duplicate-code

from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from calendar_integration import Event, load_events
from config import config
from utils.logging import configure_logger
from utils.tasks import resolve_energy_cost, task_due_date
from tasks import mark_tasks_complete, read_tasks

from utils.template_helpers import create_templates
from utils.auth import enforce_api_key


router = APIRouter()
templates = create_templates()

LOG_FILE = Path(config.LOG_DIR) / "calendar_page.log"
logger = configure_logger(__name__, LOG_FILE)

CACHE_REFRESH_INTERVAL_SECONDS = max(
    60, int(os.getenv("CALENDAR_CACHE_REFRESH_INTERVAL_SECONDS", "300"))
)
CACHE_REFRESH_RANGE_DAYS = max(
    1, int(os.getenv("CALENDAR_CACHE_REFRESH_RANGE_DAYS", "7"))
)


async def _calendar_cache_refresher() -> None:
    """Keep the calendar cache warm so the UI stays snappy."""

    while True:
        start = date.today()
        end = start + timedelta(days=CACHE_REFRESH_RANGE_DAYS - 1)
        try:
            await asyncio.to_thread(load_events, start, end)
        except Exception:
            logger.exception("Background calendar cache refresh failed")
        await asyncio.sleep(CACHE_REFRESH_INTERVAL_SECONDS)


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


def _assign_event_lanes(
    events: Iterable[Event],
) -> tuple[list[dict], int, datetime | None, datetime | None]:
    """Assign horizontal "lanes" for overlapping timed events."""

    sorted_events = sorted(events, key=lambda item: item.start)
    if not sorted_events:
        return [], 0, None, None

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
    timeline_start: datetime | None = None
    timeline_end: datetime | None = None
    if sorted_events:
        timeline_start = sorted_events[0].start
        timeline_end = max(item.end for item in sorted_events)
    timed_events: list[dict] = []
    for event, lane_index in assignments:
        overlaps = any(
            other is not event and _events_overlap(event, other)
            for other in sorted_events
        )
        start_pct = 0.0
        duration_pct = 100.0
        if timeline_start and timeline_end:
            timeline_range_minutes = max(
                1.0, (timeline_end - timeline_start).total_seconds() / 60
            )
            offset_minutes = max(
                0.0, (event.start - timeline_start).total_seconds() / 60
            )
            duration_minutes = max(1.0, (event.end - event.start).total_seconds() / 60)
            start_pct = min(
                100.0, max(0.0, offset_minutes / timeline_range_minutes * 100)
            )
            duration_pct = min(
                100.0 - start_pct,
                max(0.5, duration_minutes / timeline_range_minutes * 100),
            )
        timed_events.append(
            {
                "summary": event.summary,
                "start": event.start,
                "end": event.end,
                "lane_index": lane_index,
                "total_lanes": total_lanes,
                "overlaps": overlaps,
                "start_pct": start_pct,
                "duration_pct": duration_pct,
            }
        )
    return timed_events, total_lanes, timeline_start, timeline_end


def _serialize_due_task(task: dict, due_date: date | None, is_overdue: bool) -> dict:
    """Return the subset of task fields the calendar template needs."""

    try:
        task_id = int(task.get("id"))
    except (TypeError, ValueError):
        task_id = None
    return {
        "title": str(task.get("title") or "Task"),
        "project": str(task.get("project") or ""),
        "energy_cost": resolve_energy_cost(task),
        "id": task_id,
        "due_date": due_date,
        "is_overdue": is_overdue,
    }


def _parse_iso_date(value: str | None) -> date | None:
    """Parse ISO date strings coming from the client."""

    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_start_date(value: str | None) -> date | None:
    """Return a parsed ISO date or ``None`` if invalid."""

    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_range_days(value: str | None, default: int = 7, max_value: int = 30) -> int:
    """Clamp the requested range to a sensible window."""

    try:
        requested = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(requested, max_value))


def _bool_query_flag(params, key: str, default: bool) -> bool:
    """Interpret GET flags that use ``1``/``0`` values."""

    raw = params.get(key)
    if raw is None:
        return default
    return raw == "1"


@router.get("/calendar", response_class=HTMLResponse)
def calendar_page(request: Request):
    """Display events pulled from linked calendars."""

    logger.info("GET /calendar")
    query_params = request.query_params
    today = date.today()
    client_today = _parse_iso_date(query_params.get("today"))
    effective_today = client_today or today
    start = _parse_start_date(query_params.get("start_date")) or effective_today
    range_days = _parse_range_days(query_params.get("range"))
    end = start + timedelta(days=range_days - 1)
    events = sorted(load_events(start, end), key=lambda e: (e.start.date(), e.start))

    events_by_date: dict[date, list[Event]] = defaultdict(list)
    for event in events:
        events_by_date[event.start.date()].append(event)

    tasks = read_tasks()
    tasks_by_date: dict[date, list[dict]] = defaultdict(list)
    overdue_tasks: list[tuple[dict, date]] = []
    for task in tasks:
        if str(task.get("status", "")).lower() == "complete":
            continue
        due_date = task_due_date(task)
        if due_date:
            tasks_by_date[due_date].append(task)
            if due_date < effective_today:
                overdue_tasks.append((task, due_date))

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

        timed_events, peak_overlap, _, _ = _assign_event_lanes(timed_candidates)
        due_tasks = [
            _serialize_due_task(task, current_day, current_day < effective_today)
            for task in tasks_by_date.get(current_day, [])
        ]
        if current_day == effective_today:
            due_tasks.extend(
                _serialize_due_task(task, due_date, True)
                for task, due_date in overdue_tasks
            )
        due_tasks.sort(
            key=lambda item: (
                not item["is_overdue"],
                item["due_date"] or date.max,
            )
        )
        energy_total = sum(
            task["energy_cost"]
            for task in due_tasks
            if task.get("energy_cost") is not None
        )
        overdue_count = sum(1 for task in due_tasks if task.get("is_overdue"))
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
                "energy_total": energy_total,
                "overdue_count": overdue_count,
            }
        )
        current_day += timedelta(days=1)

    show_all_day = _bool_query_flag(query_params, "show_all_day", True)
    show_timed = _bool_query_flag(query_params, "show_timed", True)
    show_tasks = _bool_query_flag(query_params, "show_tasks", True)
    focus_overlaps = _bool_query_flag(query_params, "focus_overlaps", False)
    focus_tasks_due = _bool_query_flag(query_params, "focus_tasks_due", False)

    display_days = calendar_days
    if focus_overlaps:
        display_days = [day for day in display_days if day["peak_overlap"] > 1]
    if focus_tasks_due:
        display_days = [day for day in display_days if day["tasks_due"]]

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
    applied_range_days = range_days

    return templates.TemplateResponse(
        "calendar.html",
        {
            "request": request,
            "start_date": start,
            "end_date": end,
            "events": events,
            "calendar_days": calendar_days,
            "display_days": display_days,
            "total_events": total_events,
            "busiest_day": busiest_day,
            "next_event": next_event,
            "range_days": range_days,
            "show_all_day": show_all_day,
            "show_timed": show_timed,
            "show_tasks": show_tasks,
            "focus_overlaps": focus_overlaps,
            "focus_tasks_due": focus_tasks_due,
            "today": effective_today,
            "today_iso": effective_today.isoformat(),
        },
    )


@router.post("/calendar/tasks/complete")
def complete_calendar_task(
    task_id: int = Form(...),
    start_date: str | None = Form(None),
    range_days: str | None = Form(None),
    show_all_day: str = Form("1"),
    show_timed: str = Form("1"),
    show_tasks: str = Form("1"),
    focus_overlaps: str = Form("0"),
    focus_tasks_due: str = Form("0"),
    _: None = Depends(enforce_api_key),
):
    mark_tasks_complete([task_id])
    params = {
        "start_date": start_date,
        "range": range_days,
        "show_all_day": show_all_day,
        "show_timed": show_timed,
        "show_tasks": show_tasks,
        "focus_overlaps": focus_overlaps,
        "focus_tasks_due": focus_tasks_due,
    }
    query = urlencode({k: v for k, v in params.items() if v not in (None, "")})
    url = "/calendar"
    if query:
        url = f"{url}?{query}"
    return RedirectResponse(url, status_code=303)


@router.post("/calendar/tasks/complete-ajax")
def complete_calendar_task_ajax(
    task_id: int = Form(...), _: None = Depends(enforce_api_key)
):
    """Mark a single calendar task complete, returning a simple JSON payload."""

    updated = mark_tasks_complete([task_id])
    return {"completed": updated}


@router.on_event("startup")
async def _launch_calendar_cache_refresher() -> None:
    """Ensure a background task keeps the calendar cache fresh."""

    logger.info(
        "Starting calendar cache refresher (every %s seconds)",
        CACHE_REFRESH_INTERVAL_SECONDS,
    )
    asyncio.create_task(_calendar_cache_refresher())
