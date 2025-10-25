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


def _prepare_prompt_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, existing_files=None
) -> Path:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    for relative_path, content in (existing_files or {}).items():
        file_path = prompts_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    monkeypatch.setattr(web, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(web, "read_tasks", lambda: [])
    monkeypatch.setattr(web, "upcoming_tasks", lambda: [])
    monkeypatch.setattr(web, "read_entries", lambda: [])
    monkeypatch.setattr(web, "load_events", lambda start, end: [])

    return prompts_dir


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


def test_render_prompt_allows_nested_template(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    prompts_dir = _prepare_prompt_environment(
        monkeypatch,
        tmp_path,
        existing_files={"nested/test.txt": "content"},
    )

    captured_path = {}

    def fake_render_prompt(path: str, variables: dict):
        captured_path["value"] = path
        return "rendered"

    monkeypatch.setattr(web, "render_prompt", fake_render_prompt)

    client = TestClient(app)
    response = client.post("/render-prompt", json={"template": "nested/test.txt"})

    assert response.status_code == 200
    assert response.json()["result"] == "rendered"
    expected = (prompts_dir / "nested" / "test.txt").resolve()
    assert captured_path["value"] == str(expected)


def test_render_prompt_rejects_path_traversal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _prepare_prompt_environment(monkeypatch, tmp_path)
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("blocked")

    called = False

    def fake_render_prompt(path: str, variables: dict):
        nonlocal called
        called = True
        return "should not be called"

    monkeypatch.setattr(web, "render_prompt", fake_render_prompt)

    client = TestClient(app)
    response = client.post("/render-prompt", json={"template": "../outside.txt"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid template path."
    assert not called


def test_render_prompt_rejects_missing_template(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _prepare_prompt_environment(monkeypatch, tmp_path)

    def fake_render_prompt(path: str, variables: dict):
        raise AssertionError("render_prompt should not be called for missing files")

    monkeypatch.setattr(web, "render_prompt", fake_render_prompt)

    client = TestClient(app)
    response = client.post("/render-prompt", json={"template": "missing.txt"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Template not found."
