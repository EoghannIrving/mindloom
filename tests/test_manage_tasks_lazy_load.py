"""Regression coverage for the lazy-loading manage tasks chunk."""

from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app
import routes.tasks_page as tasks_page


def _build_demo_tasks(count: int):
    """Return tasks with deterministic due dates for ordering."""

    tasks = []
    for index in range(1, count + 1):
        tasks.append(
            {
                "id": index,
                "title": f"Chunk {index}",
                "status": "active",
                "due": f"2024-01-{index:02d}",
            }
        )
    return tasks


@pytest.mark.parametrize(
    ("offset", "limit", "expected_titles", "expected_has_more"),
    [
        (2, 2, ["Chunk 3", "Chunk 4"], True),
        (4, 3, ["Chunk 5"], False),
    ],
)
def test_manage_tasks_chunk(
    offset, limit, expected_titles, expected_has_more, monkeypatch
):
    """Chunks should return HTML for the requested slice with pagination hints."""

    demo_tasks = _build_demo_tasks(5)
    monkeypatch.setattr(
        tasks_page, "read_tasks", lambda: [dict(task) for task in demo_tasks]
    )
    monkeypatch.setattr(
        tasks_page, "_load_defined_projects", lambda *args, **kwargs: []
    )

    client = TestClient(app)
    response = client.get(f"/manage-tasks-chunk?offset={offset}&limit={limit}")
    assert response.status_code == 200

    payload = response.json()
    expected_next_offset = min(len(demo_tasks), offset + limit)
    assert payload["nextOffset"] == expected_next_offset
    assert payload["hasMore"] == expected_has_more

    html = payload["html"] or ""
    assert "data-task-details" in html
    for title in expected_titles:
        assert title in html
