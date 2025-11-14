"""Tests for the daily tasks collection helper."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes.tasks_page import _collect_due_tasks


def test_collect_due_tasks_includes_overdue_items():
    today = date(2024, 2, 12)
    tasks = [
        {"id": 1, "title": "Due today", "due": "2024-02-12", "status": "active"},
        {"id": 2, "title": "Overdue work", "due": "2024-02-10", "status": "active"},
        {"id": 3, "title": "Future work", "due": "2024-02-19", "status": "active"},
        {
            "id": 4,
            "title": "Complete overdue",
            "due": "2024-02-09",
            "status": "complete",
        },
    ]
    reasons = {
        "due today": "Recommended for today",
        "overdue work": "Falls behind schedule",
    }

    due_tasks = _collect_due_tasks(tasks, today, reasons)

    assert {task["title"] for task in due_tasks} == {"Due today", "Overdue work"}
    due_today = next(task for task in due_tasks if task["title"] == "Due today")
    assert due_today["due_date_normalized"] == "2024-02-12"
    assert due_today["reason"] == "Recommended for today"
    overdue = next(task for task in due_tasks if task["title"] == "Overdue work")
    assert overdue["reason"] == "Falls behind schedule"
