"""Regression tests for managing tasks with filters."""

import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import yaml
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app
import routes.tasks_page as tasks_page


def test_save_tasks_redirect_preserves_filters(monkeypatch: pytest.MonkeyPatch):
    """Submitting the manage tasks form keeps the existing filters."""

    initial_tasks = [{"id": 1, "title": "Demo task", "status": "active"}]

    monkeypatch.setattr(tasks_page, "read_tasks", lambda: [dict(initial_tasks[0])])

    written: dict[str, list] = {}

    def fake_write_tasks(data: list[dict]) -> None:
        written["tasks"] = data

    monkeypatch.setattr(tasks_page, "write_tasks", fake_write_tasks)

    client = TestClient(app)
    response = client.post(
        "/manage-tasks",
        data={
            "title-1": "Demo task",
            "status-1": "complete",
            "q": "deep work",
            "status": "active",
            "project": "Project Mercury",
            "area": "Focus",
            "type": "research",
            "sort": "due_asc",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    parsed = urlparse(response.headers["location"])
    assert parsed.path == "/manage-tasks"
    params = parse_qs(parsed.query)
    assert params == {
        "q": ["deep work"],
        "status": ["active"],
        "project": ["Project Mercury"],
        "area": ["Focus"],
        "type": ["research"],
        "sort": ["due_asc"],
    }

    assert "tasks" in written
    assert written["tasks"][0]["status"] == "complete"


def test_manage_tasks_default_hides_complete_tasks(monkeypatch: pytest.MonkeyPatch):
    """Without an explicit status filter completed tasks are hidden."""

    demo_tasks = [
        {"id": 1, "title": "Active item", "status": "active"},
        {"id": 2, "title": "Completed item", "status": "complete"},
    ]

    monkeypatch.setattr(
        tasks_page, "read_tasks", lambda: [dict(task) for task in demo_tasks]
    )

    client = TestClient(app)
    response = client.get("/manage-tasks")

    assert response.status_code == 200
    body = response.text
    assert "Active item" in body
    assert "Completed item" not in body


def test_manage_tasks_defaults_to_due_date_sort(monkeypatch: pytest.MonkeyPatch):
    """The default sort orders tasks by due date ascending and marks the option selected."""

    demo_tasks = [
        {"id": 1, "title": "Later", "status": "active", "due": "2024-07-01"},
        {"id": 2, "title": "Soon", "status": "active", "due": "2024-05-01"},
        {"id": 3, "title": "Someday", "status": "active", "due": None},
    ]

    monkeypatch.setattr(
        tasks_page, "read_tasks", lambda: [dict(task) for task in demo_tasks]
    )

    client = TestClient(app)
    response = client.get("/manage-tasks")

    assert response.status_code == 200
    body = response.text

    # Due date ascending: Soon, Later, Someday (no due date last)
    positions = [body.index(title) for title in ("Soon", "Later", "Someday")]
    assert positions == sorted(positions)

    match = re.search(r'<option value="due_asc"[^>]*selected', body)
    assert match, "Expected due_asc option to be marked as selected"


def test_manage_tasks_includes_projects_from_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Projects defined in projects.yaml appear in the filter dropdown."""

    monkeypatch.setattr(tasks_page, "read_tasks", lambda: [])

    project_path = "vault/Projects/new-project.md"
    projects_file = tmp_path / "projects.yaml"
    projects_file.write_text(
        yaml.safe_dump([{"path": project_path}], sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(tasks_page.config, "OUTPUT_PATH", projects_file)

    client = TestClient(app)
    response = client.get("/manage-tasks")

    assert response.status_code == 200
    assert f'value="{project_path}"' in response.text
