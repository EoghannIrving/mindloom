"""Unit tests for the tasks utilities."""

from __future__ import annotations

import sys
from pathlib import Path

# pylint: disable=wrong-import-position, import-outside-toplevel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import date, timedelta

from tasks import write_tasks, read_tasks


def test_write_tasks_creates_parent(tmp_path: Path):
    """write_tasks should create missing parent directories."""
    target = tmp_path / "sub" / "tasks.yaml"
    data = [{"title": "demo"}]
    write_tasks(data, target)
    assert target.exists()
    saved = read_tasks(target)
    assert saved[0]["title"] == "demo"


def test_recurring_task_due_today(tmp_path: Path):
    """read_tasks should compute next_due and due_today."""
    target = tmp_path / "tasks.yaml"
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tasks = [{"title": "habit", "recurrence": "daily", "last_completed": yesterday}]
    write_tasks(tasks, target)
    result = read_tasks(target)
    assert result[0]["due_today"] is True
    assert result[0]["next_due"] == date.today().isoformat()


def test_recurring_task_future_due(tmp_path: Path):
    """Tasks not yet due should return due_today False."""
    target = tmp_path / "tasks.yaml"
    today = date.today().isoformat()
    tasks = [{"title": "weekly", "recurrence": "weekly", "last_completed": today}]
    write_tasks(tasks, target)
    result = read_tasks(target)
    assert result[0]["due_today"] is False
    assert result[0]["next_due"] != today
