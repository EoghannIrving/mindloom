"""Unit tests for the project parsing utilities."""

from __future__ import annotations

# pylint: disable=wrong-import-position, duplicate-code, import-outside-toplevel, reimported

import sys
from pathlib import Path
import textwrap
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import parse_projects
from parse_projects import (
    extract_frontmatter,
    extract_tasks,
    summarize_body,
    parse_markdown_file,
)


def test_extract_frontmatter():
    """Ensure YAML frontmatter is parsed correctly."""
    md = textwrap.dedent(
        """---
status: active
area: work
effort: high
last_reviewed: 2024-01-01
---
Body text
"""
    )
    frontmatter, body = extract_frontmatter(md)
    assert frontmatter["status"] == "active"
    assert frontmatter["area"] == "work"
    assert frontmatter["effort"] == "high"
    assert str(frontmatter["last_reviewed"]) == "2024-01-01"
    assert body == "Body text"


def test_extract_tasks():
    """Extract markdown tasks from the body."""
    body = textwrap.dedent(
        """- [ ] Task one
- [x] Task two
Other line
"""
    )
    tasks = extract_tasks(body)
    assert tasks == ["- [ ] Task one", "- [x] Task two"]


def test_summarize_body():
    """Summarize the body by returning the first paragraph."""
    text = textwrap.dedent(
        """# Heading
Paragraph one.

> quoted text

Paragraph two.
"""
    )
    assert summarize_body(text) == "Paragraph one."


def test_parse_markdown_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Parse a markdown file and return expected metadata."""
    md_content = textwrap.dedent(
        """---
status: active
last_reviewed: 2024-02-02
---
Some body
- [ ] Task
"""
    )
    md_file = tmp_path / "example.md"
    md_file.write_text(md_content, encoding="utf-8")

    # patch PROJECTS_DIR so relative path calculation works
    monkeypatch.setattr(parse_projects, "PROJECTS_DIR", tmp_path)
    result = parse_markdown_file(md_file)

    assert result["title"] == "example"
    assert result["status"] == "active"
    assert str(result["last_reviewed"]) == "2024-02-02"
    assert result["tasks"] == ["- [ ] Task"]


def test_parse_all_projects_expands_tilde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """parse_all_projects should expand '~' in the vault path."""
    home = tmp_path / "home"
    vault = home / "vault" / "Projects"
    vault.mkdir(parents=True)
    md_file = vault / "note.md"
    md_file.write_text("Body", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VAULT_PATH", "~/vault/Projects")

    import importlib
    import config as cfg

    importlib.reload(cfg)
    import parse_projects as pp

    importlib.reload(pp)

    projects = pp.parse_all_projects()
    assert projects[0]["title"] == "note"


def test_parse_all_projects_creates_missing_root(tmp_path: Path):
    """parse_all_projects should create and return [] for a missing vault."""
    missing = tmp_path / "vault" / "Projects"
    projects = parse_projects.parse_all_projects(missing)
    assert projects == []
    assert missing.is_dir()


def test_save_tasks_yaml(tmp_path: Path):
    """save_tasks_yaml should write tasks in the expected format."""
    projects = [
        {
            "title": "demo",
            "path": "demo.md",
            "area": "work",
            "effort": "medium",
            "status": "active",
            "tasks": ["- [ ] First", "- [x] Second"],
        }
    ]
    tasks_file = tmp_path / "tasks.yaml"
    from parse_projects import save_tasks_yaml
    from tasks import read_tasks

    tasks = save_tasks_yaml(projects, tasks_file)
    data = read_tasks(tasks_file)

    assert len(data) == len(tasks)
    assert len(data) == 2
    assert data[0]["id"] == 1
    assert data[0]["title"] == "First"
    assert data[0]["type"] == "task"
    assert data[0]["project"] == "demo.md"


def test_parse_task_line_with_metadata():
    """Inline due dates and recurrence should be parsed from each line."""
    line = "- [ ] Demo Recurrence: weekly Due Date: 2025-01-01"
    title, completed, due, recurrence = parse_projects._parse_task_line(line)
    assert title == "Demo"
    assert completed is False
    assert due == "2025-01-01"
    assert recurrence == "weekly"


def test_line_overrides_frontmatter():
    """Per-line metadata should override project frontmatter."""
    projects = [
        {
            "title": "demo",
            "path": "demo.md",
            "due": "2025-12-31",
            "recurrence": "monthly",
            "tasks": ["- [ ] Task Recurrence: weekly Due Date: 2025-01-01"],
        }
    ]
    tasks = parse_projects.projects_to_tasks(projects)
    assert tasks[0]["due"] == "2025-01-01"
    assert tasks[0]["recurrence"] == "weekly"


def test_write_tasks_to_projects(tmp_path: Path):
    """write_tasks_to_projects should update markdown tasks."""
    project_dir = tmp_path / "Projects"
    project_dir.mkdir()
    md_file = project_dir / "demo.md"
    md_file.write_text("- [ ] First\n- [ ] Second\n", encoding="utf-8")

    tasks = [
        {
            "id": 1,
            "title": "First",
            "project": "Projects/demo.md",
            "status": "complete",
        },
        {
            "id": 2,
            "title": "Second",
            "project": "Projects/demo.md",
            "recurrence": "daily",
            "status": "active",
        },
    ]

    parse_projects.write_tasks_to_projects(tasks, project_dir)

    lines = md_file.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "- [x] First"
    assert lines[1] == "- [ ] Second Recurrence: daily"
