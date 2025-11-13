import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import routes.openai_route as openai_route
from routes.openai_route import effective_energy_level
from task_selector import select_next_task
from openai_client import OpenAIClientError
from main import app


def test_effective_energy_level_edge_cases():
    # Both inputs missing should return the provided default value.
    assert effective_energy_level(None, None) == 3
    assert effective_energy_level(None, None, default=5) == 5

    # Mood-only inputs should respect the mapped target energy level.
    assert effective_energy_level(None, "Joyful") == 5
    assert effective_energy_level(None, "sad") == 1

    # When energy and mood conflict, the minimum value should be used.
    assert effective_energy_level(4, "sad") == 1
    assert effective_energy_level(2, "joyful") == 2

    # Invalid energy or mood strings should fall back to the default.
    assert effective_energy_level("high", "sparkly") == 3


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

    def fake_record_entry(energy: int, mood: str, time_blocks: Optional[int] = None):
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
    assert data["reasoning"] == {
        "due_date": today,
        "energy_penalty": 0,
        "executive_penalty": 0,
        "total_score": 0,
    }
    assert recorded["energy"] == payload["energy"]
    assert recorded["mood"] == payload["mood"]


def test_plan_endpoint_next_task_respects_project_filter_on_energy_fallback(
    monkeypatch: pytest.MonkeyPatch,
):
    today = date.today().isoformat()
    tasks = [
        {
            "id": 1,
            "title": "Deep Focus",
            "due": today,
            "energy_cost": 5,
            "project": "Focus",
        },
        {
            "id": 2,
            "title": "General Task",
            "due": today,
            "energy_cost": 1,
            "project": "Other",
        },
    ]

    def fake_upcoming_tasks(days: int = 7):
        return list(tasks)

    monkeypatch.setattr(openai_route, "upcoming_tasks", fake_upcoming_tasks)

    recorded: Dict[str, Any] = {}

    def fake_record_entry(energy: int, mood: str, time_blocks: Optional[int] = None):
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
    monkeypatch.setattr(openai_route, "read_entries", lambda: [])

    def fake_filter_tasks_by_energy(task_list, target):
        return [t for t in task_list if t.get("energy_cost", 0) <= target]

    monkeypatch.setattr(
        openai_route, "filter_tasks_by_energy", fake_filter_tasks_by_energy
    )

    client = TestClient(app)
    payload = {"energy": 1, "mood": "meh", "time_blocks": 3}
    resp = client.post("/plan?mode=next_task&project_param=Focus", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_task"]["project"] == "Focus"
    assert data["next_task"]["title"] == "Deep Focus"


def test_plan_endpoint_next_task_with_project_filter_and_no_matches(
    monkeypatch: pytest.MonkeyPatch,
):
    today = date.today().isoformat()
    tasks = [
        {
            "id": 1,
            "title": "General Task",
            "due": today,
        "energy_cost": 1,
            "project": "Other",
        }
    ]

    def fake_upcoming_tasks(days: int = 7):
        return list(tasks)

    monkeypatch.setattr(openai_route, "upcoming_tasks", fake_upcoming_tasks)

    recorded: Dict[str, Any] = {}

    def fake_record_entry(energy: int, mood: str, time_blocks: Optional[int] = None):
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
    monkeypatch.setattr(openai_route, "read_entries", lambda: [])
    monkeypatch.setattr(
        openai_route, "filter_tasks_by_energy", lambda task_list, target: task_list
    )

    client = TestClient(app)
    payload = {"energy": 2, "mood": "okay", "time_blocks": 3}
    resp = client.post("/plan?mode=next_task&project_param=Focus", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_task"] is None
    assert "No tasks match" in data["plan"]


def test_plan_endpoint_next_task_uses_effective_energy(
    monkeypatch: pytest.MonkeyPatch,
):
    today = date.today().isoformat()
    tasks = [
        {"id": 1, "title": "Deep Work", "due": today, "energy_cost": 4},
        {"id": 2, "title": "Easy Win", "due": today, "energy_cost": 1},
    ]

    def fake_upcoming_tasks(days: int = 7):
        return list(tasks)

    monkeypatch.setattr(openai_route, "upcoming_tasks", fake_upcoming_tasks)

    recorded: Dict[str, Any] = {}

    def fake_record_entry(energy: int, mood: str, time_blocks: Optional[int] = None):
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

    client = TestClient(app)
    payload = {"energy": 4, "mood": "sad", "time_blocks": 4}
    resp = client.post("/plan?mode=next_task", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_task"]["title"] == "Easy Win"
    assert data["next_task"]["energy_cost"] == 1


def test_select_next_task_penalizes_executive_trigger():
    today = date.today().isoformat()
    tasks = [
        {
            "id": 1,
            "title": "High Friction",
            "due": today,
        "energy_cost": 1,
            "executive_trigger": "high",
        },
        {
            "id": 2,
            "title": "Low Friction",
            "due": today,
            "energy_cost": 2,
            "executive_trigger": "low",
        },
    ]

    selected, reasoning = select_next_task(tasks, mood="sad", energy_level=2)

    assert selected["title"] == "Low Friction"
    assert reasoning == {
        "due_date": today,
        "energy_penalty": 0,
        "executive_penalty": 2,
        "total_score": 2,
    }


def test_select_next_task_prefers_high_energy_within_limits():
    today = date.today().isoformat()
    tasks = [
        {"id": 1, "title": "Easy Win", "due": today, "energy_cost": 1},
        {"id": 2, "title": "High Reward", "due": today, "energy_cost": 3},
    ]

    selected, reasoning = select_next_task(tasks, mood="meh", energy_level=3)

    assert selected["title"] == "High Reward"
    assert reasoning["energy_penalty"] == 0


def test_plan_endpoint_next_task_filters_by_project(monkeypatch: pytest.MonkeyPatch):
    today = date.today().isoformat()
    tasks = [
        {
            "id": 1,
            "title": "Alpha Deliverable",
            "due": today,
            "energy_cost": 3,
            "project": "Alpha",
            "area": "Work",
        },
        {
            "id": 2,
            "title": "Beta Follow-up",
            "due": today,
            "energy_cost": 2,
            "project": "Beta",
            "area": "Personal",
        },
    ]

    def fake_upcoming_tasks(days: int = 7):
        return list(tasks)

    monkeypatch.setattr(openai_route, "upcoming_tasks", fake_upcoming_tasks)

    recorded = {}

    def fake_record_entry(energy: int, mood: str, time_blocks: Optional[int] = None):
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
    monkeypatch.setattr(openai_route, "read_entries", lambda: [])
    monkeypatch.setattr(openai_route, "filter_tasks_by_energy", lambda t, e: t)

    client = TestClient(app)
    payload = {"energy": 3, "mood": "Okay", "time_blocks": 2, "project": "Alpha"}
    resp = client.post("/plan?mode=next_task", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_task"]["project"] == "Alpha"
    assert data["next_task"]["title"] == "Alpha Deliverable"
    assert recorded["energy"] == payload["energy"]
    assert recorded["mood"] == payload["mood"]
    assert recorded["time_blocks"] == payload["time_blocks"]


def test_plan_endpoint_next_task_falls_back_when_filter_empty(
    monkeypatch: pytest.MonkeyPatch,
):
    today = date.today()
    tasks = [
        {
            "id": 1,
            "title": "Overdue Deep Work",
            "due": (today - timedelta(days=2)).isoformat(),
            "energy_cost": 5,
        },
        {
            "id": 2,
            "title": "Catch Up On Inbox",
            "due": (today - timedelta(days=1)).isoformat(),
            "energy_cost": 4,
        },
    ]

    recorded = {}

    def fake_upcoming_tasks(days=7):
        return list(tasks)

    monkeypatch.setattr(openai_route, "upcoming_tasks", fake_upcoming_tasks)

    def fake_record_entry(energy: int, mood: str, time_blocks: Optional[int] = None):
        recorded.update(
            {
                "date": today.isoformat(),
                "energy": energy,
                "mood": mood,
                "time_blocks": time_blocks,
            }
        )
        return recorded.copy()

    monkeypatch.setattr(openai_route, "record_entry", fake_record_entry)

    monkeypatch.setattr(openai_route, "read_entries", lambda: [])
    monkeypatch.setattr(
        openai_route, "filter_tasks_by_energy", openai_route.filter_tasks_by_energy
    )

    client = TestClient(app)
    payload = {"energy": 1, "mood": "sad", "time_blocks": 3}
    resp = client.post("/plan?mode=next_task", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_task"] is not None
    assert data["next_task"]["title"] in {t["title"] for t in tasks}


def test_plan_endpoint_next_task_metadata_filter_returns_empty_when_no_match(
    monkeypatch: pytest.MonkeyPatch,
):
    today = date.today().isoformat()
    tasks = [
        {
            "id": 10,
            "title": "Alpha Planning",
            "due": today,
            "energy_cost": 2,
            "project": "Alpha",
            "area": "Work",
        },
        {
            "id": 11,
            "title": "Beta Review",
            "due": today,
            "energy_cost": 2,
            "project": "Beta",
            "area": "Personal",
        },
    ]

    def fake_upcoming_tasks(days: int = 7):
        return list(tasks)

    monkeypatch.setattr(openai_route, "upcoming_tasks", fake_upcoming_tasks)

    recorded = {}

    def fake_record_entry(energy: int, mood: str, time_blocks: Optional[int] = None):
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
    monkeypatch.setattr(openai_route, "read_entries", lambda: [])
    monkeypatch.setattr(openai_route, "filter_tasks_by_energy", lambda t, e: t)

    client = TestClient(app)
    payload = {
        "energy": 2,
        "mood": "Okay",
        "time_blocks": 3,
        "project": "Gamma",
    }
    resp = client.post("/plan?mode=next_task", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_task"] is None
    assert "No tasks match" in data["plan"]


def test_plan_endpoint_next_task_requires_energy_and_mood(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(openai_route, "upcoming_tasks", lambda days=7: [])
    monkeypatch.setattr(openai_route, "read_entries", lambda: [])

    record_calls = []

    def fake_record_entry(energy: int, mood: str, time_blocks: Optional[int] = None):
        record_calls.append((energy, mood, time_blocks))
        return {
            "date": date.today().isoformat(),
            "energy": energy,
            "mood": mood,
            "time_blocks": time_blocks,
        }

    monkeypatch.setattr(openai_route, "record_entry", fake_record_entry)

    client = TestClient(app)
    resp = client.post("/plan?mode=next_task", json={"energy": 3})

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Energy and mood are required for next_task mode."
    resp = client.post("/plan?mode=next_task", json={"mood": "Sad"})

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Energy and mood are required for next_task mode."
    assert record_calls == []


def test_plan_endpoint_next_task_allows_missing_time_blocks(
    monkeypatch: pytest.MonkeyPatch,
):
    today = date.today().isoformat()
    tasks = [
        {"id": 1, "title": "Gentle", "due": today, "energy_cost": 2},
        {"id": 2, "title": "Intense", "due": today, "energy_cost": 4},
    ]

    monkeypatch.setattr(openai_route, "upcoming_tasks", lambda days=7: list(tasks))
    monkeypatch.setattr(openai_route, "read_entries", lambda: [])
    monkeypatch.setattr(openai_route, "filter_tasks_by_energy", lambda t, e: t)

    def fail_record_entry(energy: int, mood: str, time_blocks: Optional[int] = None):
        pytest.fail("record_entry should not be called when time blocks are omitted")

    monkeypatch.setattr(openai_route, "record_entry", fail_record_entry)

    client = TestClient(app)
    resp = client.post("/plan?mode=next_task", json={"energy": 2, "mood": "Okay"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "Gentle"
    assert data["next_task"]["title"] == "Gentle"


def test_plan_endpoint_next_task_requires_payload_body(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(openai_route, "upcoming_tasks", lambda days=7: [])
    monkeypatch.setattr(openai_route, "read_entries", lambda: [])

    record_calls = []

    def fake_record_entry(energy: int, mood: str, time_blocks: Optional[int] = None):
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
    assert resp.json()["detail"] == "Energy and mood are required for next_task mode."
    assert record_calls == []


def test_plan_endpoint_next_task_falls_back_to_future_tasks(
    monkeypatch: pytest.MonkeyPatch,
):
    today = date.today()
    future_due = (today + timedelta(days=2)).isoformat()
    tasks = [{"id": 3, "title": "Future Task", "due": future_due, "energy_cost": 2}]

    calls = []

    def fake_upcoming_tasks(days: int = 7):
        calls.append(days)
        if days == 0:
            return []
        return tasks

    monkeypatch.setattr(openai_route, "upcoming_tasks", fake_upcoming_tasks)

    recorded = {}

    def fake_record_entry(energy: int, mood: str, time_blocks: Optional[int] = None):
        recorded.update(
            {
                "date": today.isoformat(),
                "energy": energy,
                "mood": mood,
                "time_blocks": time_blocks,
            }
        )
        return recorded.copy()

    monkeypatch.setattr(openai_route, "record_entry", fake_record_entry)
    monkeypatch.setattr(openai_route, "read_entries", lambda: [])
    monkeypatch.setattr(openai_route, "filter_tasks_by_energy", lambda t, e: t)

    client = TestClient(app)
    payload = {"energy": 2, "mood": "Okay", "time_blocks": 3}
    resp = client.post("/plan?mode=next_task", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "Future Task"
    assert data["next_task"]["title"] == "Future Task"
    assert calls == [0, 7]
    assert recorded["energy"] == payload["energy"]
    assert recorded["mood"] == payload["mood"]


def test_plan_endpoint_plan_mode_applies_metadata_filters(
    monkeypatch: pytest.MonkeyPatch,
):
    today = date.today().isoformat()
    tasks = [
        {
            "id": 1,
            "title": "Work Task",
            "due": today,
            "energy_cost": 2,
            "area": "Work",
        },
        {
            "id": 2,
            "title": "Personal Task",
            "due": today,
            "energy_cost": 2,
            "area": "Personal",
        },
    ]

    monkeypatch.setattr(openai_route, "upcoming_tasks", lambda days=7: list(tasks))
    monkeypatch.setattr(openai_route, "save_plan", lambda plan: None)
    monkeypatch.setattr(openai_route, "load_events", lambda start, end: [])

    captured = []

    def fake_filter(task_list, energy):
        captured.append(task_list)
        return task_list

    monkeypatch.setattr(openai_route, "filter_tasks_by_energy", fake_filter)
    monkeypatch.setattr(
        openai_route,
        "read_entries",
        lambda: [{"date": today, "energy": 4, "time_blocks": 3}],
    )

    async def fake_ask(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 500):
        return "Plan"

    monkeypatch.setattr(openai_route, "ask_chatgpt", fake_ask)

    client = TestClient(app)
    resp = client.post("/plan?template=morning_planner", json={"area": "Work"})

    assert resp.status_code == 200
    assert resp.json()["plan"] == "Plan"
    assert captured, "Energy filter should be invoked"
    assert len(captured[0]) == 1
    assert captured[0][0]["area"] == "Work"


def test_ask_endpoint_handles_openai_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    async def fail(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 500):
        raise OpenAIClientError("boom")

    monkeypatch.setattr(openai_route, "ask_chatgpt", fail)

    client = TestClient(app)
    with caplog.at_level(logging.ERROR):
        resp = client.post("/ask", json={"prompt": "Hello"})

    assert resp.status_code == 502
    assert (
        resp.json()["detail"]
        == "Failed to fetch response from language model. Please try again later."
    )
    assert any(
        "POST /ask OpenAI call failed" in record.message for record in caplog.records
    )


def test_plan_endpoint_handles_openai_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    monkeypatch.setattr(openai_route, "upcoming_tasks", lambda: [])
    monkeypatch.setattr(openai_route, "read_entries", lambda: [])
    monkeypatch.setattr(openai_route, "load_events", lambda start, end: [])
    monkeypatch.setattr(openai_route, "save_plan", lambda plan: None)

    async def fail(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 500):
        raise OpenAIClientError("boom")

    monkeypatch.setattr(openai_route, "ask_chatgpt", fail)

    client = TestClient(app)
    with caplog.at_level(logging.ERROR):
        resp = client.post("/plan?template=morning_planner")

    assert resp.status_code == 502
    assert (
        resp.json()["detail"]
        == "Failed to generate plan from language model. Please try again later."
    )
    assert any(
        "POST /plan OpenAI call failed" in record.message for record in caplog.records
    )


def test_goal_breakdown_endpoint_handles_openai_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    async def fail(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 500):
        raise OpenAIClientError("boom")

    monkeypatch.setattr(openai_route, "ask_chatgpt", fail)

    client = TestClient(app)
    with caplog.at_level(logging.ERROR):
        resp = client.post("/goal-breakdown", json={"goal": "Ship"})

    assert resp.status_code == 502
    assert (
        resp.json()["detail"]
        == "Failed to generate goal breakdown from language model. Please try again later."
    )
    assert any(
        "POST /goal-breakdown OpenAI call failed" in record.message
        for record in caplog.records
    )
