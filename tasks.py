"""Utilities for reading saved task entries."""

# pylint: disable=duplicate-code

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import List, Dict

import yaml

from config import config

TASKS_FILE = Path(config.TASKS_PATH)
TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)

LOG_FILE = Path(config.LOG_DIR) / "tasks.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


RECURRENCE_DAYS = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "yearly": 365,
}


def _next_due(task: Dict, today: date) -> date:
    """Return the next due date for a recurring task."""
    base = today
    if task.get("last_completed"):
        base = date.fromisoformat(str(task["last_completed"]))
    elif task.get("due"):
        base = date.fromisoformat(str(task["due"]))

    days = RECURRENCE_DAYS.get(str(task.get("recurrence", "")).lower())
    return base + timedelta(days=days) if days else base


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
    today = date.today().isoformat()
    count = 0
    for task in tasks:
        if task.get("id") in task_ids:
            task["status"] = "complete"
            task["last_completed"] = today
            count += 1
        task.pop("next_due", None)
        task.pop("due_today", None)
    write_tasks(tasks, path)
    logger.info("Updated %d tasks", count)
    return count


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
