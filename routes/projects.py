"""API routes for project information."""

# pylint: disable=duplicate-code

import logging
from pathlib import Path
from typing import List, Optional

import yaml
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from parse_projects import (
    _task_to_line,
    parse_all_projects,
    save_tasks_yaml,
    write_tasks_to_projects,
)
from tasks import read_tasks

from config import config

router = APIRouter()
PROJECTS_FILE = Path(config.OUTPUT_PATH)
TASKS_FILE = Path(config.TASKS_PATH)

LOG_FILE = Path(config.LOG_DIR) / "projects.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class ProjectTask(BaseModel):
    """Schema for checklist items associated with a project."""

    title: str = Field(..., min_length=1)
    status: str = Field("active", description="Task completion state.")
    due: Optional[str] = None
    recurrence: Optional[str] = None
    effort: Optional[str] = None
    energy_cost: Optional[int] = None
    last_completed: Optional[str] = None
    executive_trigger: Optional[str] = None


class ProjectCreateRequest(BaseModel):
    """Payload schema for creating a new markdown project file."""

    title: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    area: str = Field(..., min_length=1)
    effort: str = Field(..., min_length=1)
    due: Optional[str] = None
    recurrence: Optional[str] = None
    last_completed: Optional[str] = None
    executive_trigger: Optional[str] = None
    last_reviewed: Optional[str] = None
    tasks: Optional[List[ProjectTask]] = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:  # noqa: D401
        """Ensure the slug stays within the vault."""

        path = Path(value)
        if path.is_absolute() or any(part == ".." for part in path.parts):
            raise ValueError("slug must be a relative path without traversal")
        return value


@router.get("/projects")
def get_projects(
    status: Optional[str] = Query(None),
    area: Optional[str] = Query(None),
    effort: Optional[str] = Query(None),
):
    """Return projects filtered by query parameters."""
    logger.info(
        "GET /projects status=%s area=%s effort=%s",
        status,
        area,
        effort,
    )
    if not PROJECTS_FILE.exists():
        logger.warning("%s not found", PROJECTS_FILE)
        return {"error": f"{PROJECTS_FILE} not found"}

    with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
        projects = yaml.safe_load(f)

    if status:
        projects = [p for p in projects if p.get("status") == status]
    if area:
        projects = [p for p in projects if p.get("area") == area]
    if effort:
        projects = [p for p in projects if p.get("effort") == effort]

    logger.info("Returning %d projects", len(projects))
    return projects


@router.post("/parse-projects")
def parse_projects_endpoint():
    """Parse vault markdown files and update the projects YAML."""
    logger.info("POST /parse-projects")
    projects = parse_all_projects()
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        yaml.dump(projects, f, sort_keys=False, allow_unicode=True)
    logger.info("Parsed %d projects", len(projects))
    return {"count": len(projects)}


@router.post("/save-tasks")
def save_tasks_endpoint():
    """Parse projects and write data/tasks.yaml."""
    logger.info("POST /save-tasks")
    projects = parse_all_projects()
    tasks = save_tasks_yaml(projects, TASKS_FILE)
    logger.info("Saved %d tasks", len(tasks))
    return {"count": len(tasks)}


@router.post("/write-tasks")
def write_tasks_endpoint():
    """Write modified tasks.yaml entries back to project files."""
    logger.info("POST /write-tasks")
    tasks = read_tasks(TASKS_FILE)
    count = write_tasks_to_projects(tasks, Path(config.VAULT_PATH))
    logger.info("Updated %d project files", count)
    return {"projects": count}


@router.get("/tasks")
def get_tasks():
    """Return saved tasks from data/tasks.yaml."""
    logger.info("GET /tasks")
    tasks = read_tasks(TASKS_FILE)
    logger.info("Returning %d tasks", len(tasks))
    return tasks


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreateRequest):
    """Create a new project markdown file in the configured vault."""

    logger.info("POST /projects slug=%s", payload.slug)
    vault_root = Path(config.VAULT_PATH)
    vault_root.mkdir(parents=True, exist_ok=True)

    slug_path = Path(payload.slug)
    if slug_path.suffix != ".md":
        slug_path = slug_path.with_suffix(".md")

    target_path = vault_root / slug_path
    if target_path.exists():
        logger.warning("Project already exists at %s", target_path)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project file already exists",
        )

    frontmatter_keys = [
        "status",
        "area",
        "effort",
        "due",
        "recurrence",
        "last_completed",
        "executive_trigger",
        "last_reviewed",
    ]
    frontmatter = {
        key: getattr(payload, key)
        for key in frontmatter_keys
        if getattr(payload, key) is not None
    }

    frontmatter_yaml = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    task_lines = []
    for task in payload.tasks or []:
        task_lines.append(_task_to_line(task.model_dump(exclude_none=True)))

    parts = ["---", frontmatter_yaml, "---", "", f"# {payload.title}", ""]
    parts.extend(task_lines)
    content = "\n".join(parts).rstrip() + "\n"

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as handle:
        handle.write(content)

    project_path = str(target_path.relative_to(vault_root.parent))
    response = {
        "title": payload.title,
        "path": project_path,
        **frontmatter,
        "tasks": task_lines,
    }
    logger.info("Created project at %s", target_path)
    return response
