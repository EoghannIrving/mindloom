"""FastAPI router for interacting with the OpenAI API."""

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel
import logging

from calendar_integration import load_events
from fastapi import APIRouter, Body, HTTPException, Query

from openai_client import ask_chatgpt
from prompt_renderer import render_prompt
from tasks import upcoming_tasks
from energy import read_entries, record_entry
from planner import save_plan, filter_tasks_by_energy
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

MOOD_ENERGY_TARGETS = {
    "sad": 1,
    "meh": 2,
    "okay": 3,
    "joyful": 4,
}


def _due_date_value(task: Dict[str, Any]) -> date:
    date_str = task.get("next_due") or task.get("due")
    if not date_str:
        return date.max
    try:
        return date.fromisoformat(str(date_str))
    except ValueError:
        return date.max


def _energy_cost(task: Dict[str, Any]) -> Optional[int]:
    try:
        cost = task.get("energy_cost")
        return int(cost)
    except (TypeError, ValueError):
        return None


def _select_next_task(
    tasks: List[Dict[str, Any]], mood: Optional[str], energy_level: Optional[int]
) -> Optional[Dict[str, Any]]:
    if not tasks:
        return None

    mood_key = (mood or "").lower()
    mood_target = MOOD_ENERGY_TARGETS.get(mood_key)
    target_energy = energy_level if energy_level is not None else mood_target
    if target_energy is None:
        target_energy = 3

    def sort_key(task: Dict[str, Any]):
        due = _due_date_value(task)
        cost = _energy_cost(task)
        penalty = abs(cost - target_energy) if cost is not None else target_energy
        return (due, penalty, cost or target_energy)

    return sorted(tasks, key=sort_key)[0]


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


class PlanRequest(BaseModel):
    energy: Optional[int] = None
    mood: Optional[str] = None
    time_blocks: Optional[int] = None


class PlanResponse(BaseModel):
    plan: str
    next_task: Optional[Dict[str, Any]] = None


@router.post("/plan", response_model=PlanResponse)
async def plan_endpoint(
    intensity: str = Query("medium"),
    template: Literal["plan_intensity_selector", "morning_planner"] = Query(
        "morning_planner"
    ),
    mode: Literal["plan", "next_task"] = Query(
        "plan", description="Select 'next_task' to fetch a single recommendation"
    ),
    focus: Optional[Literal["plan", "next_task"]] = Query(
        None,
        description="Alias for the mode parameter, kept for backward compatibility",
    ),
    payload: Optional[PlanRequest] = Body(
        None,
        description="Optional energy, mood and time block data to persist before planning",
    ),
) -> PlanResponse:
    """Generate a plan or task selection based on the chosen template."""
    selected_mode = focus or mode or "plan"
    if selected_mode not in {"plan", "next_task"}:
        logger.warning("Invalid mode %s, defaulting to plan", selected_mode)
        selected_mode = "plan"

    logger.info(
        "POST /plan intensity=%s template=%s mode=%s",
        intensity,
        template,
        selected_mode,
    )
    intensity = intensity.lower()
    if intensity not in {"light", "medium", "full"}:
        logger.warning("Invalid intensity %s, defaulting to medium", intensity)
        intensity = "medium"

    payload_values = (
        payload.energy if payload else None,
        payload.mood if payload else None,
        payload.time_blocks if payload else None,
    )
    has_full_payload = payload is not None and all(
        value is not None for value in payload_values
    )
    has_partial_payload = payload is not None and any(
        value is not None for value in payload_values
    )

    if selected_mode == "next_task" and not has_full_payload:
        logger.warning(
            "Missing energy payload for next_task mode: %s",
            payload.model_dump() if payload else None,
        )
        raise HTTPException(
            status_code=400,
            detail="Energy, mood, and time_blocks are required for next_task mode.",
        )

    recorded_entry: Optional[Dict[str, Any]] = None
    if has_full_payload and payload:
        recorded_entry = record_entry(payload.energy, payload.mood, payload.time_blocks)
        logger.info("Persisted energy entry via API: %s", recorded_entry)
    elif has_partial_payload:
        logger.warning(
            "Partial energy payload provided; skipping record_entry call: %s",
            payload.model_dump(),
        )

    if selected_mode == "next_task":
        tasks = upcoming_tasks(days=0)
        if not tasks:
            logger.info(
                "No tasks due today; expanding next_task search window to default range"
            )
            tasks = upcoming_tasks()
    else:
        tasks = upcoming_tasks()
    logger.info("Loaded %d upcoming tasks", len(tasks))

    unfiltered_tasks = list(tasks)

    entries = read_entries()
    logger.info("Loaded %d energy entries", len(entries))
    if recorded_entry and recorded_entry not in entries:
        entries = [*entries, recorded_entry]
    latest = recorded_entry or (entries[-1] if entries else {})
    energy_level = latest.get("energy")
    if energy_level is not None:
        logger.info("Filtering tasks by energy=%s", energy_level)
        filtered_tasks = filter_tasks_by_energy(tasks, int(energy_level))
        if not filtered_tasks and unfiltered_tasks:
            logger.info(
                "Energy filter removed all tasks; falling back to unfiltered task list"
            )
            tasks = unfiltered_tasks
        else:
            tasks = filtered_tasks
        logger.info("Tasks after energy filter: %d", len(tasks))
    else:
        logger.info("No energy entry found; skipping energy filter")

    if selected_mode == "next_task":
        next_task = _select_next_task(tasks, latest.get("mood"), energy_level)
        plan_text = next_task.get("title", "") if next_task else ""
        logger.info("Selected next task: %s", next_task)
        return PlanResponse(plan=plan_text, next_task=next_task)

    if template == "plan_intensity_selector":
        selector_template = PROJECT_ROOT / "prompts" / "plan_intensity_selector.txt"
        prompt = render_prompt(
            str(selector_template), {"tasks": tasks, "intensity": intensity}
        )
        logger.debug("Selector prompt: %s", prompt)
        response = await ask_chatgpt(prompt)
        logger.info("Generated selector response: %s", response)
        return PlanResponse(plan=response)

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
    template_path = PROJECT_ROOT / "prompts" / "morning_planner.txt"
    prompt = render_prompt(str(template_path), variables)
    logger.debug("Final plan prompt: %s", prompt)
    plan = await ask_chatgpt(prompt)
    logger.info("Generated plan: %s", plan)
    save_plan(plan)
    logger.info("Plan saved")
    return PlanResponse(plan=plan)


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
