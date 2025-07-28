"""Utilities for reading saved task entries."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Dict

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


def parse_todo_line(line: str) -> Dict:
    """Convert a single todo.txt line into a task dictionary."""
    tokens = line.strip().split()
    task: Dict[str, str | int] = {"title": ""}
    title_parts: List[str] = []
    for token in tokens:
        if token.startswith("path:"):
            task["path"] = token.split(":", 1)[1]
        elif token.startswith("area:"):
            task["area"] = token.split(":", 1)[1]
        elif token.startswith("effort:"):
            task["effort"] = token.split(":", 1)[1]
        elif token.startswith("status:"):
            task["status"] = token.split(":", 1)[1]
        elif token.startswith("energy:"):
            task["energy_cost"] = int(token.split(":", 1)[1])
        elif token.startswith("last_reviewed:"):
            task["last_reviewed"] = token.split(":", 1)[1]
        else:
            title_parts.append(token)
    task["title"] = " ".join(title_parts)
    task.setdefault("type", "project")
    task.setdefault("source", "summary")
    return task


def read_tasks(path: Path = TASKS_FILE) -> List[Dict]:
    """Return all task entries from the todo.txt file."""
    logger.info("Reading tasks from %s", path)
    if not path.exists():
        logger.info("%s does not exist", path)
        return []
    with open(path, "r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip()]
    tasks = [parse_todo_line(line) for line in lines]
    logger.debug("Loaded %d tasks", len(tasks))
    return tasks
