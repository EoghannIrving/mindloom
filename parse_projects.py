"""Utility functions for extracting project metadata from markdown files."""

# pylint: disable=duplicate-code

import re
import logging
from pathlib import Path
from typing import List, Dict, Optional
import yaml

from config import config
from tasks import read_tasks_raw, write_tasks

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


def _parse_task_line(line):
    """Return task info parsed from a markdown list item."""
    match = re.match(r"- \[(?P<box>[ xX])\] (?P<rest>.+)", line.strip())
    if not match:
        return line.strip(), False, None, None

    completed = match.group("box").lower() == "x"
    rest = match.group("rest")

    parts = [p.strip() for p in rest.split(" | ")]
    title = parts[0]
    metadata = {}
    for segment in parts[1:]:
        if ":" in segment:
            key, value = segment.split(":", 1)
            metadata[key.strip()] = value.strip()

    return title, completed, metadata.get("due"), metadata.get("recur")


def projects_to_tasks(projects, start_id: int = 1):
    """Convert parsed project data to task entries using the task schema."""
    mapping = {"low": 1, "medium": 3, "high": 5}
    tasks = []
    idx = start_id
    for proj in projects:
        for line in proj.get("tasks", []):
            title, completed, line_due, line_recurrence = _parse_task_line(line)
            task = {
                "id": idx,
                "title": title,
                "project": proj.get("path"),
                "area": proj.get("area", ""),
                "type": "task",
                "due": line_due if line_due else proj.get("due"),
                "recurrence": (
                    line_recurrence if line_recurrence else proj.get("recurrence")
                ),
                "effort": proj.get("effort", "low"),
                "energy_cost": mapping.get(proj.get("effort", "low"), 1),
                "status": "complete" if completed else proj.get("status", "active"),
                "last_completed": proj.get("last_completed") if completed else None,
                "executive_trigger": proj.get("executive_trigger"),
                "source": "markdown",
            }
            tasks.append(task)
            idx += 1
    return tasks


def save_tasks_yaml(projects, path=TASKS_FILE):
    """Write project tasks to a YAML file using the tasks schema."""
    existing_tasks = read_tasks_raw(path)

    def is_markdown_task(task: Dict) -> bool:
        project = task.get("project")
        if not project:
            return False
        source = task.get("source")
        if source is None:
            return True
        return source == "markdown"

    preserved = [task for task in existing_tasks if not is_markdown_task(task)]

    def _numeric_id(task: Dict) -> Optional[int]:
        value = task.get("id")
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    numeric_ids = [
        task_id
        for task_id in (_numeric_id(task) for task in preserved)
        if task_id is not None
    ]
    next_id = max(numeric_ids, default=0) + 1
    project_tasks = projects_to_tasks(projects, start_id=next_id)
    combined = preserved + project_tasks
    write_tasks(combined, path)
    return combined


META_KEYS = {
    "due": "due",
    "recurrence": "recur",
    "effort": "effort",
    "energy_cost": "energy",
    "last_completed": "last",
    "executive_trigger": "exec",
}


def _task_to_line(task: Dict) -> str:
    """Return the markdown representation of a task."""
    line = "- [x] " if task.get("status") == "complete" else "- [ ] "
    line += task.get("title", "")
    meta = [
        f"{label}:{task[field]}"
        for field, label in META_KEYS.items()
        if task.get(field)
    ]
    if meta:
        line += " | " + " | ".join(meta)
    return line


def write_tasks_to_projects(tasks, root=PROJECTS_DIR):
    """Update markdown checklists based on tasks.yaml."""
    root = Path(root).expanduser()
    grouped: Dict[str, List[Dict]] = {}
    for task in tasks:
        proj = task.get("project")
        if proj:
            grouped.setdefault(str(proj), []).append(task)

    count = 0
    for rel_path, items in grouped.items():
        filepath = root.parent / rel_path
        if not filepath.exists():
            logger.warning("%s not found", filepath)
            continue

        with open(filepath, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()

        idx = 0
        new_lines: List[str] = []
        for line in lines:
            if re.match(r"\s*- \[[ xX]\] ", line) and idx < len(items):
                new_lines.append(_task_to_line(items[idx]))
                idx += 1
            elif re.match(r"\s*- \[[ xX]\] ", line):
                # skip leftover task lines beyond the yaml list
                continue
            else:
                new_lines.append(line)

        for t in items[idx:]:
            new_lines.append(_task_to_line(t))

        with open(filepath, "w", encoding="utf-8") as handle:
            handle.write("\n".join(new_lines) + "\n")

        count += 1

    return count


if __name__ == "__main__":
    logger.info("Starting project parsing")
    all_projects = parse_all_projects()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        yaml.dump(all_projects, f, sort_keys=False, allow_unicode=True)
    logger.info("Wrote %d projects to %s", len(all_projects), OUTPUT_FILE)
    save_tasks_yaml(all_projects)
    logger.info("Wrote tasks to %s", TASKS_FILE)
