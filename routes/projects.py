"""API routes for project information."""

from typing import Optional

import yaml
from fastapi import APIRouter, Query

from parse_projects import parse_all_projects

from config import config

router = APIRouter()
PROJECTS_FILE = config.OUTPUT_PATH

@router.get("/projects")
def get_projects(
    status: Optional[str] = Query(None),
    area: Optional[str] = Query(None),
    effort: Optional[str] = Query(None),
):
    """Return projects filtered by query parameters."""
    if not PROJECTS_FILE.exists():
        return {"error": f"{PROJECTS_FILE} not found"}

    with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
        projects = yaml.safe_load(f)

    if status:
        projects = [p for p in projects if p.get("status") == status]
    if area:
        projects = [p for p in projects if p.get("area") == area]
    if effort:
        projects = [p for p in projects if p.get("effort") == effort]

    return projects


@router.post("/parse-projects")
def parse_projects_endpoint():
    """Parse vault markdown files and update the projects YAML."""
    projects = parse_all_projects()
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        yaml.dump(projects, f, sort_keys=False, allow_unicode=True)
    return {"count": len(projects)}
