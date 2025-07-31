"""Unit tests for planner utilities."""

from __future__ import annotations

import sys
from pathlib import Path

# pylint: disable=wrong-import-position, import-outside-toplevel
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planner import save_plan, read_plan, filter_tasks_by_plan, parse_plan_reasons


def test_save_and_read_plan(tmp_path: Path):
    """Saving then loading should return the original text."""
    path = tmp_path / "plan.txt"
    save_plan("Do things", path)
    assert read_plan(path) == "Do things"


def test_filter_tasks_by_plan():
    """Only tasks mentioned in the plan should be returned."""
    tasks = [{"title": "Write code"}, {"title": "Exercise"}]
    plan = "Today you should Write code and relax"
    filtered = filter_tasks_by_plan(tasks, plan)
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Write code"


def test_filter_tasks_ignores_punctuation():
    """Titles should match even when the plan omits punctuation."""
    tasks = [{"title": "Check garden hose."}, {"title": "Write code"}]
    plan = "1. Check garden hose (home) - make sure it works"
    filtered = filter_tasks_by_plan(tasks, plan)
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Check garden hose."


def test_parse_plan_reasons():
    """parse_plan_reasons should map titles to explanations."""
    text = "1. Write code - finish feature\n2. Exercise - stay healthy"
    reasons = parse_plan_reasons(text)
    assert reasons["write code"] == "finish feature"
    assert reasons["exercise"] == "stay healthy"


def test_parse_plan_reasons_em_dash_and_parenthesis():
    """parse_plan_reasons should handle em dashes and numbered parentheses."""
    text = "1) Write code — finish feature\n- Exercise: stay healthy"
    reasons = parse_plan_reasons(text)
    assert reasons["write code"] == "finish feature"
    assert reasons["exercise"] == "stay healthy"
