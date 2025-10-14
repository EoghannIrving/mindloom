"""Tests for deleting tasks from the manage tasks interface."""

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


def _setup_environment(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    tasks_file = tmp_path / "tasks.yaml"
    vault_root = tmp_path / "Projects"
    vault_root.mkdir(parents=True, exist_ok=True)

    def _read_tasks_override(path=None):  # pragma: no cover - signature parity
        return tasks.read_tasks(tasks_file)

    def _write_tasks_override(data, path=None):  # pragma: no cover - signature parity
        tasks.write_tasks(data, tasks_file)

    def _sync_projects_override(
        items, root=None, cleared_projects=None
    ):  # pragma: no cover - signature parity
        return parse_projects.write_tasks_to_projects(
            items, root=vault_root, cleared_projects=cleared_projects
        )

    monkeypatch.setattr(tasks_route, "read_tasks", _read_tasks_override)
    monkeypatch.setattr(tasks_route, "write_tasks", _write_tasks_override)
    monkeypatch.setattr(tasks_route, "write_tasks_to_projects", _sync_projects_override)

    return tasks_file, vault_root


def test_delete_task_removes_from_yaml_and_markdown(monkeypatch, tmp_path: Path):
    tasks_file, vault_root = _setup_environment(monkeypatch, tmp_path)

    project_rel = "Projects/demo.md"
    project_file = vault_root / "demo.md"
    project_file.write_text("# Demo\n- [ ] Remove me\n", encoding="utf-8")

    existing_tasks = [
        {
            "id": 1,
            "title": "Remove me",
            "project": project_rel,
            "status": "active",
            "type": "task",
            "effort": "low",
            "energy_cost": 1,
        },
        {
            "id": 2,
            "title": "Keep me",
            "status": "active",
            "type": "task",
            "effort": "low",
            "energy_cost": 1,
        },
    ]

    tasks.write_tasks(existing_tasks, tasks_file)

    form_payload = {
        "title-1": "Remove me",
        "project-1": project_rel,
        "status-1": "active",
        "delete-1": "1",
        "title-2": "Keep me",
        "status-2": "active",
    }

    with TestClient(app) as client:
        response = client.post(
            "/manage-tasks", data=form_payload, follow_redirects=False
        )

    assert response.status_code == 303

    persisted = yaml.safe_load(tasks_file.read_text(encoding="utf-8"))
    assert len(persisted) == 1
    assert persisted[0]["id"] == 2

    updated_markdown = project_file.read_text(encoding="utf-8")
    assert "Remove me" not in updated_markdown
    assert "Keep me" not in updated_markdown  # project had a single task, now cleared
