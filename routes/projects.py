"""API routes for project information."""

# pylint: disable=duplicate-code

import logging
from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, Query

from parse_projects import parse_all_projects

from config import config

router = APIRouter()
PROJECTS_FILE = Path(config.OUTPUT_PATH)

LOG_FILE = Path(config.LOG_DIR) / "projects.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


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
