"""FastAPI router for interacting with the OpenAI API."""

from datetime import date
from fastapi import APIRouter, Body

from openai_client import ask_chatgpt
from prompt_renderer import render_prompt
from tasks import read_tasks
from energy import read_entries
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
async def plan_endpoint():
    """Generate a daily plan using incomplete tasks and today's energy log."""
    tasks = [t for t in read_tasks() if t.get("status") != "complete"]
    entries = read_entries()
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
