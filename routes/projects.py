"""API routes for project information."""

# pylint: disable=duplicate-code

import json
from pathlib import Path
from typing import List, Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from parse_projects import (
    _task_to_line,
    TASK_LINE_PATTERN,
    VALID_KEYS,
    extract_frontmatter,
    extract_tasks,
    merge_project_files,
    parse_all_projects,
    save_tasks_yaml,
    write_tasks_to_projects,
)
from tasks import read_tasks, read_tasks_raw, write_tasks

from config import config
from utils.logging import configure_logger
from utils.vault import normalize_slug_path, resolve_slug_path
from utils.auth import enforce_api_key

router = APIRouter()
PROJECTS_FILE = Path(config.OUTPUT_PATH)
TASKS_FILE = Path(config.TASKS_PATH)
VAULT_ROOT = Path(config.VAULT_PATH)

LOG_FILE = Path(config.LOG_DIR) / "projects.log"
logger = configure_logger(__name__, LOG_FILE)
PROJECT_FRONTMATTER_KEYS = [
    "status",
    "area",
    "effort",
    "due",
    "recurrence",
    "last_completed",
    "executive_trigger",
    "last_reviewed",
]


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
    description: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:  # noqa: D401
        """Ensure the slug stays within the vault."""

        path = Path(value)
        if path.is_absolute() or any(part == ".." for part in path.parts):
            raise ValueError("slug must be a relative path without traversal")
        return value


class ProjectMergeRequest(BaseModel):
    """Payload schema for merging two project markdown files."""

    source_slug: str = Field(..., min_length=1)
    target_slug: str = Field(..., min_length=1)
    delete_source: bool = Field(True, description="Remove the source file after merge")

    @field_validator("source_slug", "target_slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:  # noqa: D401
        """Ensure the slug stays within the vault and normalize it."""

        vault_root = Path(config.VAULT_PATH)
        normalized = normalize_slug_path(value, vault_root)
        return str(normalized)


class ProjectUpdateRequest(BaseModel):
    """Payload schema for updating project metadata and tasks."""

    title: Optional[str] = None
    status: Optional[str] = None
    area: Optional[str] = None
    effort: Optional[str] = None
    due: Optional[str] = None
    recurrence: Optional[str] = None
    last_completed: Optional[str] = None
    executive_trigger: Optional[str] = None
    last_reviewed: Optional[str] = None
    tasks_text: Optional[str] = None
    description: Optional[str] = None


def _normalize_task_lines(raw: str) -> List[str]:
    lines: List[str] = []
    for entry in raw.splitlines():
        trimmed = entry.strip()
        if not trimmed:
            continue
        if not TASK_LINE_PATTERN.match(trimmed):
            trimmed = f"- [ ] {trimmed}"
        lines.append(trimmed)
    return lines


def _extract_description_lines(body: str) -> List[str]:
    lines: List[str] = []
    seen_title = False
    for line in body.splitlines():
        stripped = line.lstrip()
        if not seen_title and stripped.startswith("# "):
            seen_title = True
            continue
        if not seen_title:
            continue
        if TASK_LINE_PATTERN.match(line):
            break
        lines.append(line)
    # Trim leading/trailing blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _compose_description_lines(
    title_value: str, description_override: Optional[str], body: str
) -> List[str]:
    description_lines: List[str]
    if description_override is not None:
        description_lines = description_override.splitlines()
    else:
        description_lines = _extract_description_lines(body)
    result = [f"# {title_value}"]
    if description_lines:
        result.append("")
        result.extend(description_lines)
    return result


def _assemble_project_content(
    frontmatter: dict, desc_lines: List[str], task_lines: List[str]
) -> str:
    frontmatter_yaml = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    sections = ["---", frontmatter_yaml, "---"]
    desc_text = "\n".join(desc_lines).strip()
    if desc_text:
        sections.extend(["", desc_text])
    if task_lines:
        sections.extend(["", *task_lines])
    return "\n".join(sections).rstrip() + "\n"


def _extract_title_from_body(body: str, fallback: str) -> str:
    for line in body.splitlines():
        candidate = line.strip()
        if candidate.startswith("# "):
            return candidate[2:].strip() or fallback
    return fallback


@router.get("/projects")
def get_projects(
    status: Optional[str] = Query(None),
    area: Optional[str] = Query(None),
    effort: Optional[str] = Query(None),
):
    """Return projects filtered by query parameters."""
    logger.info(
        "GET /projects filters status=%s area=%s effort=%s",
        bool(status),
        bool(area),
        bool(effort),
    )
    if status or area or effort:
        logger.debug(
            "GET /projects filter values status=%s area=%s effort=%s",
            status,
            area,
            effort,
        )
    if not PROJECTS_FILE.exists():
        logger.warning("%s not found", PROJECTS_FILE)
        return {"error": f"{PROJECTS_FILE} not found"}

    with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
        projects = yaml.safe_load(f) or []

    if status:
        projects = [p for p in projects if p.get("status") == status]
    if area:
        projects = [p for p in projects if p.get("area") == area]
    if effort:
        projects = [p for p in projects if p.get("effort") == effort]

    logger.info("Returning %d projects", len(projects))
    return projects


@router.get("/projects/{slug:path}")
def get_project(slug: str):
    """Return a single project's metadata and checklist."""
    logger.info("GET /projects/%s", slug)
    try:
        project_path = resolve_slug_path(slug, VAULT_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if not project_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project file not found"
        )
    content = project_path.read_text(encoding="utf-8")
    frontmatter, body = extract_frontmatter(content)
    tasks = extract_tasks(body)
    title = _extract_title_from_body(body, project_path.stem)
    description_lines = _extract_description_lines(body)
    description = "\n".join(description_lines) if description_lines else ""
    return {
        "title": title,
        "slug": str(project_path.relative_to(VAULT_ROOT)),
        "path": str(project_path.relative_to(VAULT_ROOT.parent)),
        "tasks": tasks,
        "description": description,
        **frontmatter,
    }


@router.put("/projects/{slug:path}")
def update_project(
    slug: str, payload: ProjectUpdateRequest, _: None = Depends(enforce_api_key)
):
    """Update an existing project's metadata or checklist."""
    logger.info("PUT /projects/%s", slug)
    try:
        project_path = resolve_slug_path(slug, VAULT_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if not project_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project file not found"
        )

    content = project_path.read_text(encoding="utf-8")
    frontmatter, body = extract_frontmatter(content)
    existing_title = _extract_title_from_body(body, project_path.stem)
    updates = {
        key: getattr(payload, key)
        for key in PROJECT_FRONTMATTER_KEYS
        if getattr(payload, key) is not None
    }
    frontmatter.update(updates)
    title_value = payload.title or existing_title
    desc_lines = _compose_description_lines(title_value, payload.description, body)
    task_lines = (
        _normalize_task_lines(payload.tasks_text)
        if payload.tasks_text is not None
        else extract_tasks(body)
    )
    new_content = _assemble_project_content(frontmatter, desc_lines, task_lines)
    project_path.write_text(new_content, encoding="utf-8")
    logger.info("Updated project %s", project_path)
    return {
        "title": payload.title or existing_title,
        "slug": str(project_path.relative_to(VAULT_ROOT)),
        "path": str(project_path.relative_to(VAULT_ROOT.parent)),
        "tasks": len(task_lines),
    }


@router.post("/parse-projects")
def parse_projects_endpoint(_: None = Depends(enforce_api_key)):
    """Parse vault markdown files and update the projects YAML."""
    logger.info("POST /parse-projects")
    projects = parse_all_projects()
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        yaml.dump(projects, f, sort_keys=False, allow_unicode=True)
    logger.info("Parsed %d projects", len(projects))
    return {"count": len(projects)}


@router.post("/save-tasks")
def save_tasks_endpoint(_: None = Depends(enforce_api_key)):
    """Parse projects and write data/tasks.yaml."""
    logger.info("POST /save-tasks")
    projects = parse_all_projects()
    tasks = save_tasks_yaml(projects, TASKS_FILE)
    logger.info("Saved %d tasks", len(tasks))
    return {"count": len(tasks)}


@router.post("/write-tasks")
def write_tasks_endpoint(_: None = Depends(enforce_api_key)):
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
def create_project(payload: ProjectCreateRequest, _: None = Depends(enforce_api_key)):
    """Create a new project markdown file in the configured vault."""

    logger.info("POST /projects slug_length=%s", len(payload.slug))
    logger.debug("POST /projects slug=%s", payload.slug)
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

    frontmatter = {
        key: getattr(payload, key)
        for key in PROJECT_FRONTMATTER_KEYS
        if getattr(payload, key) is not None
    }

    frontmatter_yaml = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    task_lines = []
    for task in payload.tasks or []:
        task_lines.append(_task_to_line(task.model_dump(exclude_none=True)))

    desc_lines = _compose_description_lines(payload.title, payload.description, "")
    parts = ["---", frontmatter_yaml, "---", ""]
    parts.extend(desc_lines)
    if task_lines:
        parts.append("")
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
    logger.info("Created project file for slug_length=%s", len(payload.slug))
    logger.debug("Created project at %s", target_path)
    return response


def _resolve_slug(slug: str, vault_root: Path) -> Path:
    """Return the filesystem path for a slug within the vault."""

    try:
        return resolve_slug_path(slug, vault_root)
    except ValueError as exc:  # pragma: no cover - defensive, caught by validation
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/projects/merge")
def merge_projects(payload: ProjectMergeRequest, _: None = Depends(enforce_api_key)):
    """Merge two markdown project files and update derived data."""

    logger.info(
        "POST /projects/merge source_length=%s target_length=%s delete_source=%s",
        len(payload.source_slug),
        len(payload.target_slug),
        payload.delete_source,
    )

    vault_root = Path(config.VAULT_PATH)
    vault_root.mkdir(parents=True, exist_ok=True)

    source_path = _resolve_slug(payload.source_slug, vault_root)
    target_path = _resolve_slug(payload.target_slug, vault_root)

    if source_path == target_path:
        logger.warning(
            "Source and target slug resolve to the same path: %s", source_path
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and target projects must be different",
        )

    if not source_path.exists():
        logger.error("Source project missing: %s", source_path)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source project not found",
        )

    if not target_path.exists():
        logger.error("Target project missing: %s", target_path)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target project not found",
        )

    merge_result = merge_project_files(
        source_path,
        target_path,
        delete_source=payload.delete_source,
    )

    vault_parent = vault_root.parent
    source_rel = str(source_path.relative_to(vault_parent))
    target_rel = str(target_path.relative_to(vault_parent))

    logger.info("Updating tasks.yaml from %s to %s", source_rel, target_rel)
    tasks = read_tasks_raw(TASKS_FILE)
    migrated_yaml_tasks = 0
    unique_tasks = []
    seen = set()
    for task in tasks:
        if task.get("project") == source_rel:
            task["project"] = target_rel
            migrated_yaml_tasks += 1
        key = json.dumps(task, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            unique_tasks.append(task)

    write_tasks(unique_tasks, TASKS_FILE)
    logger.info("Updated %d tasks in tasks.yaml", migrated_yaml_tasks)

    logger.info("Regenerating projects.yaml and markdown tasks export")
    projects = parse_all_projects(vault_root)
    with open(PROJECTS_FILE, "w", encoding="utf-8") as handle:
        yaml.dump(projects, handle, sort_keys=False, allow_unicode=True)
    save_tasks_yaml(projects, TASKS_FILE)

    response = {
        "source": source_rel,
        "target": target_rel,
        "migrated_project_tasks": merge_result.get("source_tasks", 0),
        "target_total_tasks": merge_result.get("target_total_tasks", 0),
        "tasks_relinked": migrated_yaml_tasks,
        "source_removed": merge_result.get("source_removed", False),
    }
    logger.info("Merge complete: %s", response)
    return response
