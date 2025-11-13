"""API routes for Discord integrations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from config import config
from tasks import read_tasks
from task_selector import select_next_task
from utils.logging import configure_logger
from utils.tasks import filter_tasks_by_metadata

router = APIRouter(prefix="/discord", tags=["discord"])

LOG_FILE = Path(config.LOG_DIR) / "discord_api.log"
logger = configure_logger(__name__, LOG_FILE)


class NextTaskResponse(BaseModel):
    """Payload returned when requesting a single task recommendation."""

    task: Optional[Dict[str, Any]] = Field(
        default=None, description="Selected task or null when none match."
    )
    reasoning: Optional[Dict[str, Any]] = Field(
        default=None, description="Selection heuristics for the chosen task."
    )
    total_tasks: int = Field(
        0,
        ge=0,
        description="Number of incomplete tasks that satisfied the provided filters.",
    )


class ProjectListResponse(BaseModel):
    """Wrapper for project identifiers used by Discord autocomplete."""

    projects: List[str] = Field(default_factory=list)


def _filter_tasks(
    tasks: List[Dict[str, Any]], project_filter: Optional[str]
) -> List[Dict[str, Any]]:
    """Return incomplete tasks filtered by the optional project name."""

    return filter_tasks_by_metadata(
        tasks,
        project=project_filter,
        project_contains=True,
        exclude_completed=True,
    )


@router.get("/next-task", response_model=NextTaskResponse)
def next_task(
    project: Optional[str] = Query(
        None, description="Filter tasks to a specific project."
    ),
    energy: Optional[int] = Query(
        None, description="Override the effective energy level used for scoring."
    ),
    mood: Optional[str] = Query(
        None,
        description="Optional mood label to refine the effective energy level.",
    ),
) -> NextTaskResponse:
    """Return the next best task for the Discord bot."""

    logger.info(
        "GET /discord/next-task project=%s energy=%s mood=%s",
        project,
        energy,
        mood,
    )

    tasks = read_tasks()
    filtered = _filter_tasks(tasks, project)
    logger.info("Tasks available after filters: %d", len(filtered))

    if not filtered:
        logger.info("No tasks available for selection")
        return NextTaskResponse(total_tasks=0)

    selected, reasoning = select_next_task(filtered, mood, energy)
    logger.debug("Selected task: %s", selected)
    logger.debug("Selection reasoning: %s", reasoning)

    task_payload = dict(selected) if selected else None
    reasoning_payload = dict(reasoning) if reasoning else None

    return NextTaskResponse(
        task=task_payload,
        reasoning=reasoning_payload,
        total_tasks=len(filtered),
    )


def _normalize_projects(tasks: List[Dict[str, Any]]) -> List[str]:
    """Return sorted unique project identifiers from task metadata."""

    unique: set[str] = set()
    for task in tasks:
        project = task.get("project")
        if not project:
            continue
        key = str(project).strip()
        if not key:
            continue
        unique.add(key)
    return sorted(unique)


@router.get("/projects", response_model=ProjectListResponse)
def project_list(
    query: Optional[str] = Query(
        None,
        alias="q",
        description="Optional substring used to filter the returned project names.",
    ),
) -> ProjectListResponse:
    """Return project identifiers for Discord autocomplete."""

    logger.info("GET /discord/projects query=%s", query)

    tasks = read_tasks()
    projects = _normalize_projects(tasks)

    if query:
        term = query.strip().lower()
        projects = [p for p in projects if term in p.lower()]

    logger.info("Returning %d projects", len(projects))
    return ProjectListResponse(projects=projects)
