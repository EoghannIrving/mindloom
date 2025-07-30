"""Utilities for storing and applying the daily plan."""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict
import string

PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _clean(text: str) -> str:
    """Lowercase and remove punctuation from ``text``."""
    return text.translate(PUNCT_TABLE).lower()


from config import config, PROJECT_ROOT

PLAN_PATH = Path(getattr(config, "PLAN_PATH", PROJECT_ROOT / "data/morning_plan.txt"))
PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)


def read_plan(path: Path = PLAN_PATH) -> str:
    """Return the saved morning plan text if it exists."""
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def save_plan(text: str, path: Path = PLAN_PATH) -> None:
    """Persist the generated morning plan."""
    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def filter_tasks_by_plan(tasks: List[Dict], plan_text: str | None = None) -> List[Dict]:
    """Return only tasks whose titles appear in the plan text."""
    if not plan_text:
        return tasks
    plan_clean = _clean(plan_text)
    return [t for t in tasks if _clean(str(t.get("title", ""))) in plan_clean]
