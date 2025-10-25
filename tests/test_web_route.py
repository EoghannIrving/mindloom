import sys
from pathlib import Path
from datetime import datetime

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app
import routes.web as web


class DummyEvent:
    def __init__(self, start, end):
        self.start = start
        self.end = end


def test_index_includes_all_active_projects(monkeypatch: pytest.MonkeyPatch):
    due_soon = [
        {
            "title": "Due soon task",
            "project": "Project Alpha",
            "area": "Focus",
            "status": "in-progress",
        }
    ]
    all_tasks = due_soon + [
        {
            "title": "Later task",
            "project": "Project Beta",
            "area": "Deep Work",
            "status": "todo",
        },
        {
            "title": "Completed task",
            "project": "Project Gamma",
            "area": "Archive",
            "status": "complete",
        },
    ]
    monkeypatch.setattr(web, "upcoming_tasks", lambda: due_soon)
    monkeypatch.setattr(web, "read_tasks", lambda: all_tasks)

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "Project Alpha" in html
    assert "Project Beta" in html
    assert "Project Gamma" not in html
    assert "Deep Work" in html
    assert "Archive" not in html


def test_projects_page_includes_management_controls(
    monkeypatch: pytest.MonkeyPatch,
):
    all_tasks = [
        {
            "title": "One",
            "project": "projects/source.md",
            "area": "Area A",
            "status": "todo",
        },
        {
            "title": "Two",
            "project": "projects/target.md",
            "area": "Area B",
            "status": "active",
        },
    ]
    monkeypatch.setattr(web, "read_tasks", lambda: all_tasks)

    client = TestClient(app)
    response = client.get("/projects-page")

    assert response.status_code == 200
    html = response.text
    assert 'id="newProjectForm"' in html
    assert 'id="parseBtn"' in html
    assert 'id="mergeProjectsBtn"' in html
    assert 'id="mergeSourceProject"' in html


def test_render_prompt_morning_injects_calendar(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(web, "read_tasks", lambda: [])
    monkeypatch.setattr(web, "upcoming_tasks", lambda: [])
    monkeypatch.setattr(web, "read_entries", lambda: [])
    monkeypatch.setattr(
        web,
        "load_events",
        lambda start, end: [
            DummyEvent(datetime(2023, 1, 1, 9, 0), datetime(2023, 1, 1, 10, 0))
        ],
    )

    client = TestClient(app)
    resp = client.post("/render-prompt", json={"template": "morning_planner.txt"})
    assert resp.status_code == 200
    assert "09:00-10:00" in resp.json()["result"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"template": ""},
        {"template": "   "},
        {"template": None},
    ],
)
def test_render_prompt_requires_template(payload):
    client = TestClient(app)
    response = client.post("/render-prompt", json=payload)
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "The 'template' parameter must be a non-empty string."
    )
