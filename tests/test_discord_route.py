import sys
from pathlib import Path
from typing import List, Dict

from fastapi.testclient import TestClient

# pylint: disable=wrong-import-position, import-outside-toplevel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app  # noqa: E402
from routes import discord as discord_route  # noqa: E402


def _override_read_tasks(monkeypatch, tasks: List[Dict]):
    def _reader(path: Path | None = None):  # pragma: no cover - signature parity
        return tasks

    monkeypatch.setattr(discord_route, "read_tasks", _reader)


def test_next_task_returns_earliest_due(monkeypatch):
    tasks = [
        {
            "id": 1,
            "title": "Write documentation",
            "status": "active",
            "due": "2024-06-15",
            "energy_cost": 2,
        },
        {
            "id": 2,
            "title": "Prepare slides",
            "status": "active",
            "due": "2024-05-20",
            "energy_cost": 3,
        },
    ]
    _override_read_tasks(monkeypatch, tasks)

    with TestClient(app) as client:
        response = client.get("/discord/next-task")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task"]["id"] == 2
    assert payload["total_tasks"] == 2


def test_next_task_filters_by_project(monkeypatch):
    tasks = [
        {
            "id": 1,
            "title": "Alpha task",
            "project": "Projects/alpha.md",
            "status": "active",
            "due": "2024-06-01",
        },
        {
            "id": 2,
            "title": "Beta task",
            "project": "Projects/beta.md",
            "status": "active",
            "due": "2024-04-01",
        },
    ]
    _override_read_tasks(monkeypatch, tasks)

    with TestClient(app) as client:
        response = client.get("/discord/next-task", params={"project": "alpha"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["task"]["project"] == "Projects/alpha.md"
    assert payload["total_tasks"] == 1


def test_project_list_returns_sorted_unique_projects(monkeypatch):
    tasks = [
        {
            "id": 1,
            "title": "Alpha task",
            "project": "Projects/alpha.md",
            "status": "active",
        },
        {
            "id": 2,
            "title": "Alpha duplicate",
            "project": "Projects/alpha.md",
            "status": "active",
        },
        {
            "id": 3,
            "title": "Beta task",
            "project": "Projects/beta.md",
            "status": "active",
        },
    ]
    _override_read_tasks(monkeypatch, tasks)

    with TestClient(app) as client:
        response = client.get("/discord/projects")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"projects": ["Projects/alpha.md", "Projects/beta.md"]}


def test_project_list_supports_query_filter(monkeypatch):
    tasks = [
        {
            "id": 1,
            "title": "Alpha task",
            "project": "Projects/alpha.md",
            "status": "active",
        },
        {
            "id": 2,
            "title": "Gamma task",
            "project": "Projects/gamma.md",
            "status": "active",
        },
    ]
    _override_read_tasks(monkeypatch, tasks)

    with TestClient(app) as client:
        response = client.get("/discord/projects", params={"q": "gam"})

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"projects": ["Projects/gamma.md"]}
