"""Utility functions for extracting project metadata from markdown files."""

# pylint: disable=duplicate-code

import re
import logging
from pathlib import Path
import yaml

from config import config
from tasks import write_tasks

TASKS_FILE = Path(config.TASKS_PATH)

PROJECTS_DIR = Path(config.VAULT_PATH)
OUTPUT_FILE = Path(config.OUTPUT_PATH)
LOG_FILE = Path(config.LOG_DIR) / "parse_projects.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
VALID_KEYS = {
    "status",
    "area",
    "effort",
    "due",
    "recurrence",
    "last_completed",
    "executive_trigger",
    "last_reviewed",
}


def extract_frontmatter(text):
    """Return frontmatter dict and remaining body from a markdown string."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            try:
                front = yaml.safe_load(text[3:end])
                data = {k: front.get(k) for k in VALID_KEYS if k in front}
                logger.debug("Parsed frontmatter: %s", data)
                return data, text[end + 3 :].strip()
            except yaml.YAMLError as exc:
                logger.warning("Failed to parse frontmatter: %s", exc)
    return {}, text


def extract_tasks(text):
    """Extract markdown task list items."""
    return re.findall(r"- \[[ xX]\] .+", text)


def summarize_body(text, max_chars=300):
    """Return the first paragraph without headings or block quotes."""
    body = re.sub(r"#+ .*", "", text)
    body = re.sub(r"> .*", "", body)
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    return paras[0][:max_chars] if paras else ""


def parse_markdown_file(filepath):
    """Parse a single markdown project file."""
    logger.info("Parsing %s", filepath)
    with open(filepath, "r", encoding="utf-8") as handle:
        content = handle.read()
    frontmatter, body = extract_frontmatter(content)
    tasks = extract_tasks(body)
    summary = summarize_body(body)
    data = {
        "title": filepath.stem,
        "path": str(filepath.relative_to(PROJECTS_DIR.parent)),
        **frontmatter,
        "tasks": tasks,
        "summary": summary,
    }
    logger.debug("Parsed data for %s: %s", filepath, data)
    return data


def parse_all_projects(root=PROJECTS_DIR):
    """Return a list of parsed projects from the given directory."""
    root = Path(root).expanduser()
    logger.info("Scanning %s for markdown files", root)
    if not root.is_dir():
        logger.info("%s does not exist, creating it", root)
        root.mkdir(parents=True, exist_ok=True)
        return []
    md_files = list(root.rglob("*.md"))
    logger.info("Found %d markdown files", len(md_files))
    projects = [parse_markdown_file(md) for md in md_files]
    logger.info("Parsed %d projects", len(projects))
    return projects


def projects_to_tasks(projects):
    """Convert parsed project data to task entries using the task schema."""
    mapping = {"low": 1, "medium": 3, "high": 5}
    tasks = []
    for idx, proj in enumerate(projects, start=1):
        task = {
            "id": idx,
            "title": proj.get("title"),
            "area": proj.get("area", ""),
            "type": "project",
            "due": proj.get("due"),
            "recurrence": proj.get("recurrence"),
            "effort": proj.get("effort", "low"),
            "energy_cost": mapping.get(proj.get("effort", "low"), 1),
            "status": proj.get("status", "active"),
            "last_completed": proj.get("last_completed"),
            "executive_trigger": proj.get("executive_trigger"),
        }
        tasks.append(task)
    return tasks


def save_tasks_yaml(projects, path=TASKS_FILE):
    """Write project tasks to a YAML file using the tasks schema."""
    tasks = projects_to_tasks(projects)
    write_tasks(tasks, path)
    return tasks


if __name__ == "__main__":
    logger.info("Starting project parsing")
    all_projects = parse_all_projects()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        yaml.dump(all_projects, f, sort_keys=False, allow_unicode=True)
    logger.info("Wrote %d projects to %s", len(all_projects), OUTPUT_FILE)
    save_tasks_yaml(all_projects)
    logger.info("Wrote tasks to %s", TASKS_FILE)
