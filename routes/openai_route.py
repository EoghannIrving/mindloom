"""FastAPI router for interacting with the OpenAI API."""

from datetime import date
from fastapi import APIRouter, Body, Query

from openai_client import ask_chatgpt
from prompt_renderer import render_prompt
from tasks import upcoming_tasks
from energy import read_entries
from planner import save_plan, filter_tasks_by_energy, filter_tasks_by_plan
from config import PROJECT_ROOT

router = APIRouter()


@router.post("/ask")
async def ask_endpoint(data: dict = Body(...)):
    """Send the provided prompt to ChatGPT and return the response."""
    prompt: str = data.get("prompt", "")
    if not prompt:
        return {"error": "Prompt is required"}

    response = await ask_chatgpt(prompt)
    return {"response": response}


@router.post("/plan")
async def plan_endpoint(intensity: str = Query("medium")):
    """Generate a daily plan using incomplete tasks and today's energy log."""
    intensity = intensity.lower()
    if intensity not in {"light", "medium", "full"}:
        intensity = "medium"

    tasks = upcoming_tasks()
    entries = read_entries()
    latest = entries[-1] if entries else {}
    energy_level = latest.get("energy")
    if energy_level is not None:
        tasks = filter_tasks_by_energy(tasks, int(energy_level))

    selector_template = PROJECT_ROOT / "prompts" / "plan_intensity_selector.txt"
    selector_prompt = render_prompt(
        str(selector_template), {"tasks": tasks, "intensity": intensity}
    )
    selector_response = await ask_chatgpt(selector_prompt)
    tasks = filter_tasks_by_plan(tasks, selector_response)

    today = date.today().isoformat()
    today_entry = next(
        (e for e in reversed(entries) if e.get("date") == today),
        {},
    )
    variables = {
        "tasks": tasks,
        "energy": today_entry.get("energy", 0),
        "time_blocks": today_entry.get("time_blocks", 0),
    }
    template = PROJECT_ROOT / "prompts" / "morning_planner.txt"
    prompt = render_prompt(str(template), variables)
    plan = await ask_chatgpt(prompt)
    save_plan(plan)
    return {"plan": plan}


@router.post("/goal-breakdown")
async def goal_breakdown_endpoint(data: dict = Body(...)):
    """Expand a high-level goal into actionable tasks."""
    goal_text: str = data.get("goal", "")
    if not goal_text:
        return {"error": "Goal is required"}
    template = PROJECT_ROOT / "prompts" / "task_explainer.txt"
    prompt = render_prompt(str(template), {"goal_text": goal_text})
    result = await ask_chatgpt(prompt)
    return {"tasks": result}
