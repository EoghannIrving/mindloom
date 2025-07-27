"""Utility functions for extracting project metadata from markdown files."""

import re
import logging
from pathlib import Path
import yaml

from config import config

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
VALID_KEYS = {"status", "area", "effort", "due"}


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
        raise FileNotFoundError(f"{root} does not exist")
    md_files = list(root.rglob("*.md"))
    logger.info("Found %d markdown files", len(md_files))
    projects = [parse_markdown_file(md) for md in md_files]
    logger.info("Parsed %d projects", len(projects))
    return projects


if __name__ == "__main__":
    logger.info("Starting project parsing")
    all_projects = parse_all_projects()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        yaml.dump(all_projects, f, sort_keys=False, allow_unicode=True)
    logger.info("Wrote %d projects to %s", len(all_projects), OUTPUT_FILE)
