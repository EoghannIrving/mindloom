"""Unit tests for the project parsing utilities."""

from __future__ import annotations

# pylint: disable=wrong-import-position

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
---
Body text
"""
    )
    frontmatter, body = extract_frontmatter(md)
    assert frontmatter == {"status": "active", "area": "work", "effort": "high"}
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
