"""Simple web interface for Mindloom."""

# pylint: disable=duplicate-code

from pathlib import Path

from datetime import date
from fastapi import APIRouter, Request, Body, HTTPException
from fastapi.responses import HTMLResponse

from config import config, PROJECT_ROOT
from parse_projects import parse_all_projects
from prompt_renderer import render_prompt
from tasks import read_tasks, task_completion_history, upcoming_tasks
from energy import read_entries
from calendar_integration import load_events
from utils.logging import configure_logger
from utils.template_helpers import create_templates
from utils.tasks import build_option_values


router = APIRouter()
templates = create_templates()

LOG_FILE = Path(config.LOG_DIR) / "web.log"
logger = configure_logger(__name__, LOG_FILE)


def _load_project_area_options():
    active_tasks = [
        task
        for task in read_tasks()
        if str(task.get("status", "")).lower() != "complete"
    ]
    return {
        "project_options": build_option_values(active_tasks, "project"),
        "area_options": build_option_values(active_tasks, "area"),
    }


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Return the basic web interface."""
    logger.info("GET /")
    prompts_dir = PROJECT_ROOT / "prompts"
    prompt_files = [
        p.relative_to(prompts_dir).as_posix() for p in prompts_dir.rglob("*.txt")
    ]
    _due_soon_tasks = upcoming_tasks()
    options = _load_project_area_options()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "prompt_files": prompt_files,
            **options,
        },
    )


@router.get("/projects-page", response_class=HTMLResponse)
def projects_page(request: Request):
    """Render the projects management interface."""
    logger.info("GET /projects-page")
    options = _load_project_area_options()
    raw_projects = parse_all_projects()
    vault_name = Path(config.VAULT_PATH).name
    project_list = []
    for project in raw_projects:
        path_value = project.get("path", "")
        slug_path = Path(path_value)
        if slug_path.parts and slug_path.parts[0] == vault_name:
            slug_value = str(slug_path.relative_to(vault_name))
        else:
            slug_value = str(slug_path)
        entry = dict(project)
        entry["slug"] = slug_value
        project_list.append(entry)
    status_counts = {}
    for project in project_list:
        status_label = (project.get("status") or "Unspecified").title()
        status_counts[status_label] = status_counts.get(status_label, 0) + 1
    return templates.TemplateResponse(
        "projects.html",
        {
            "request": request,
            "project_list": project_list,
            "project_summary": {"total": len(project_list)},
            "project_status_counts": status_counts,
            **options,
        },
    )


@router.get("/energy-trends", response_class=HTMLResponse)
def energy_trends_page(request: Request):
    """Render the energy and mood trends dashboard."""

    logger.info("GET /energy-trends")
    entries = sorted(
        read_entries(),
        key=lambda entry: entry.get("recorded_at") or entry.get("date") or "",
    )
    return templates.TemplateResponse(
        "energy_trends.html",
        {
            "request": request,
            "entries": entries,
        },
    )


@router.get("/task-trends", response_class=HTMLResponse)
def task_trends_page(request: Request):
    """Render a dashboard tracking completed tasks and their energy cost."""

    logger.info("GET /task-trends")
    completions = sorted(
        task_completion_history(),
        key=lambda entry: entry.get("completed_at") or "",
    )
    return templates.TemplateResponse(
        "task_trends.html",
        {
            "request": request,
            "completions": completions,
        },
    )


@router.get("/offline", response_class=HTMLResponse)
def offline_page(request: Request):
    """Render the offline fallback page."""

    logger.info("GET /offline")
    return templates.TemplateResponse("offline.html", {"request": request})


@router.post("/render-prompt")
def render_prompt_endpoint(data: dict = Body(...)):
    """Render a prompt template with optional variables."""
    template_name = data.get("template")
    if not isinstance(template_name, str) or not template_name.strip():
        raise HTTPException(
            status_code=400,
            detail="The 'template' parameter must be a non-empty string.",
        )
    variables = data.get("variables", {})

    # automatically inject tasks and energy data if not provided
    tasks = read_tasks()
    completed = [t for t in tasks if t.get("status") == "complete"]
    is_morning = Path(template_name).name == "morning_planner.txt"
    if is_morning:
        tasks = upcoming_tasks()

    if "tasks" not in variables:
        variables["tasks"] = tasks
    if "completed_tasks" not in variables:
        variables["completed_tasks"] = completed

    entries = read_entries()
    if is_morning:
        today = date.today()
        iso_today = today.isoformat()
        latest = next((e for e in reversed(entries) if e.get("date") == iso_today), {})
        events = load_events(today, today)
        busy_blocks = [
            f"{ev.start.strftime('%H:%M')}-{ev.end.strftime('%H:%M')}" for ev in events
        ]
        variables.setdefault("calendar", busy_blocks)
    else:
        latest = entries[-1] if entries else {}

    variables.setdefault("energy", latest.get("energy", 0))
    variables.setdefault("mood", latest.get("mood", ""))

    prompts_dir = (PROJECT_ROOT / "prompts").resolve()
    requested_path = Path(template_name)

    if requested_path.is_absolute():
        raise HTTPException(status_code=400, detail="Invalid template path.")

    try:
        template_path = (prompts_dir / requested_path).resolve(strict=False)
    except (RuntimeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid template path.")

    try:
        template_path.relative_to(prompts_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template path.")

    if not template_path.is_file():
        raise HTTPException(status_code=404, detail="Template not found.")

    result = render_prompt(str(template_path), variables)
    return {"result": result}
