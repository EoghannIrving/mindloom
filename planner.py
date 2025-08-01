"""Utilities for storing and applying the daily plan."""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict
import re
import string
from config import config, PROJECT_ROOT

PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _clean(text: str) -> str:
    """Lowercase and remove punctuation from ``text``."""
    return text.translate(PUNCT_TABLE).lower()


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


def parse_plan_reasons(plan_text: str) -> Dict[str, str]:
    """Return a mapping of cleaned task titles to GPT-provided reasons."""
    reasons: Dict[str, str] = {}
    pattern = re.compile(
        r"^\s*(?:\d+[.)]?|[-*\u2022])\s*(.+?)(?:(?:\s+[-\u2013\u2014]|:)\s*(.+))?$"
    )
    bullet_only = re.compile(r"^\s*[-*\u2022]\s*(.+)")
    split_pattern = re.compile(r"^(.+?)(?:(?:\s+[-\u2013\u2014]|:)\s*(.+))?$")
    last_title: str | None = None
    last_was_number = False
    previous_blank = False
    for line in plan_text.splitlines():
        line = line.strip()
        if not line:
            previous_blank = True
            continue
        bullet_match = bullet_only.match(line)
        if bullet_match:
            bullet_text = bullet_match.group(1).strip()
            m = split_pattern.match(bullet_text)
            if last_title and last_was_number and not (m and m.group(2)):
                if not reasons.get(last_title):
                    reasons[last_title] = bullet_text
                last_was_number = False
                continue
            if m:
                title = m.group(1).strip()
                reason = (m.group(2) or "").strip()
                title = re.sub(r"\([^\)]*\)\s*$", "", title).strip()
                last_title = _clean(title)
                reasons[last_title] = reason
                last_was_number = False
                continue
        match = pattern.match(line)
        if not match:
            if last_title and not reasons.get(last_title) and not previous_blank:
                reasons[last_title] = line
            else:
                last_title = _clean(line)
                reasons[last_title] = ""
            last_was_number = False
            previous_blank = False
            continue
        is_number = line.lstrip()[0].isdigit()
        title = match.group(1).strip()
        reason = (match.group(2) or "").strip()
        # handle cases like "Task (meta: value)" where the colon splits the regex
        if title.count("(") > title.count(")") and ")" in reason:
            split = reason.index(")")
            title = f"{title} {reason[: split + 1]}".strip()
            reason = reason[split + 1 :].strip()
        # remove trailing parenthetical metadata e.g. "(effort: high)"
        title = re.sub(r"\([^\)]*\)\s*$", "", title).strip()
        if not is_number and last_title and not reason:
            if not reasons.get(last_title):
                reasons[last_title] = title
            continue
        last_title = _clean(title)
        reasons[last_title] = reason
        last_was_number = is_number
        previous_blank = False
    return reasons


def filter_tasks_by_energy(tasks: List[Dict], energy: int | None) -> List[Dict]:
    """Return tasks whose ``energy_cost`` is within the available ``energy``."""
    if energy is None:
        return tasks
    filtered: List[Dict] = []
    for task in tasks:
        cost = task.get("energy_cost")
        try:
            cost_val = int(cost)
        except (TypeError, ValueError):
            filtered.append(task)
            continue
        if cost_val <= energy:
            filtered.append(task)
    return filtered
