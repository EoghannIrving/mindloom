"""Simple web interface for Mindloom."""

# pylint: disable=duplicate-code

import logging
from pathlib import Path

from datetime import date
from fastapi import APIRouter, Request, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import config, PROJECT_ROOT
from prompt_renderer import render_prompt
from tasks import read_tasks, due_within
from energy import read_entries


router = APIRouter()
templates = Jinja2Templates(directory=PROJECT_ROOT / "templates")

LOG_FILE = Path(config.LOG_DIR) / "web.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Return the basic web interface."""
    logger.info("GET /")
    prompts_dir = PROJECT_ROOT / "prompts"
    prompt_files = [
        p.relative_to(prompts_dir).as_posix() for p in prompts_dir.rglob("*.txt")
    ]
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "prompt_files": prompt_files},
    )


@router.post("/render-prompt")
def render_prompt_endpoint(data: dict = Body(...)):
    """Render a prompt template with optional variables."""
    template_name = data.get("template")
    variables = data.get("variables", {})

    # automatically inject tasks and energy data if not provided
    tasks = read_tasks()
    completed = [t for t in tasks if t.get("status") == "complete"]
    is_morning = Path(template_name).name == "morning_planner.txt"
    if is_morning:
        tasks = due_within([t for t in tasks if t.get("status") != "complete"], days=7)

    if "tasks" not in variables:
        variables["tasks"] = tasks
    if "completed_tasks" not in variables:
        variables["completed_tasks"] = completed

    entries = read_entries()
    if is_morning:
        today = date.today().isoformat()
        latest = next((e for e in reversed(entries) if e.get("date") == today), {})
    else:
        latest = entries[-1] if entries else {}

    variables.setdefault("energy", latest.get("energy", 0))
    variables.setdefault("mood", latest.get("mood", ""))
    variables.setdefault("time_blocks", latest.get("time_blocks", 0))

    prompts_dir = PROJECT_ROOT / "prompts"
    template_path = prompts_dir / template_name
    result = render_prompt(str(template_path), variables)
    return {"result": result}
