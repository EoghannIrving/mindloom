import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import routes.openai_route as openai_route
from main import app


def test_plan_endpoint_intensity(monkeypatch: pytest.MonkeyPatch):
    tasks = [
        {"title": "Task A", "energy_cost": 1},
        {"title": "Task B", "energy_cost": 2},
    ]

    monkeypatch.setattr(openai_route, "upcoming_tasks", lambda: tasks)
    today = date.today().isoformat()
    monkeypatch.setattr(
        openai_route,
        "read_entries",
        lambda: [{"date": today, "energy": 5, "time_blocks": 4}],
    )
    monkeypatch.setattr(openai_route, "save_plan", lambda plan: None)
    monkeypatch.setattr(openai_route, "filter_tasks_by_energy", lambda t, e: t)

    responses = iter(["- Task A", "Plan"])

    async def fake_ask(prompt: str, model: str = "gpt-3.5-turbo"):
        return next(responses)

    captured = []

    async def fake_ask_capture(prompt: str, model: str = "gpt-3.5-turbo"):
        captured.append(prompt)
        return await fake_ask(prompt, model)

    monkeypatch.setattr(openai_route, "ask_chatgpt", fake_ask_capture)

    client = TestClient(app)
    resp = client.post("/plan?intensity=light")
    assert resp.status_code == 200
    assert resp.json()["plan"] == "Plan"
    assert "light" in captured[0]
