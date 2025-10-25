"""Tests for task sorting helpers."""

from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes.tasks_page import _annotate_task, _sort_tasks


def _build_task(
    task_id: int, due: str | None, status: str = "active", title: str = "Task"
) -> dict:
    return {"id": task_id, "due": due, "status": status, "title": f"{title} {task_id}"}


def test_overdue_first_sort_prioritises_overdue_then_due_dates():
    today = date(2024, 1, 10)
    tasks = [
        _build_task(1, "2024-01-09"),  # overdue
        _build_task(2, None),  # no due date
        _build_task(3, "2024-01-10"),  # due today
        _build_task(4, "2024-01-15"),  # future
        _build_task(5, "2023-12-31"),  # overdue, oldest
    ]

    annotated = [_annotate_task(dict(task), today) for task in tasks]

    ordered = _sort_tasks(annotated, "overdue_first")

    assert [task["id"] for task in ordered] == [5, 1, 3, 4, 2]


def test_due_ascending_sort_places_undated_tasks_last():
    today = date(2024, 1, 10)
    tasks = [
        _build_task(1, "2024-02-01"),
        _build_task(2, None),
        _build_task(3, "2024-01-05"),
    ]

    annotated = [_annotate_task(dict(task), today) for task in tasks]

    ordered = _sort_tasks(annotated, "due_asc")

    assert [task["id"] for task in ordered] == [3, 1, 2]


def test_status_sort_orders_status_then_due_then_title():
    today = date(2024, 1, 10)
    tasks = [
        _build_task(1, "2024-01-13", status="blocked", title="Blocked Later"),
        _build_task(2, "2024-01-12", status="active", title="Active Gamma"),
        _build_task(3, "2024-01-10", status="active", title="Active Alpha"),
        _build_task(4, "2024-01-10", status="active", title="Active Beta"),
        _build_task(5, None, status="complete", title="Complete No Due"),
        _build_task(6, "2024-01-11", status="blocked", title="Blocked First"),
        _build_task(7, "2024-01-09", status="complete", title="Complete Due"),
    ]

    annotated = [_annotate_task(dict(task), today) for task in tasks]

    ordered = _sort_tasks(annotated, "status")

    assert [task["id"] for task in ordered] == [3, 4, 2, 6, 1, 7, 5]

    active = [task for task in ordered if task["status"] == "active"]
    assert [task["due_date_normalized"] for task in active] == [
        "2024-01-10",
        "2024-01-10",
        "2024-01-12",
    ]
    assert [task["title"] for task in active[:2]] == ["Active Alpha 3", "Active Beta 4"]

    blocked = [task for task in ordered if task["status"] == "blocked"]
    assert [task["due_date_normalized"] for task in blocked] == [
        "2024-01-11",
        "2024-01-13",
    ]

    complete = [task for task in ordered if task["status"] == "complete"]
    assert [task["due_date_normalized"] for task in complete] == [
        "2024-01-09",
        None,
    ]
