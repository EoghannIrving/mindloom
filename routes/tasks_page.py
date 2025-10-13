"""Web page and API for daily tasks."""

# pylint: disable=duplicate-code

from __future__ import annotations

import logging
from pathlib import Path
from typing import List
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config import config, PROJECT_ROOT
from tasks import read_tasks, write_tasks, mark_tasks_complete
from planner import read_plan, filter_tasks_by_plan, parse_plan_reasons, _clean

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


@router.get("/daily-tasks", response_class=HTMLResponse)
def tasks_page(request: Request):
    """Display all saved tasks with checkboxes."""
    logger.info("GET /daily-tasks")
    tasks = read_tasks()
    plan = read_plan()
    reasons = parse_plan_reasons(plan)
    tasks = filter_tasks_by_plan(tasks, plan)
    for task in tasks:
        task["reason"] = reasons.get(_clean(str(task.get("title", ""))), "")
    return templates.TemplateResponse(
        "tasks.html", {"request": request, "tasks": tasks}
    )


@router.post("/daily-tasks")
def complete_tasks(task_id: List[int] = Form([])):
    """Mark selected tasks as complete and persist updates."""
    logger.info("POST /daily-tasks ids=%s", task_id)
    mark_tasks_complete([int(i) for i in task_id])
    return RedirectResponse("/daily-tasks", status_code=303)


@router.get("/manage-tasks", response_class=HTMLResponse)
def manage_tasks_page(request: Request):
    """Display editable list of all tasks."""
    logger.info("GET /manage-tasks")
    tasks = read_tasks()

    query = request.query_params.get("q", "").strip()
    selected_status = request.query_params.get("status", "").strip()
    selected_project = request.query_params.get("project", "").strip()
    selected_area = request.query_params.get("area", "").strip()
    selected_type = request.query_params.get("type", "").strip()

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
        if selected_status and str(task.get("status", "")) != selected_status:
            return False
        if selected_project and str(task.get("project", "")) != selected_project:
            return False
        if selected_area and str(task.get("area", "")) != selected_area:
            return False
        if selected_type and str(task.get("type", "")) != selected_type:
            return False
        return True

    filtered_tasks = [task for task in tasks if _matches(task)]

    projects = sorted({t.get("project") for t in tasks if t.get("project")})
    areas = sorted({t.get("area") for t in tasks if t.get("area")})
    task_types = sorted({t.get("type") for t in tasks if t.get("type")})
    statuses = sorted({t.get("status") for t in tasks if t.get("status")})

    return templates.TemplateResponse(
        "manage_tasks.html",
        {
            "request": request,
            "tasks": filtered_tasks,
            "project_options": projects,
            "area_options": areas,
            "type_options": task_types,
            "status_options": statuses,
            "search_query": query,
            "selected_status": selected_status,
            "selected_project": selected_project,
            "selected_area": selected_area,
            "selected_type": selected_type,
        },
    )


@router.post("/manage-tasks")
async def save_tasks(request: Request):
    """Persist edited task fields back to tasks.yaml."""
    logger.info("POST /manage-tasks")
    form = await request.form()
    tasks = read_tasks()
    submitted_ids: set[str] = set()
    for key in form.keys():
        if "-" not in key:
            continue
        _, task_id = key.rsplit("-", 1)
        if task_id:
            submitted_ids.add(task_id)
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

    for task in tasks:
        tid = str(task.get("id"))
        if tid not in submitted_ids:
            task.pop("next_due", None)
            task.pop("due_today", None)
            continue
        for field in fields:
            key = f"{field}-{tid}"
            _update_field(task, field, form.get(key))
        task.pop("next_due", None)
        task.pop("due_today", None)
    write_tasks(tasks)
    return RedirectResponse("/manage-tasks", status_code=303)
