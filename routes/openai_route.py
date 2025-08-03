"""FastAPI router for interacting with the OpenAI API."""

from datetime import date
from pathlib import Path
from typing import List
import logging

from calendar_integration import load_events
from fastapi import APIRouter, Body, Query

from openai_client import ask_chatgpt
from prompt_renderer import render_prompt
from tasks import upcoming_tasks
from energy import read_entries
from planner import save_plan, filter_tasks_by_energy, filter_tasks_by_plan
from config import PROJECT_ROOT, config

router = APIRouter()

LOG_FILE = Path(config.LOG_DIR) / "openai_api.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@router.post("/ask")
async def ask_endpoint(data: dict = Body(...)):
    """Send the provided prompt to ChatGPT and return the response."""
    prompt: str = data.get("prompt", "")
    if not prompt:
        logger.warning("POST /ask missing prompt")
        return {"error": "Prompt is required"}

    logger.info("POST /ask prompt_length=%s", len(prompt))
    response = await ask_chatgpt(prompt)
    logger.info("POST /ask response_length=%s", len(response))
    return {"response": response}


@router.post("/plan")
async def plan_endpoint(intensity: str = Query("medium")):
    """Generate a daily plan using incomplete tasks and today's energy log."""
    logger.info("POST /plan intensity=%s", intensity)
    intensity = intensity.lower()
    if intensity not in {"light", "medium", "full"}:
        logger.warning("Invalid intensity %s, defaulting to medium", intensity)
        intensity = "medium"

    tasks = upcoming_tasks()
    logger.info("Loaded %d upcoming tasks", len(tasks))

    entries = read_entries()
    logger.info("Loaded %d energy entries", len(entries))
    latest = entries[-1] if entries else {}
    energy_level = latest.get("energy")
    if energy_level is not None:
        logger.info("Filtering tasks by energy=%s", energy_level)
        tasks = filter_tasks_by_energy(tasks, int(energy_level))
        logger.info("Tasks after energy filter: %d", len(tasks))
    else:
        logger.info("No energy entry found; skipping energy filter")

    selector_template = PROJECT_ROOT / "prompts" / "plan_intensity_selector.txt"
    selector_prompt = render_prompt(
        str(selector_template), {"tasks": tasks, "intensity": intensity}
    )
    logger.debug("Selector prompt: %s", selector_prompt)
    selector_response = await ask_chatgpt(selector_prompt)
    logger.info("Selector response: %s", selector_response)
    tasks = filter_tasks_by_plan(tasks, selector_response)
    logger.info("Tasks after plan filter: %d", len(tasks))

    events = load_events(date.today(), date.today())
    logger.info("Loaded %d calendar events", len(events))
    busy_blocks: List[str] = [
        f"{ev.start.strftime('%H:%M')}-{ev.end.strftime('%H:%M')}" for ev in events
    ]
    logger.debug("Busy blocks: %s", busy_blocks)

    today = date.today().isoformat()
    today_entry = next(
        (e for e in reversed(entries) if e.get("date") == today),
        {},
    )
    logger.debug("Today's entry: %s", today_entry)
    variables = {
        "tasks": tasks,
        "energy": today_entry.get("energy", 0),
        "time_blocks": today_entry.get("time_blocks", 0),
        "calendar": busy_blocks,
    }
    logger.debug("Prompt variables: %s", variables)
    template = PROJECT_ROOT / "prompts" / "morning_planner.txt"
    prompt = render_prompt(str(template), variables)
    logger.debug("Final plan prompt: %s", prompt)
    plan = await ask_chatgpt(prompt)
    logger.info("Generated plan: %s", plan)
    save_plan(plan)
    logger.info("Plan saved")
    return {"plan": plan}


@router.post("/goal-breakdown")
async def goal_breakdown_endpoint(data: dict = Body(...)):
    """Expand a high-level goal into actionable tasks."""
    goal_text: str = data.get("goal", "")
    if not goal_text:
        logger.warning("POST /goal-breakdown missing goal")
        return {"error": "Goal is required"}
    logger.info("POST /goal-breakdown goal_length=%s", len(goal_text))
    template = PROJECT_ROOT / "prompts" / "task_explainer.txt"
    prompt = render_prompt(str(template), {"goal_text": goal_text})
    logger.debug("Goal breakdown prompt: %s", prompt)
    result = await ask_chatgpt(prompt)
    logger.info("POST /goal-breakdown response_length=%s", len(result))
    return {"tasks": result}
