"""Web page and API for daily tasks."""

# pylint: disable=duplicate-code

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import yaml

from config import config, PROJECT_ROOT
from energy import MOOD_EMOJIS, latest_entry, read_entries
from tasks import read_tasks, write_tasks, mark_tasks_complete, complete_task
from planner import read_plan, parse_plan_reasons, _clean
from parse_projects import write_tasks_to_projects
from pydantic import BaseModel, Field

router = APIRouter()
templates = Jinja2Templates(directory=PROJECT_ROOT / "templates")

LOG_FILE = Path(config.LOG_DIR) / "tasks_page.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


ENERGY_MAPPING = {"low": 1, "medium": 3, "high": 5}
MOOD_CAPACITY_ADJUSTMENTS = {
    "Sad": -1,
    "Meh": -0.5,
    "Okay": 0,
    "Calm": 0.5,
    "Joyful": 1,
}
DEFAULT_ENERGY_LEVEL = 3
DEFAULT_STATUS_FILTER = "active"


class TaskCreateRequest(BaseModel):
    """Schema for creating a task entry."""

    title: str = Field(..., min_length=1)
    project: Optional[str] = None
    area: Optional[str] = None
    type: Optional[str] = Field(default="task", description="Task category")
    effort: Optional[str] = Field(default="low", description="Estimated effort")
    energy_cost: Optional[int] = None
    executive_trigger: Optional[str] = None
    recurrence: Optional[str] = None
    due: Optional[date] = None
    last_completed: Optional[date] = None
    status: Optional[str] = Field(default="active", description="Task status")
    notes: Optional[str] = None


def _strip_runtime_fields(task: dict) -> dict:
    """Remove transient recurrence metadata before persisting."""

    return {k: v for k, v in task.items() if k not in {"next_due", "due_today"}}


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreateRequest):
    """Create a task, assigning the next available identifier."""

    logger.info(
        "POST /tasks payload_received title_length=%s project_provided=%s",
        len(payload.title),
        bool(payload.project),
    )
    logger.debug("POST /tasks payload: %s", payload.model_dump())

    existing_tasks = read_tasks()
    persisted_tasks: List[dict] = []
    max_id = 0
    for item in existing_tasks:
        clean = _strip_runtime_fields(dict(item))
        persisted_tasks.append(clean)
        try:
            candidate = int(clean.get("id", 0))
        except (TypeError, ValueError):
            candidate = 0
        max_id = max(max_id, candidate)

    new_id = max_id + 1
    task_data = payload.model_dump(exclude_unset=True)

    for field in ("due", "last_completed"):
        value = task_data.get(field)
        if isinstance(value, date):
            task_data[field] = value.isoformat()
        elif value in (None, ""):
            task_data.pop(field, None)

    task = {k: v for k, v in task_data.items() if v is not None}

    effort_value = task.get("effort") or "low"
    if isinstance(effort_value, str):
        effort_key = effort_value.lower()
    else:
        effort_key = str(effort_value).lower()
        effort_value = str(effort_value)
    task["effort"] = effort_value

    energy_value = task.get("energy_cost")
    if energy_value is None:
        task["energy_cost"] = ENERGY_MAPPING.get(effort_key, ENERGY_MAPPING["low"])
    else:
        try:
            task["energy_cost"] = int(energy_value)
        except (TypeError, ValueError):
            task["energy_cost"] = ENERGY_MAPPING.get(effort_key, ENERGY_MAPPING["low"])

    if not task.get("type"):
        task["type"] = "task"
    if not task.get("status"):
        task["status"] = "active"

    if not task.get("recurrence"):
        task.pop("recurrence", None)

    if not task.get("notes"):
        task.pop("notes", None)

    if not task.get("project"):
        task.pop("project", None)

    if not task.get("area"):
        task.pop("area", None)

    task["id"] = new_id

    persisted_tasks.append(task)
    write_tasks(persisted_tasks)

    if task.get("project"):
        write_tasks_to_projects(persisted_tasks)

    return task


@router.get("/daily-tasks", response_class=HTMLResponse)
def tasks_page(request: Request):
    """Display all saved tasks with checkboxes."""
    logger.info("GET /daily-tasks")
    today = date.today()
    tasks = read_tasks()
    plan = read_plan()
    reasons = parse_plan_reasons(plan)
    energy_entries = read_entries()
    latest_entry = _latest_energy_entry(energy_entries)
    energy_summary = _summarize_energy_entry(latest_entry)

    due_today = _collect_due_today_tasks(tasks, today, reasons)
    achievable_tasks, over_limit_tasks = _score_due_tasks(
        due_today, energy_summary["available_energy"]
    )

    return templates.TemplateResponse(
        "tasks.html",
        {
            "request": request,
            "achievable_tasks": achievable_tasks,
            "over_limit_tasks": over_limit_tasks,
            "energy_summary": energy_summary,
            "today": today,
        },
    )


@router.post("/daily-tasks")
def complete_tasks(task_id: List[int] = Form([])):
    """Mark selected tasks as complete and persist updates."""
    logger.info("POST /daily-tasks completed_count=%s", len(task_id))
    if task_id:
        logger.debug("POST /daily-tasks ids=%s", task_id)
    mark_tasks_complete([int(i) for i in task_id])
    return RedirectResponse("/daily-tasks", status_code=303)


def _parse_due_date(value: str | date | None) -> date | None:
    """Convert stored due date strings to ``date`` objects when possible."""

    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _task_due_date(task: dict) -> date | None:
    """Determine the next relevant due date for a task."""

    return _parse_due_date(task.get("next_due") or task.get("due"))


def _annotate_task(task: dict, today: date) -> dict:
    """Attach sorting helpers and due date flags to a task."""

    due_date = _task_due_date(task)
    task["due_date_normalized"] = due_date.isoformat() if due_date else None
    status = str(task.get("status", "")).lower()
    is_complete = status == "complete"
    task["is_overdue"] = bool(due_date and due_date < today and not is_complete)
    task["is_due_today"] = bool(due_date and due_date == today and not is_complete)
    task["_due_sort_key"] = due_date or date.max
    return task


def _sort_tasks(tasks: list[dict], mode: str) -> list[dict]:
    """Sort tasks according to the requested mode."""

    if mode == "due_asc":
        return sorted(
            tasks,
            key=lambda task: (
                task.get("_due_sort_key", date.max),
                str(task.get("title", "")),
            ),
        )
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
        return tasks


def _latest_energy_entry(entries: list[dict] | None = None) -> dict | None:
    """Return the most recent energy entry, if any."""

    records = entries or read_entries()
    return latest_entry(records)


def _summarize_energy_entry(entry: dict | None) -> dict:
    """Translate an energy entry into context used on the UI."""

    summary = {
        "entry": entry,
        "energy": DEFAULT_ENERGY_LEVEL,
        "available_energy": float(DEFAULT_ENERGY_LEVEL),
        "available_display": float(DEFAULT_ENERGY_LEVEL),
        "mood": "Okay",
        "emoji": MOOD_EMOJIS.get("Okay", ""),
        "has_entry": False,
        "message": "Record today's energy to unlock personalized ordering.",
    }
    if not entry:
        return summary

    try:
        energy_value = int(entry.get("energy", DEFAULT_ENERGY_LEVEL))
    except (TypeError, ValueError):
        energy_value = DEFAULT_ENERGY_LEVEL

    raw_mood = str(entry.get("mood") or "Okay").capitalize()
    mood_value = raw_mood if raw_mood else "Okay"
    adjustment = MOOD_CAPACITY_ADJUSTMENTS.get(mood_value, 0)
    available_energy = max(0.5, energy_value + adjustment)

    summary.update(
        {
            "energy": energy_value,
            "available_energy": available_energy,
                "available_display": min(5, available_energy),
                "mood": mood_value,
                "emoji": MOOD_EMOJIS.get(mood_value, ""),
                "recorded_at": entry.get("recorded_at"),
                "has_entry": True,
                "message": f"Based on {energy_value} energy and {mood_value} mood.",
            }
        )
    return summary


def _resolve_energy_cost(task: dict) -> int:
    """Normalize the stored energy cost to an integer."""

    value = task.get("energy_cost")
    if value is None:
        effort = str(task.get("effort") or "low").lower()
        return ENERGY_MAPPING.get(effort, ENERGY_MAPPING["low"])
    try:
        return int(value)
    except (TypeError, ValueError):
        effort = str(task.get("effort") or "low").lower()
        return ENERGY_MAPPING.get(effort, ENERGY_MAPPING["low"])


def _collect_due_today_tasks(
    tasks: list[dict], today: date, reasons: dict[str, str]
) -> list[dict]:
    """Return the subset of incomplete tasks explicitly due today."""

    due_tasks: list[dict] = []
    for original in tasks:
        if str(original.get("status", "")).lower() == "complete":
            continue
        due_date = _task_due_date(original)
        if not due_date or due_date != today:
            continue
        task = dict(original)
        task["due_date_normalized"] = due_date.isoformat()
        title_key = _clean(str(task.get("title", "")))
        task["reason"] = reasons.get(title_key, "")
        due_tasks.append(task)
    return due_tasks


def _score_due_tasks(
    tasks: list[dict], available_energy: float
) -> tuple[list[dict], list[dict]]:
    """Split due tasks into achievable and over-limit buckets."""

    achievable: list[dict] = []
    over_limit: list[dict] = []
    for task in tasks:
        cost = _resolve_energy_cost(task)
        gap = available_energy - cost
        annotated = dict(task)
        annotated["energy_cost"] = cost
        annotated["capacity_gap"] = gap
        if gap >= 0:
            achievable.append(annotated)
        else:
            over_limit.append(annotated)

    achievable.sort(
        key=lambda candidate: (
            candidate["capacity_gap"],
            -candidate["energy_cost"],
            str(candidate.get("title", "")).lower(),
        )
    )
    over_limit.sort(
        key=lambda candidate: (
            -candidate["energy_cost"],
            str(candidate.get("title", "")).lower(),
        )
    )
    return achievable, over_limit


def _load_defined_projects(output_path: Path | str | None = None) -> list[str]:
    """Return project slugs defined in projects.yaml."""

    target = output_path or config.OUTPUT_PATH
    path = Path(target).expanduser()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or []
    except FileNotFoundError:
        return []
    except yaml.YAMLError as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to parse %s: %s", path, exc)
        return []
    except OSError as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to read %s: %s", path, exc)
        return []

    if not isinstance(payload, list):
        logger.warning("Unexpected projects format in %s", path)
        return []

    projects: list[str] = []
    for entry in payload:
        if isinstance(entry, dict):
            candidate = entry.get("path") or entry.get("slug")
            if candidate:
                projects.append(str(candidate))
    return projects


@router.get("/manage-tasks", response_class=HTMLResponse)
def manage_tasks_page(request: Request):
    """Display editable list of all tasks."""
    logger.info("GET /manage-tasks")
    tasks = read_tasks()

    query = request.query_params.get("q", "").strip()
    status_param_provided = "status" in request.query_params
    selected_status = request.query_params.get("status", "")
    selected_status = selected_status.strip()
    if not status_param_provided and not selected_status:
        selected_status = DEFAULT_STATUS_FILTER
    selected_project = request.query_params.get("project", "").strip()
    selected_area = request.query_params.get("area", "").strip()
    selected_type = request.query_params.get("type", "").strip()
    sort_mode = (request.query_params.get("sort") or "").strip() or "due_asc"
    today = date.today()

    def _matches(task: dict) -> bool:
        if query:
            haystacks = [
                str(task.get("title", "")),
                str(task.get("notes", "")),
                str(task.get("project", "")),
                str(task.get("area", "")),
                str(task.get("type", "")),
            ]
            if not any(query.lower() in haystack.lower() for haystack in haystacks):
                return False
        task_status = str(task.get("status", "")).strip()
        if selected_status:
            if task_status != selected_status:
                return False
        if selected_project and str(task.get("project", "")) != selected_project:
            return False
        if selected_area and str(task.get("area", "")) != selected_area:
            return False
        if selected_type and str(task.get("type", "")) != selected_type:
            return False
        return True

    filtered_tasks = [
        _annotate_task(dict(task), today) for task in tasks if _matches(task)
    ]
    sorted_tasks = _sort_tasks(filtered_tasks, sort_mode)

    projects_from_tasks = {
        str(project) for project in (task.get("project") for task in tasks) if project
    }
    defined_projects = {str(project) for project in _load_defined_projects() if project}
    projects = sorted(projects_from_tasks | defined_projects)
    areas = sorted({t.get("area") for t in tasks if t.get("area")})
    task_types = sorted({t.get("type") for t in tasks if t.get("type")})
    statuses = sorted({t.get("status") for t in tasks if t.get("status")})
    sort_options = [
        ("due_asc", "Due date (oldest first)"),
        ("overdue_first", "Overdue first"),
        ("status", "Status"),
    ]

    return templates.TemplateResponse(
        "manage_tasks.html",
        {
            "request": request,
            "tasks": sorted_tasks,
            "project_options": projects,
            "area_options": areas,
            "type_options": task_types,
            "status_options": statuses,
            "sort_options": sort_options,
            "search_query": query,
            "selected_status": selected_status,
            "selected_project": selected_project,
            "selected_area": selected_area,
            "selected_type": selected_type,
            "selected_sort": sort_mode,
        },
    )


@router.post("/manage-tasks")
async def save_tasks(request: Request):
    """Persist edited task fields back to tasks.yaml."""
    logger.info("POST /manage-tasks")
    form = await request.form()
    tasks = read_tasks()
    submitted_ids: set[str] = set()
    deleted_ids: set[str] = set()
    completed_ids: set[str] = set()
    for key in form.keys():
        if "-" not in key:
            continue
        field, task_id = key.rsplit("-", 1)
        if not task_id:
            continue
        submitted_ids.add(task_id)
        if field == "delete" and form.get(key) == "1":
            deleted_ids.add(task_id)
        if field == "complete" and form.get(key) == "1":
            completed_ids.add(task_id)
    fields = [
        "title",
        "project",
        "area",
        "type",
        "effort",
        "energy_cost",
        "executive_trigger",
        "recurrence",
        "due",
        "last_completed",
        "status",
    ]

    def _update_field(task: dict, field: str, value: str | None) -> None:
        if value:
            if field == "energy_cost":
                try:
                    task[field] = int(value)
                except ValueError:
                    task[field] = str(value)
            else:
                task[field] = str(value)
        else:
            if field != "title":
                task.pop(field, None)
            else:
                task[field] = ""

    remaining_tasks: list[dict] = []
    cleared_projects: set[str] = set()

    for task in tasks:
        tid = str(task.get("id"))
        if tid in deleted_ids:
            project = task.get("project")
            if project:
                cleared_projects.add(str(project))
            continue
        if tid not in submitted_ids:
            task.pop("next_due", None)
            task.pop("due_today", None)
            remaining_tasks.append(task)
            continue
        for field in fields:
            key = f"{field}-{tid}"
            _update_field(task, field, form.get(key))
        if tid in completed_ids:
            complete_task(task)
        task.pop("next_due", None)
        task.pop("due_today", None)
        remaining_tasks.append(task)
    write_tasks(remaining_tasks)
    write_tasks_to_projects(remaining_tasks, cleared_projects=cleared_projects)

    filters = {
        name: form.get(name)
        for name in ("q", "status", "project", "area", "type", "sort")
    }
    query = {key: value for key, value in filters.items() if value}
    redirect_url = request.url_for("manage_tasks_page")
    if query:
        redirect_url = f"{redirect_url}?{urlencode(query)}"

    return RedirectResponse(redirect_url, status_code=303)
