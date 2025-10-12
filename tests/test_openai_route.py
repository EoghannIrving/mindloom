import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import routes.openai_route as openai_route
from main import app


def test_plan_endpoint_selector(monkeypatch: pytest.MonkeyPatch):
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
    monkeypatch.setattr(openai_route, "filter_tasks_by_energy", lambda t, e: t)

    responses = iter(["- Task A"])

    async def fake_ask(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 500):
        return next(responses)

    captured = []

    async def fake_ask_capture(
        prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 500
    ):
        captured.append(prompt)
        return await fake_ask(prompt, model, max_tokens)

    monkeypatch.setattr(openai_route, "ask_chatgpt", fake_ask_capture)

    client = TestClient(app)
    resp = client.post("/plan?intensity=light&template=plan_intensity_selector")
    assert resp.status_code == 200
    assert resp.json()["plan"] == "- Task A"
    assert "light" in captured[0]


def test_plan_endpoint_morning_planner(monkeypatch: pytest.MonkeyPatch):
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
    monkeypatch.setattr(openai_route, "load_events", lambda s, e: [])

    responses = iter(["Plan"])

    async def fake_ask(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 500):
        return next(responses)

    captured = []

    async def fake_ask_capture(
        prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 500
    ):
        captured.append(prompt)
        return await fake_ask(prompt, model, max_tokens)

    monkeypatch.setattr(openai_route, "ask_chatgpt", fake_ask_capture)

    client = TestClient(app)
    resp = client.post("/plan?template=morning_planner")
    assert resp.status_code == 200
    assert resp.json()["plan"] == "Plan"
    assert "YAML" in captured[0]


def test_plan_endpoint_next_task(monkeypatch: pytest.MonkeyPatch):
    today = date.today().isoformat()
    tasks = [
        {"id": 1, "title": "High Effort", "due": today, "energy_cost": 4},
        {"id": 2, "title": "Gentle Start", "due": today, "energy_cost": 1},
    ]

    recorded = {}

    def fake_upcoming_tasks(days=7):
        assert (
            recorded
        ), "Energy entry should be recorded before selecting the next task"
        return tasks

    monkeypatch.setattr(openai_route, "upcoming_tasks", fake_upcoming_tasks)

    def fake_record_entry(energy: int, mood: str, time_blocks: int):
        recorded.update(
            {
                "date": today,
                "energy": energy,
                "mood": mood,
                "time_blocks": time_blocks,
            }
        )
        return recorded.copy()

    monkeypatch.setattr(openai_route, "record_entry", fake_record_entry)

    monkeypatch.setattr(
        openai_route, "read_entries", lambda: [recorded.copy()] if recorded else []
    )
    monkeypatch.setattr(
        openai_route, "filter_tasks_by_energy", openai_route.filter_tasks_by_energy
    )

    client = TestClient(app)
    payload = {"energy": 3, "mood": "Sad", "time_blocks": 6}
    resp = client.post("/plan?mode=next_task", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "Gentle Start"
    assert data["next_task"]["title"] == "Gentle Start"
    assert recorded["energy"] == payload["energy"]
    assert recorded["mood"] == payload["mood"]


def test_plan_endpoint_next_task_requires_complete_payload(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(openai_route, "upcoming_tasks", lambda days=0: [])
    monkeypatch.setattr(openai_route, "read_entries", lambda: [])

    record_calls = []

    def fake_record_entry(energy: int, mood: str, time_blocks: int):
        record_calls.append((energy, mood, time_blocks))
        return {
            "date": date.today().isoformat(),
            "energy": energy,
            "mood": mood,
            "time_blocks": time_blocks,
        }

    monkeypatch.setattr(openai_route, "record_entry", fake_record_entry)

    client = TestClient(app)
    resp = client.post("/plan?mode=next_task", json={"energy": 3, "mood": "Sad"})

    assert resp.status_code == 400
    assert (
        resp.json()["detail"]
        == "Energy, mood, and time_blocks are required for next_task mode."
    )
    assert record_calls == []


def test_plan_endpoint_next_task_requires_payload_body(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(openai_route, "upcoming_tasks", lambda days=0: [])
    monkeypatch.setattr(openai_route, "read_entries", lambda: [])

    record_calls = []

    def fake_record_entry(energy: int, mood: str, time_blocks: int):
        record_calls.append((energy, mood, time_blocks))
        return {
            "date": date.today().isoformat(),
            "energy": energy,
            "mood": mood,
            "time_blocks": time_blocks,
        }

    monkeypatch.setattr(openai_route, "record_entry", fake_record_entry)

    client = TestClient(app)
    resp = client.post("/plan?mode=next_task")

    assert resp.status_code == 400
    assert (
        resp.json()["detail"]
        == "Energy, mood, and time_blocks are required for next_task mode."
    )
    assert record_calls == []
