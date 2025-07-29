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
from tasks import read_tasks, mark_tasks_complete

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
    return templates.TemplateResponse(
        "tasks.html", {"request": request, "tasks": tasks}
    )


@router.post("/daily-tasks")
def complete_tasks(task_id: List[int] = Form([])):
    """Mark selected tasks as complete and persist updates."""
    logger.info("POST /daily-tasks ids=%s", task_id)
    mark_tasks_complete([int(i) for i in task_id])
    return RedirectResponse("/daily-tasks", status_code=303)
