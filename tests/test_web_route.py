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
