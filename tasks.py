"""Utilities for reading saved task entries."""

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
        if not task.get("recurrence"):
            continue
        next_due = _next_due(task, today)
        task["next_due"] = next_due.isoformat()
        task["due_today"] = next_due <= today
    return tasks


def read_tasks(path: Path = TASKS_FILE) -> List[Dict]:
    """Return all task entries from the YAML file."""
    logger.info("Reading tasks from %s", path)
    if not path.exists():
        logger.info("%s does not exist", path)
        return []
    with open(path, "r", encoding="utf-8") as handle:
        tasks = yaml.safe_load(handle) or []
    logger.debug("Loaded %d tasks", len(tasks))
    return apply_recurrence(tasks)


def write_tasks(tasks: List[Dict], path: Path = TASKS_FILE) -> None:
    """Write tasks to a YAML file."""
    logger.info("Writing %d tasks to %s", len(tasks), path)
    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        yaml.dump(tasks, handle, sort_keys=False, allow_unicode=True)
