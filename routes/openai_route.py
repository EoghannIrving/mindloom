"""FastAPI router for interacting with the OpenAI API."""

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Literal, NoReturn, Optional, Tuple
from pydantic import BaseModel
import logging

from calendar_integration import load_events
from fastapi import APIRouter, Body, HTTPException, Query

from openai_client import OpenAIClientError, ask_chatgpt
from prompt_renderer import render_prompt
from tasks import upcoming_tasks
from energy import latest_entry, read_entries, record_entry
from planner import save_plan, filter_tasks_by_energy
from config import PROJECT_ROOT, config
from task_selector import effective_energy_level, select_next_task

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


def _raise_language_model_error(context: str, exc: Exception, detail: str) -> NoReturn:
    logger.error("%s OpenAI call failed: %s", context, exc)
    raise HTTPException(status_code=502, detail=detail) from exc


@router.post("/ask")
async def ask_endpoint(data: dict = Body(...)):
    """Send the provided prompt to ChatGPT and return the response."""
    prompt: str = data.get("prompt", "")
    if not prompt:
        logger.warning("POST /ask missing prompt")
        return {"error": "Prompt is required"}

    logger.info("POST /ask prompt_length=%s", len(prompt))
    try:
        response = await ask_chatgpt(prompt)
    except OpenAIClientError as exc:
        _raise_language_model_error(
            "POST /ask",
            exc,
            "Failed to fetch response from language model. Please try again later.",
        )
    logger.info("POST /ask response_length=%s", len(response))
    return {"response": response}


class PlanRequest(BaseModel):
    energy: Optional[int] = None
    mood: Optional[str] = None
    time_blocks: Optional[int] = None
    project: Optional[str] = None
    area: Optional[str] = None


class PlanResponse(BaseModel):
    plan: str
    next_task: Optional[Dict[str, Any]] = None
    reasoning: Optional[Dict[str, Any]] = None


def _payload_field_summary(payload: Optional[PlanRequest]) -> str:
    if not payload:
        return "none"
    data = payload.model_dump(exclude_none=True)
    if not data:
        return "none"
    return ",".join(sorted(data.keys()))


def _normalize_filter_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _matches_filter(task_value: Any, filter_value: str) -> bool:
    normalized = _normalize_filter_value(task_value)
    if normalized is None:
        return False
    return normalized.casefold() == filter_value.casefold()


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
    project_param: Optional[str] = Query(
        None,
        description="Optional project filter applied before energy filtering.",
    ),
    area_param: Optional[str] = Query(
        None,
        description="Optional area filter applied before energy filtering.",
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

    payload_energy = payload.energy if payload else None
    payload_mood = payload.mood if payload else None
    payload_time_blocks = payload.time_blocks if payload else None
    payload_values = (payload_energy, payload_mood, payload_time_blocks)
    has_all_payload_fields = all(value is not None for value in payload_values)
    has_any_payload_field = any(value is not None for value in payload_values)

    payload_project = _normalize_filter_value(payload.project if payload else None)
    payload_area = _normalize_filter_value(payload.area if payload else None)
    query_project = _normalize_filter_value(project_param)
    query_area = _normalize_filter_value(area_param)
    project_filter_value = payload_project or query_project
    area_filter_value = payload_area or query_area

    if selected_mode == "next_task" and not (
        payload_energy is not None and payload_mood is not None
    ):
        logger.warning(
            "Missing energy payload for next_task mode: provided_fields=%s",
            _payload_field_summary(payload),
        )
        raise HTTPException(
            status_code=400,
            detail="Energy and mood are required for next_task mode.",
        )

    recorded_entry: Optional[Dict[str, Any]] = None
    payload_snapshot: Optional[Dict[str, Any]] = None
    if payload:
        snapshot: Dict[str, Any] = {}
        if payload_energy is not None:
            snapshot["energy"] = payload_energy
        if payload_mood is not None:
            snapshot["mood"] = payload_mood
        if payload_time_blocks is not None:
            snapshot["time_blocks"] = payload_time_blocks
        if snapshot:
            payload_snapshot = snapshot

    if selected_mode == "next_task":
        recorded_entry = record_entry(payload_energy, payload_mood, payload_time_blocks)
        logger.info(
            "Persisted energy entry via API for next_task date=%s recorded_at=%s",
            recorded_entry.get("date"),
            recorded_entry.get("recorded_at"),
        )
        logger.debug("Persisted energy entry details: %s", recorded_entry)
    elif payload and has_all_payload_fields:
        recorded_entry = record_entry(payload_energy, payload_mood, payload_time_blocks)
        logger.info(
            "Persisted energy entry via API for date=%s",
            recorded_entry.get("date"),
        )
        logger.debug("Persisted energy entry details: %s", recorded_entry)
    elif payload and payload_time_blocks is not None:
        logger.warning(
            "Incomplete energy payload provided; skipping record_entry call: provided_fields=%s",
            _payload_field_summary(payload),
        )
    elif payload and has_any_payload_field:
        logger.info(
            "Energy or mood provided without time blocks; skipping record_entry call"
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
    metadata_filters_active = False
    metadata_filter_eliminated_all = False
    filters_requested = bool(project_filter_value or area_filter_value)

    if filters_requested:
        logger.info(
            "Applying task metadata filters project=%s area=%s",
            project_filter_value,
            area_filter_value,
        )
        metadata_filtered_tasks = [
            task
            for task in unfiltered_tasks
            if (
                (
                    not project_filter_value
                    or _matches_filter(task.get("project"), project_filter_value)
                )
                and (
                    not area_filter_value
                    or _matches_filter(task.get("area"), area_filter_value)
                )
            )
        ]
        if metadata_filtered_tasks:
            tasks = metadata_filtered_tasks
            logger.info("Tasks after metadata filter: %d", len(tasks))
            metadata_filters_active = True
        else:
            logger.info(
                "Task metadata filter removed all tasks; no tasks remain after applying filters"
            )
            tasks = []
            metadata_filters_active = True
            metadata_filter_eliminated_all = True

    metadata_filtered_tasks = list(tasks)
    if metadata_filters_active and not metadata_filtered_tasks:
        metadata_filter_eliminated_all = True

    entries = read_entries()
    logger.info("Loaded %d energy entries", len(entries))
    if recorded_entry and recorded_entry not in entries:
        entries = [*entries, recorded_entry]
    latest_record = latest_entry(entries)
    latest = recorded_entry or payload_snapshot or (latest_record or {})
    energy_level = latest.get("energy")
    mood_value = latest.get("mood")
    target_energy = effective_energy_level(energy_level, mood_value)
    if energy_level is None and mood_value is None:
        logger.info(
            "No recent energy or mood entry found; using default target for filtering",
        )
    else:
        logger.info(
            "Applying energy filter to tasks using effective energy level %s",
            target_energy,
        )
        logger.debug(
            "Filter inputs - recorded energy: %s mood: %s",
            energy_level,
            mood_value,
        )
    filtered_tasks = filter_tasks_by_energy(tasks, target_energy)
    if not filtered_tasks and unfiltered_tasks:
        if metadata_filters_active:
            logger.info(
                "Energy filter removed all tasks; falling back to metadata-filtered task list",
            )
            tasks = metadata_filtered_tasks
        else:
            logger.info(
                "Energy filter removed all tasks; falling back to unfiltered task list",
            )
            tasks = unfiltered_tasks
    else:
        tasks = filtered_tasks
    logger.info("Tasks after energy filter: %d", len(tasks))

    if selected_mode == "next_task":
        next_task, reasoning = select_next_task(tasks, mood_value, energy_level)
        if next_task:
            plan_text = next_task.get("title", "")
        elif metadata_filter_eliminated_all:
            plan_text = "No tasks match the selected project or area filters."
        else:
            plan_text = ""
        if next_task:
            logger.info(
                "Selected next task id=%s due=%s",
                next_task.get("id"),
                next_task.get("due") or next_task.get("next_due"),
            )
            logger.debug("Selected next task details: %s", next_task)
        else:
            if metadata_filter_eliminated_all:
                logger.info(
                    "No next task selected because no tasks matched the requested metadata filters"
                )
            else:
                logger.info("No next task selected")
        return PlanResponse(plan=plan_text, next_task=next_task, reasoning=reasoning)

    if template == "plan_intensity_selector":
        selector_template = PROJECT_ROOT / "prompts" / "plan_intensity_selector.txt"
        prompt = render_prompt(
            str(selector_template), {"tasks": tasks, "intensity": intensity}
        )
        logger.debug("Selector prompt: %s", prompt)
        try:
            response = await ask_chatgpt(prompt)
        except OpenAIClientError as exc:
            _raise_language_model_error(
                "POST /plan selector",
                exc,
                "Failed to generate selector response from language model. Please try again later.",
            )
        response_text = response or ""
        logger.info("Generated selector response length=%s", len(response_text))
        if response_text:
            preview = response_text[:200]
            if len(preview) < len(response_text):
                preview = f"{preview}…"
            logger.debug("Selector response preview: %s", preview)
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
    try:
        plan = await ask_chatgpt(prompt)
    except OpenAIClientError as exc:
        _raise_language_model_error(
            "POST /plan",
            exc,
            "Failed to generate plan from language model. Please try again later.",
        )
    plan_text = plan or ""
    logger.info("Generated plan length=%s", len(plan_text))
    if plan_text:
        plan_preview = plan_text[:200]
        if len(plan_preview) < len(plan_text):
            plan_preview = f"{plan_preview}…"
        logger.debug("Generated plan preview: %s", plan_preview)
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
    try:
        result = await ask_chatgpt(prompt)
    except OpenAIClientError as exc:
        _raise_language_model_error(
            "POST /goal-breakdown",
            exc,
            "Failed to generate goal breakdown from language model. Please try again later.",
        )
    logger.info("POST /goal-breakdown response_length=%s", len(result))
    return {"tasks": result}
