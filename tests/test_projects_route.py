import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import config
from main import app
from routes import projects as projects_route


def _setup_vault(monkeypatch, tmp_path: Path) -> Path:
    vault_root = tmp_path / "Projects"
    monkeypatch.setattr(config, "VAULT_PATH", vault_root)
    return vault_root


def test_create_project_success(monkeypatch, tmp_path):
    vault_root = _setup_vault(monkeypatch, tmp_path)
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
