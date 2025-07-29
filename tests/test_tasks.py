"""Unit tests for the tasks utilities."""

from __future__ import annotations

import sys
from pathlib import Path

# pylint: disable=wrong-import-position, import-outside-toplevel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tasks import write_tasks, read_tasks


def test_write_tasks_creates_parent(tmp_path: Path):
    """write_tasks should create missing parent directories."""
    target = tmp_path / "sub" / "tasks.yaml"
    data = [{"title": "demo"}]
    write_tasks(data, target)
    assert target.exists()
    saved = read_tasks(target)
    assert saved[0]["title"] == "demo"
