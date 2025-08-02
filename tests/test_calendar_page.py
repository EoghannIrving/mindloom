"""Tests for calendar page route automatically loading calendars."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.calendar_page as cp


def test_calendar_page_loads_linked_calendars(monkeypatch):
    """GET /calendar should trigger load_events and display results."""

    called = {}

    def fake_load_events(start: date, end: date):  # pragma: no cover - patched
        called["args"] = (start, end)
        return [
            SimpleNamespace(
                summary="Event", start=datetime(2025, 1, 1), end=datetime(2025, 1, 1, 1)
            )
        ]

    monkeypatch.setattr(cp, "load_events", fake_load_events)

    app = FastAPI()
    app.include_router(cp.router)
    client = TestClient(app)

    response = client.get("/calendar")
    assert response.status_code == 200
    assert "Event" in response.text
    assert called["args"][0] == date.today()
    assert called["args"][1] == date.today() + timedelta(days=7)
