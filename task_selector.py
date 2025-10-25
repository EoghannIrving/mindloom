"""Utilities for selecting the next task recommendation."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

MOOD_ENERGY_TARGETS = {
    "sad": 1,
    "meh": 2,
    "okay": 3,
    "joyful": 5,
}

EXECUTIVE_TRIGGER_WEIGHTS = {"low": 0, "medium": 1, "high": 2}

MOOD_EXECUTIVE_TOLERANCE = {
    "sad": 0,
    "meh": 1,
    "okay": 1,
    "joyful": 2,
}

DEFAULT_EXECUTIVE_TOLERANCE = 1


def effective_energy_level(
    energy_level: Optional[int], mood: Optional[str], default: int = 3
) -> int:
    """Return the target energy level based on energy and mood."""

    mood_key = (mood or "").strip().lower()
    mood_target = MOOD_ENERGY_TARGETS.get(mood_key)

    values: List[int] = []
    for raw in (energy_level, mood_target):
        if raw is None:
            continue
        try:
            values.append(int(raw))
        except (TypeError, ValueError):
            continue

    if not values:
        return default
    if len(values) == 1:
        combined = values[0]
    else:
        combined = min(values)

    return max(0, combined)


def _due_date_value(task: Dict[str, Any]) -> date:
    date_str = task.get("next_due") or task.get("due")
    if not date_str:
        return date.max
    try:
        return date.fromisoformat(str(date_str))
    except ValueError:
        return date.max


def _energy_cost(task: Dict[str, Any]) -> Optional[int]:
    try:
        cost = task.get("energy_cost")
        return int(cost)
    except (TypeError, ValueError):
        return None


def _executive_weight(task: Dict[str, Any]) -> Optional[int]:
    value = task.get("executive_trigger")
    if value is None:
        return None
    key = str(value).strip().lower()
    return EXECUTIVE_TRIGGER_WEIGHTS.get(key)


def select_next_task(
    tasks: List[Dict[str, Any]],
    mood: Optional[str],
    energy_level: Optional[int],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Return the next task and reasoning using task heuristics."""

    if not tasks:
        return None, None

    mood_key = (mood or "").lower()
    target_energy = effective_energy_level(energy_level, mood)

    executive_tolerance = MOOD_EXECUTIVE_TOLERANCE.get(
        mood_key, DEFAULT_EXECUTIVE_TOLERANCE
    )

    scored: List[Tuple[Dict[str, Any], Dict[str, Any], Tuple[Any, ...]]] = []

    for task in tasks:
        due = _due_date_value(task)
        cost = _energy_cost(task)
        energy_penalty = abs(cost - target_energy) if cost is not None else 0

        exec_weight = _executive_weight(task)
        executive_penalty = (
            max(0, exec_weight - executive_tolerance) if exec_weight is not None else 0
        )

        total_penalty = energy_penalty + executive_penalty

        reasoning = {
            "due_date": due.isoformat() if due != date.max else None,
            "energy_penalty": energy_penalty,
            "executive_penalty": executive_penalty,
            "total_score": total_penalty,
        }

        scored.append(
            (
                task,
                reasoning,
                (
                    due,
                    total_penalty,
                    energy_penalty,
                    executive_penalty,
                    cost if cost is not None else target_energy,
                    exec_weight if exec_weight is not None else executive_tolerance,
                ),
            )
        )

    selected_task, reasoning, _ = min(scored, key=lambda item: item[2])
    return selected_task, reasoning
