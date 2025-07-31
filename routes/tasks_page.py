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
from planner import read_plan, filter_tasks_by_plan

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
    plan_text = read_plan()
    tasks = filter_tasks_by_plan(tasks, plan_text)
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
    return templates.TemplateResponse(
        "manage_tasks.html", {"request": request, "tasks": tasks}
    )


@router.post("/manage-tasks")
async def save_tasks(request: Request):
    """Persist edited task fields back to tasks.yaml."""
    logger.info("POST /manage-tasks")
    form = await request.form()
    tasks = read_tasks()
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

    for task in tasks:
        tid = str(task.get("id"))
        for field in fields:
            key = f"{field}-{tid}"
            if key in form:
                value = form[key]
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
        task.pop("next_due", None)
        task.pop("due_today", None)
    write_tasks(tasks)
    return RedirectResponse("/manage-tasks", status_code=303)
