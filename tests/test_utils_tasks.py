"""Unit tests for shared task helper utilities."""

from __future__ import annotations

from datetime import date, timedelta

from utils.tasks import (
    annotate_task,
    filter_tasks_by_metadata,
    matches_search_query,
    resolve_energy_cost,
    sort_tasks,
)


def _base_tasks():
    return [
        {"project": "Alpha", "area": "Personal", "status": "active"},
        {"project": "Beta", "area": "Work", "status": "complete"},
        {"project": "Alpha", "area": "Work", "status": "active"},
    ]


def test_filter_tasks_by_metadata_exact_match_and_exclude_completed():
    tasks = _base_tasks()
    filtered = filter_tasks_by_metadata(tasks, project="alpha")
    assert len(filtered) == 2
    assert all(task["project"] == "Alpha" for task in filtered)

    filtered = filter_tasks_by_metadata(tasks, project="alpha", exclude_completed=True)
    assert all(task["status"] != "complete" for task in filtered)


def test_filter_tasks_by_metadata_contains():
    tasks = [
        {"project": "Alpha Team", "area": "Personal", "status": "active"},
        {"project": "Beta", "area": "Work", "status": "active"},
    ]
    filtered = filter_tasks_by_metadata(tasks, project="alpha", project_contains=True)
    assert len(filtered) == 1
    assert filtered[0]["project"] == "Alpha Team"


def test_matches_search_query_true_and_false():
    task = {"title": "Write Report", "notes": "todo", "project": "Alpha"}
    assert matches_search_query(task, "report", ["title", "notes"]) is True
    assert matches_search_query(task, "missing", ["title"]) is False


def test_resolve_energy_cost_handles_defaults_and_strings():
    assert resolve_energy_cost({"energy_cost": "2"}) == 2
    assert resolve_energy_cost({"effort": "High"}) == 5


def test_annotate_task_and_sorting_modes():
    today = date(2025, 1, 5)
    tasks = [
        annotate_task(
            {"title": "Overdue", "due": "2025-01-03", "status": "active"}, today
        ),
        annotate_task(
            {"title": "Tomorrow", "due": "2025-01-06", "status": "active"}, today
        ),
        annotate_task(
            {"title": "Complete", "due": "2025-01-04", "status": "complete"}, today
        ),
    ]
    sorted_default = sort_tasks(tasks, mode="due_asc")
    assert [task["title"] for task in sorted_default] == [
        "Overdue",
        "Complete",
        "Tomorrow",
    ]
    sorted_overdue = sort_tasks(tasks, mode="overdue_first")
    assert sorted_overdue[0]["is_overdue"]
    sorted_status = sort_tasks(tasks, mode="status")
    assert [task["status"] for task in sorted_status][:2] == ["active", "active"]
