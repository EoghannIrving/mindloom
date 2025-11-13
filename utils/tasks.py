"""Shared task helpers for filtering, energy defaults, and option builders."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, List, Mapping, Optional

ENERGY_MAPPING: Mapping[str, int] = {"low": 1, "medium": 3, "high": 5}
DEFAULT_ENERGY_LEVEL = 3


def normalize_filter_value(value: Any) -> Optional[str]:
    """Return a stripped lowercase string or ``None`` if the value is empty."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _matches_filter(task_value: Any, filter_value: str) -> bool:
    normalized = normalize_filter_value(task_value)
    if normalized is None:
        return False
    return normalized.casefold() == filter_value.casefold()


def filter_tasks_by_metadata(
    tasks: Iterable[Mapping[str, Any]],
    *,
    project: Optional[str] = None,
    area: Optional[str] = None,
    exclude_completed: bool = False,
    project_contains: bool = False,
    area_contains: bool = False,
) -> List[Mapping[str, Any]]:
    """Return tasks matching the provided metadata filters."""

    project_filter = normalize_filter_value(project)
    area_filter = normalize_filter_value(area)
    results: List[Mapping[str, Any]] = []
    for task in tasks:
        if (
            exclude_completed
            and str(task.get("status", "")).strip().lower() == "complete"
        ):
            continue
        if project_filter:
            if project_contains:
                candidate = normalize_filter_value(task.get("project"))
                if candidate is None or project_filter not in candidate.casefold():
                    continue
            elif not _matches_filter(task.get("project"), project_filter):
                continue
        if area_filter:
            if area_contains:
                candidate = normalize_filter_value(task.get("area"))
                if candidate is None or area_filter not in candidate.casefold():
                    continue
            elif not _matches_filter(task.get("area"), area_filter):
                continue
        results.append(task)
    return results


def build_option_values(tasks: Iterable[Mapping[str, Any]], field: str) -> List[str]:
    """Return unique, sorted string values extracted from ``field``."""

    values = {
        cleaned
        for task in tasks
        for cleaned in [str(task.get(field) or "").strip()]
        if cleaned
    }
    return sorted(values)


def unique_sorted_values(tasks: Iterable[Mapping[str, Any]], field: str) -> List[Any]:
    """Return sorted unique values for a given field, preserving raw types."""

    values = {task.get(field) for task in tasks if task.get(field) is not None}
    return sorted(values)


def matches_search_query(
    task: Mapping[str, Any], query: Optional[str], fields: Iterable[str]
) -> bool:
    """Return ``True`` if the query appears in at least one of the fields."""

    normalized_query = normalize_filter_value(query)
    if not normalized_query:
        return True
    term = normalized_query.casefold()
    for field in fields:
        value = str(task.get(field, "")).lower()
        if term in value:
            return True
    return False


def resolve_energy_cost(
    task: Mapping[str, Any], *, mapping: Mapping[str, int] = ENERGY_MAPPING
) -> int:
    """Normalize the stored energy cost or derive it from effort."""

    cost = task.get("energy_cost")
    if cost is None:
        effort = str(task.get("effort") or "low").lower()
        return mapping.get(effort, mapping["low"])
    try:
        return int(cost)
    except (TypeError, ValueError):
        effort = str(task.get("effort") or "low").lower()
        return mapping.get(effort, mapping["low"])


def _parse_iso_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def task_due_date(task: Mapping[str, Any]) -> Optional[date]:
    return _parse_iso_date(task.get("next_due") or task.get("due"))


def annotate_task(
    task: Mapping[str, Any], today: Optional[date] = None
) -> dict[str, Any]:
    today = today or date.today()
    item = dict(task)
    due_date = task_due_date(item)
    item["due_date_normalized"] = due_date.isoformat() if due_date else None
    status = str(item.get("status", "")).lower()
    is_complete = status == "complete"
    item["is_overdue"] = bool(due_date and due_date < today and not is_complete)
    item["is_due_today"] = bool(due_date and due_date == today and not is_complete)
    item["_due_sort_key"] = due_date or date.max
    return item


def sort_tasks(
    tasks: Iterable[Mapping[str, Any]], mode: str = "due_asc"
) -> List[Mapping[str, Any]]:
    def due_key(task: Mapping[str, Any]) -> tuple[date, str]:
        return (
            task.get("_due_sort_key", date.max),
            str(task.get("title", "")),
        )

    if mode == "due_asc":
        return sorted(tasks, key=due_key)
    if mode == "overdue_first":
        return sorted(
            tasks,
            key=lambda task: (
                0 if task.get("is_overdue") else 1,
                task.get("_due_sort_key", date.max),
                str(task.get("title", "")),
            ),
        )
    if mode == "status":
        return sorted(
            tasks,
            key=lambda task: (
                str(task.get("status", "")),
                task.get("_due_sort_key", date.max),
                str(task.get("title", "")),
            ),
        )
    return list(tasks)
