import sys
from datetime import date
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import routes.activation as activation
from main import app


def test_suggest_task(monkeypatch: pytest.MonkeyPatch):
    tasks = [{"title": "Task A", "project": "P", "energy_cost": 1}]
    monkeypatch.setattr(activation, "read_tasks", lambda: tasks)
    today = date.today().isoformat()
    monkeypatch.setattr(
        activation,
        "read_entries",
        lambda: [{"date": today, "energy": 3, "mood": "Meh"}],
    )

    async def fake_call(payload):
        return [{"task": "Task A", "score": 5}]

    monkeypatch.setattr(activation, "_call_activation_engine", fake_call)

    client = TestClient(app)
    resp = client.get("/suggest-task")
    assert resp.status_code == 200
    assert resp.json()["suggestion"]["task"] == "Task A"
