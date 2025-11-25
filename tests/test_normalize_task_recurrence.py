"""Tests for the recurrence normalizer script."""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.normalize_task_recurrence as normalizer
from tasks import write_tasks, read_tasks_raw


def test_normalize_saved_tasks_updates_recurrence(tmp_path: Path):
    target = tmp_path / "tasks.yaml"
    write_tasks(
        [{"id": 1, "title": "custom", "recurrence": "First Saturday"}],
        target,
    )
    changed = normalizer.normalize_saved_tasks(target)
    assert changed
    assert read_tasks_raw(target, log=False)[0]["recurrence"] == "first saturday"


def test_normalize_saved_tasks_skips_unknown(tmp_path: Path):
    target = tmp_path / "tasks.yaml"
    write_tasks([{"id": 2, "title": "beta", "recurrence": "sometimes"}], target)
    changed = normalizer.normalize_saved_tasks(target)
    assert not changed
    assert read_tasks_raw(target, log=False)[0]["recurrence"] == "sometimes"
