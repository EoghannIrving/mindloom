"""Tests for the task creation API endpoint."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

# pylint: disable=wrong-import-position, import-outside-toplevel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import parse_projects
import tasks
from main import app
from routes import tasks_page as tasks_route


def _setup_task_environment(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    tasks_file = tmp_path / "tasks.yaml"
    vault_root = tmp_path / "Projects"
    vault_root.mkdir(parents=True, exist_ok=True)

    def _read_tasks_override(path=None):  # pragma: no cover - signature parity
        return tasks.read_tasks(tasks_file)

    def _write_tasks_override(data, path=None):  # pragma: no cover - signature parity
        tasks.write_tasks(data, tasks_file)

    def _sync_projects_override(
        items, root=None
    ):  # pragma: no cover - signature parity
        return parse_projects.write_tasks_to_projects(items, root=vault_root)

    monkeypatch.setattr(tasks_route, "read_tasks", _read_tasks_override)
    monkeypatch.setattr(tasks_route, "write_tasks", _write_tasks_override)
    monkeypatch.setattr(tasks_route, "write_tasks_to_projects", _sync_projects_override)

    return tasks_file, vault_root


def test_create_task_assigns_next_id(monkeypatch, tmp_path: Path):
    tasks_file, _ = _setup_task_environment(monkeypatch, tmp_path)

    existing = [
        {
            "id": 5,
            "title": "Backlog research",
            "effort": "medium",
            "energy_cost": 3,
            "status": "active",
            "type": "task",
        }
    ]
    tasks.write_tasks(existing, tasks_file)

    with TestClient(app) as client:
        response = client.post("/tasks", json={"title": "Outline summary"})

    assert response.status_code == 201
    created = response.json()
    assert created["id"] == 6
    assert created["energy_cost"] == 1
    assert created["effort"] == "low"
    assert created["status"] == "active"

    persisted = yaml.safe_load(tasks_file.read_text(encoding="utf-8"))
    assert len(persisted) == 2
    assert persisted[-1]["title"] == "Outline summary"
    assert persisted[-1]["id"] == 6
    assert all("due_today" not in task for task in persisted)


def test_create_task_updates_project_markdown(monkeypatch, tmp_path: Path):
    tasks_file, vault_root = _setup_task_environment(monkeypatch, tmp_path)

    project_rel = "Projects/demo.md"
    project_file = vault_root / "demo.md"
    project_file.write_text("- [ ] Backlog research\n", encoding="utf-8")

    existing = [
        {
            "id": 1,
            "title": "Backlog research",
            "project": project_rel,
            "effort": "low",
            "energy_cost": 1,
            "status": "active",
            "type": "task",
        }
    ]
    tasks.write_tasks(existing, tasks_file)

    payload = {"title": "Schedule demo", "project": project_rel}
    with TestClient(app) as client:
        response = client.post("/tasks", json=payload)

    assert response.status_code == 201
    saved = yaml.safe_load(tasks_file.read_text(encoding="utf-8"))
    assert len(saved) == 2
    assert saved[-1]["project"] == project_rel

    content = project_file.read_text(encoding="utf-8")
    assert "- [ ] Backlog research" in content
    assert "- [ ] Schedule demo" in content
