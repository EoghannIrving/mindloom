"""Unit tests for the tasks utilities."""

from __future__ import annotations

import sys
from pathlib import Path

# pylint: disable=wrong-import-position, import-outside-toplevel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import date, timedelta

from tasks import (
    write_tasks,
    read_tasks,
    mark_tasks_complete,
    due_within,
    upcoming_tasks,
)


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


def test_mark_tasks_complete(tmp_path: Path):
    """mark_tasks_complete should update status and last_completed."""
    path = tmp_path / "tasks.yaml"
    tasks = [{"id": 1, "title": "demo", "status": "active"}]
    write_tasks(tasks, path)
    count = mark_tasks_complete([1], path)
    updated = read_tasks(path)
    assert count == 1
    assert updated[0]["status"] == "complete"
    assert updated[0]["last_completed"] == date.today().isoformat()


def test_mark_recurring_task_updates_due(tmp_path: Path):
    """Completing a recurring task should advance its due date."""
    path = tmp_path / "tasks.yaml"
    today = date.today()
    tasks = [
        {
            "id": 1,
            "title": "habit",
            "status": "active",
            "recurrence": "daily",
            "due": today.isoformat(),
        }
    ]
    write_tasks(tasks, path)
    mark_tasks_complete([1], path)
    updated = read_tasks(path)
    expected_due = (today + timedelta(days=1)).isoformat()
    assert updated[0]["due"] == expected_due
    assert updated[0]["next_due"] == expected_due


def test_due_date_flag(tmp_path: Path):
    """Tasks with a due date should set due_today accordingly."""
    target = tmp_path / "tasks.yaml"
    today = date.today().isoformat()
    tasks = [{"title": "deadline", "due": today}]
    write_tasks(tasks, target)
    result = read_tasks(target)
    assert result[0]["due_today"] is True


def test_due_within(tmp_path: Path):
    """due_within should filter tasks by upcoming deadlines."""
    target = tmp_path / "tasks.yaml"
    today = date.today()
    tasks = [
        {"title": "overdue", "due": (today - timedelta(days=1)).isoformat()},
        {"title": "soon", "due": (today + timedelta(days=6)).isoformat()},
        {"title": "later", "due": (today + timedelta(days=8)).isoformat()},
        {"title": "nodate"},
    ]
    write_tasks(tasks, target)
    items = read_tasks(target)
    result = due_within(items, days=7, today=today)
    titles = [t["title"] for t in result]
    assert "overdue" in titles
    assert "soon" in titles
    assert "later" not in titles
    assert "nodate" not in titles


def test_upcoming_tasks(tmp_path: Path):
    """upcoming_tasks should return overdue or soon items only."""
    target = tmp_path / "tasks.yaml"
    today = date.today()
    tasks = [
        {"id": 1, "title": "overdue", "due": (today - timedelta(days=1)).isoformat()},
        {"id": 2, "title": "soon", "due": (today + timedelta(days=3)).isoformat()},
        {"id": 3, "title": "later", "due": (today + timedelta(days=10)).isoformat()},
    ]
    write_tasks(tasks, target)
    result = upcoming_tasks(target, days=7, today=today)
    titles = [t["title"] for t in result]
    assert "overdue" in titles
    assert "soon" in titles
    assert "later" not in titles
