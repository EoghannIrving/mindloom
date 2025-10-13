"""Unit tests for planner utilities with YAML plans."""

from __future__ import annotations

import sys
from pathlib import Path

# pylint: disable=wrong-import-position, import-outside-toplevel
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planner import save_plan, read_plan, filter_tasks_by_plan, parse_plan_reasons
from planner import filter_tasks_by_energy


def test_save_and_read_plan(tmp_path: Path):
    """Saving then loading should return the original data."""
    path = tmp_path / "plan.yaml"
    data = [
        {"title": "Do things", "reason": "because"},
        {"title": "Write code", "reason": "finish feature"},
    ]
    save_plan(data, path)
    assert read_plan(path) == data


def test_filter_tasks_by_plan():
    """Only tasks mentioned in the plan should be returned."""
    tasks = [{"title": "Write code"}, {"title": "Exercise"}]
    plan = [{"title": "Write code", "reason": ""}]
    filtered = filter_tasks_by_plan(tasks, plan)
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Write code"


def test_filter_tasks_ignores_punctuation():
    """Titles should match even when the plan omits punctuation."""
    tasks = [{"title": "Check garden hose."}, {"title": "Write code"}]
    plan = [{"title": "Check garden hose", "reason": ""}]
    filtered = filter_tasks_by_plan(tasks, plan)
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Check garden hose."


def test_parse_plan_reasons():
    """parse_plan_reasons should map titles to explanations."""
    plan = [
        {"title": "Write code", "reason": "finish feature"},
        {"title": "Exercise", "reason": "stay healthy"},
    ]
    reasons = parse_plan_reasons(plan)
    assert reasons["write code"] == "finish feature"
    assert reasons["exercise"] == "stay healthy"


def test_plan_with_mixed_entries():
    """Plans with dicts using task/name keys and bare strings should work."""
    tasks = [
        {"title": "Write code"},
        {"title": "Exercise"},
        {"title": "Meditate"},
    ]
    plan = [
        {"task": "Write code", "reason": "finish feature"},
        "Exercise",
        {"name": "Meditate", "reason": "calm mind"},
    ]
    filtered = filter_tasks_by_plan(tasks, plan)
    assert {t["title"] for t in filtered} == {"Write code", "Exercise", "Meditate"}

    reasons = parse_plan_reasons(plan)
    assert reasons["write code"] == "finish feature"
    assert reasons["exercise"] == ""
    assert reasons["meditate"] == "calm mind"


def test_filter_tasks_by_energy():
    """Tasks exceeding available energy should be removed."""
    tasks = [
        {"title": "Hard", "energy_cost": 4},
        {"title": "Easy", "energy_cost": 2},
    ]
    filtered = filter_tasks_by_energy(tasks, 2)
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Easy"
