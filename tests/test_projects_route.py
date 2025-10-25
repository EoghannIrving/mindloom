import sys
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import config
import parse_projects
from main import app
from routes import projects as projects_route


def _setup_vault(monkeypatch, tmp_path: Path) -> Path:
    vault_root = tmp_path / "Projects"
    monkeypatch.setattr(config, "VAULT_PATH", vault_root)
    return vault_root


def _setup_project_paths(monkeypatch, tmp_path: Path, vault_root: Path) -> None:
    tasks_path = tmp_path / "data/tasks.yaml"
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    projects_yaml = tmp_path / "projects.yaml"

    monkeypatch.setattr(config, "TASKS_PATH", tasks_path)
    monkeypatch.setattr(config, "OUTPUT_PATH", projects_yaml)

    monkeypatch.setattr(projects_route, "TASKS_FILE", tasks_path)
    monkeypatch.setattr(projects_route, "PROJECTS_FILE", projects_yaml)

    monkeypatch.setattr(parse_projects, "TASKS_FILE", tasks_path)
    monkeypatch.setattr(parse_projects, "PROJECTS_DIR", vault_root)
    monkeypatch.setattr(parse_projects, "OUTPUT_FILE", projects_yaml)


def test_create_project_success(monkeypatch, tmp_path):
    vault_root = _setup_vault(monkeypatch, tmp_path)
    _setup_project_paths(monkeypatch, tmp_path, vault_root)
    payload = {
        "title": "Launch Mindloom",
        "slug": "launch-mindloom",
        "status": "active",
        "area": "Career",
        "effort": "medium",
        "due": "2024-05-01",
        "tasks": [
            {
                "title": "Draft pitch",
                "due": "2024-04-01",
            },
            {
                "title": "Review prototype",
                "status": "complete",
                "recurrence": "weekly",
            },
        ],
    }

    with TestClient(app) as client:
        response = client.post("/projects", json=payload)
        assert response.status_code == 201
        data = response.json()

    assert data["title"] == payload["title"]
    assert data["area"] == payload["area"]
    assert data["effort"] == payload["effort"]
    assert data["due"] == payload["due"]
    assert data["path"].endswith("Projects/launch-mindloom.md")
    assert data["tasks"] == [
        "- [ ] Draft pitch | due:2024-04-01",
        "- [x] Review prototype | recur:weekly",
    ]

    project_file = vault_root / "launch-mindloom.md"
    assert project_file.exists()
    content = project_file.read_text(encoding="utf-8")
    assert "status: active" in content
    assert "# Launch Mindloom" in content
    assert "- [ ] Draft pitch | due:2024-04-01" in content


def test_create_project_conflict(monkeypatch, tmp_path):
    vault_root = _setup_vault(monkeypatch, tmp_path)
    _setup_project_paths(monkeypatch, tmp_path, vault_root)
    project_file = vault_root / "existing.md"
    project_file.parent.mkdir(parents=True, exist_ok=True)
    project_file.write_text("existing", encoding="utf-8")

    payload = {
        "title": "Existing",
        "slug": "existing.md",
        "status": "active",
        "area": "Personal",
        "effort": "low",
    }

    with TestClient(app) as client:
        response = client.post("/projects", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "Project file already exists"


def test_create_project_invalid_slug(monkeypatch, tmp_path):
    _setup_vault(monkeypatch, tmp_path)
    _setup_project_paths(monkeypatch, tmp_path, tmp_path / "Projects")
    payload = {
        "title": "Invalid",
        "slug": "../invalid",
        "status": "active",
        "area": "Personal",
        "effort": "low",
    }

    with TestClient(app) as client:
        response = client.post("/projects", json=payload)

    assert response.status_code == 422


def test_get_projects_empty_file(monkeypatch, tmp_path):
    empty_projects_file = tmp_path / "projects.yaml"
    empty_projects_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(config, "OUTPUT_PATH", empty_projects_file)
    monkeypatch.setattr(projects_route, "PROJECTS_FILE", empty_projects_file)

    with TestClient(app) as client:
        response = client.get("/projects")

    assert response.status_code == 200
    assert response.json() == []


def test_merge_projects_success(monkeypatch, tmp_path):
    vault_root = _setup_vault(monkeypatch, tmp_path)
    _setup_project_paths(monkeypatch, tmp_path, vault_root)

    target_file = vault_root / "target.md"
    source_file = vault_root / "source.md"
    vault_root.mkdir(parents=True, exist_ok=True)

    target_content = "\n".join(
        [
            "---",
            "status: active",
            "---",
            "",
            "# Target Project",
            "",
            "- [ ] Target task | due:2024-06-01",
        ]
    )
    source_content = "\n".join(
        [
            "---",
            "status: active",
            "---",
            "",
            "# Source Project",
            "",
            "- [ ] Source task | effort:high",
        ]
    )

    target_file.write_text(target_content + "\n", encoding="utf-8")
    source_file.write_text(source_content + "\n", encoding="utf-8")

    manual_task = {
        "id": 1,
        "title": "Manual task",
        "project": "Projects/source.md",
        "status": "active",
        "source": "manual",
    }
    tasks_path = config.TASKS_PATH
    with tasks_path.open("w", encoding="utf-8") as handle:
        yaml.dump([manual_task, manual_task.copy()], handle, sort_keys=False)

    with TestClient(app) as client:
        response = client.post(
            "/projects/merge",
            json={"source_slug": "source", "target_slug": "target"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "Projects/source.md"
    assert data["target"] == "Projects/target.md"
    assert data["migrated_project_tasks"] == 1
    assert data["tasks_relinked"] == 2  # two duplicates merged into one
    assert data["source_removed"] is True

    assert not source_file.exists()
    updated_content = target_file.read_text(encoding="utf-8")
    assert "- [ ] Target task | due:2024-06-01" in updated_content
    assert "- [ ] Source task | effort:high" in updated_content

    tasks = yaml.safe_load(config.TASKS_PATH.read_text(encoding="utf-8"))
    manual_projects = [t["project"] for t in tasks if t.get("source") == "manual"]
    assert manual_projects == ["Projects/target.md"]
    assert all(t.get("project") != "Projects/source.md" for t in tasks)

    projects_yaml = config.OUTPUT_PATH.read_text(encoding="utf-8")
    assert "Projects/target.md" in projects_yaml
    assert "Projects/source.md" not in projects_yaml


def test_merge_projects_missing_source(monkeypatch, tmp_path):
    vault_root = _setup_vault(monkeypatch, tmp_path)
    _setup_project_paths(monkeypatch, tmp_path, vault_root)

    target_file = vault_root / "target.md"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("- [ ] placeholder\n", encoding="utf-8")

    with TestClient(app) as client:
        response = client.post(
            "/projects/merge",
            json={"source_slug": "missing", "target_slug": "target"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Source project not found"
