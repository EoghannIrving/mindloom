"""Regression tests for managing tasks with filters."""

import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
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
