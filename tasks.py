"""Utilities for reading saved task entries."""

# pylint: disable=duplicate-code

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List

from dateutil.relativedelta import relativedelta

import yaml

from config import config
from utils.tasks import resolve_energy_cost

TASKS_FILE = Path(config.TASKS_PATH)
TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)

LOG_FILE = Path(config.LOG_DIR) / "tasks.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
COMPLETION_LOG_PATH = Path(config.TASK_COMPLETIONS_PATH)

logger = logging.getLogger(__name__)
if not logger.handlers:
    try:
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    except PermissionError:
        handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


RECURRENCE_DAYS = {
    "daily": 1,
    "weekly": 7,
    "bi-weekly": 14,
    "monthly": 30,
    "quarterly": 91,
    "bi-annual": 182,
    "yearly": 365,
}

CALENDAR_RECURRENCE_DELTAS = {
    "monthly": relativedelta(months=1),
    "quarterly": relativedelta(months=3),
    "bi-annual": relativedelta(months=6),
    "yearly": relativedelta(years=1),
}


def _advance_for_recurrence(base: date, recurrence: str) -> date | None:
    if not base:
        return None
    key = str(recurrence or "").lower()
    if not key:
        return None

    calendar_delta = CALENDAR_RECURRENCE_DELTAS.get(key)
    if calendar_delta:
        return base + calendar_delta

    days = RECURRENCE_DAYS.get(key)
    if days:
        return base + timedelta(days=days)

    return None


def _next_due(task: Dict, today: date) -> date:
    """Return the next due date for a recurring task."""
    recurrence = str(task.get("recurrence", "")).lower()
    if not recurrence:
        return today

    def _parse_date(value: str | date | None) -> date | None:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    due_date = _parse_date(task.get("due"))
    last_completed_date = _parse_date(task.get("last_completed"))

    recurrence_date = _advance_for_recurrence(last_completed_date or today, recurrence)
    if due_date and (not last_completed_date or due_date > last_completed_date):
        # Respect a manually entered due date for the current cycle.
        return due_date

    return recurrence_date or today


def complete_task(task: Dict, today: date | None = None) -> None:
    """Mark a single task as complete and advance recurring due dates."""
    today_date = today or date.today()
    iso_today = today_date.isoformat()
    task["last_completed"] = iso_today
    record_task_completion(task, completed_at=iso_today)
    if task.get("recurrence"):
        task["status"] = "active"
        next_due = _next_due(task, today_date)
        task["due"] = next_due.isoformat()
    else:
        task["status"] = "complete"


def apply_recurrence(tasks: List[Dict], today: date | None = None) -> List[Dict]:
    """Update tasks with next due dates and due_today flag."""
    today = today or date.today()
    for task in tasks:
        if task.get("recurrence"):
            next_due = _next_due(task, today)
            task["next_due"] = next_due.isoformat()
            task["due_today"] = next_due <= today
        elif task.get("due"):
            due_date = date.fromisoformat(str(task["due"]))
            task["due_today"] = due_date <= today
        else:
            task["due_today"] = False
    return tasks


def read_tasks_raw(path: Path = TASKS_FILE, *, log: bool = True) -> List[Dict]:
    """Return task entries from YAML without recurrence annotations."""
    if log:
        logger.info("Reading tasks (raw) from %s", path)
    if not path.exists():
        logger.info("%s does not exist", path)
        return []
    with open(path, "r", encoding="utf-8") as handle:
        tasks = yaml.safe_load(handle) or []
    logger.debug("Loaded %d raw tasks", len(tasks))
    return tasks


def read_tasks(path: Path = TASKS_FILE) -> List[Dict]:
    """Return all task entries from the YAML file."""
    logger.info("Reading tasks from %s", path)
    tasks = read_tasks_raw(path, log=False)
    return apply_recurrence(tasks)


def write_tasks(tasks: List[Dict], path: Path = TASKS_FILE) -> None:
    """Write tasks to a YAML file."""
    logger.info("Writing %d tasks to %s", len(tasks), path)
    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        yaml.dump(tasks, handle, sort_keys=False, allow_unicode=True)


def mark_tasks_complete(task_ids: List[int], path: Path = TASKS_FILE) -> int:
    """Set selected task ids to complete and update ``last_completed``."""
    logger.info("Marking %d tasks complete", len(task_ids))
    if task_ids:
        logger.debug("Task ids to complete: %s", task_ids)
    tasks = read_tasks(path)
    today_date = date.today()
    today = today_date.isoformat()
    count = 0
    for task in tasks:
        if task.get("id") in task_ids:
            complete_task(task, today_date)
            count += 1
        task.pop("next_due", None)
        task.pop("due_today", None)
    write_tasks(tasks, path)
    logger.info("Updated %d tasks", count)
    return count


def _normalize_completion_timestamp(value: date | str | None) -> str | None:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    return None


def read_task_completions(path: Path | None = None) -> List[Dict]:
    target = path or COMPLETION_LOG_PATH
    if not target.exists():
        return []
    with open(target, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or []
    if isinstance(data, list):
        return data
    return []


def _write_task_completions(entries: List[Dict], path: Path | None = None) -> None:
    target = path or COMPLETION_LOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        yaml.dump(entries, handle, sort_keys=False, allow_unicode=True)


def record_task_completion(
    task: Dict,
    *,
    completed_at: str | date | None = None,
    path: Path | None = None,
) -> None:
    timestamp = _normalize_completion_timestamp(
        completed_at or task.get("last_completed")
    )
    if not timestamp:
        return
    entry = {
        "task_id": task.get("id"),
        "title": str(task.get("title") or "Task"),
        "project": str(task.get("project") or ""),
        "area": str(task.get("area") or ""),
        "due": str(task.get("due") or ""),
        "completed_at": timestamp,
        "energy_cost": resolve_energy_cost(task),
    }
    entries = read_task_completions(path=path)
    seen = {(item.get("task_id"), item.get("completed_at")) for item in entries}
    key = (entry["task_id"], entry["completed_at"])
    if key in seen:
        return
    entries.append(entry)
    _write_task_completions(entries, path=path)


def task_completion_history(
    tasks_list: List[Dict] | None = None, path: Path | None = None
) -> List[Dict]:
    history = read_task_completions(path=path)
    seen = {(item.get("task_id"), item.get("completed_at")) for item in history}
    tasks_candidate = tasks_list or read_tasks()
    for task in tasks_candidate:
        last_completed = task.get("last_completed")
        if not last_completed:
            continue
        key = (task.get("id"), str(last_completed))
        if key in seen:
            continue
        history.append(
            {
                "task_id": task.get("id"),
                "title": str(task.get("title") or "Task"),
                "project": str(task.get("project") or ""),
                "area": str(task.get("area") or ""),
                "due": str(task.get("due") or ""),
                "completed_at": str(last_completed),
                "energy_cost": resolve_energy_cost(task),
            }
        )
        seen.add(key)
    return history


def due_within(
    tasks: List[Dict], days: int = 7, today: date | None = None
) -> List[Dict]:
    """Return tasks overdue or due within ``days`` from ``today``."""
    today = today or date.today()
    limit = today + timedelta(days=days)
    results = []
    for task in tasks:
        date_str = task.get("next_due") or task.get("due")
        if not date_str:
            continue
        try:
            due_date = date.fromisoformat(str(date_str))
        except ValueError:
            continue
        if due_date <= limit:
            results.append(task)
    return results


def upcoming_tasks(
    path: Path = TASKS_FILE,
    days: int = 7,
    today: date | None = None,
) -> List[Dict]:
    """Return incomplete tasks overdue or due soon."""
    today = today or date.today()
    logger.info(
        "Fetching upcoming tasks from %s within %d days (today=%s)",
        path,
        days,
        today,
    )
    all_tasks = read_tasks(path)
    tasks = [t for t in all_tasks if t.get("status") != "complete"]
    logger.debug("Found %d incomplete tasks", len(tasks))
    results = due_within(tasks, days=days, today=today)
    logger.debug("%d tasks due within %d days", len(results), days)
    return results
