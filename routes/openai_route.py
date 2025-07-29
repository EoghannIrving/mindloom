"""FastAPI router for interacting with the OpenAI API."""

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
    """Generate a daily plan using saved tasks and the latest energy log."""
    tasks = read_tasks()
    entries = read_entries()
    latest = entries[-1] if entries else {}
    variables = {
        "tasks": tasks,
        "energy": latest.get("energy", 3),
        "time_blocks": latest.get("time_blocks", 0),
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
